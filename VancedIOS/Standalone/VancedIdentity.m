#import <Foundation/Foundation.h>
#import <Security/Security.h>
#import <CommonCrypto/CommonDigest.h>
#import <objc/runtime.h>
#import <objc/message.h>
#import <dispatch/dispatch.h>
#import <string.h>

static NSString * const VOfficialClientID = @"com.google.ios.youtube";
static IMP VOriginalSSOInit;
static IMP VOriginalAccessGroup;
static IMP VOriginalSharedGroup;
static IMP VOriginalCoreAccessGroup;
static IMP VOriginalCoreSharedGroup;
static IMP VOriginalGroupContainer;
static IMP VOriginalClientIDs[4];
static IMP VOriginalClientNames[3];

// Validate ABI before changing a method. Missing or incompatible methods keep
// their original behavior instead of being invoked through an assumed signature.
static BOOL VHasABI(Method method, const char *result, unsigned int argc) {
    if (!method || method_getNumberOfArguments(method) != argc) return NO;
    char *returnType = method_copyReturnType(method);
    BOOL match = returnType && strcmp(returnType, result) == 0;
    free(returnType);
    for (unsigned int i = 2; match && i < argc; ++i) {
        char *type = method_copyArgumentType(method, i);
        match = type && type[0] == '@';
        free(type);
    }
    return match;
}

static void VHook(const char *name, const char *selector, BOOL classMethod,
                  unsigned int argc, IMP replacement, IMP *original) {
    if (*original) return;
    Class cls = objc_getClass(name);
    if (!cls) return;
    if (classMethod) cls = object_getClass(cls);
    SEL sel = sel_registerName(selector);
    Method method = class_getInstanceMethod(cls, sel);
    if (!VHasABI(method, "@", argc)) return;
    IMP previous = method_getImplementation(method);
    if (!class_addMethod(cls, sel, replacement, method_getTypeEncoding(method))) {
        previous = method_setImplementation(class_getInstanceMethod(cls, sel), replacement);
    }
    *original = previous;
}

static NSString *VSigningAccessGroup(void) {
    static NSString *group;
    @synchronized (NSBundle.class) {
        if (group) return group;
        // Ask the OS for an item in this app's own default keychain group.
        // No access to YouTube's App Store keychain is requested or required.
        NSDictionary *query = @{
            (__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
            (__bridge id)kSecAttrAccount: @"VancedSigningGroup",
            (__bridge id)kSecAttrService: NSBundle.mainBundle.bundleIdentifier ?: @"ro.ion.youtubevanced",
            (__bridge id)kSecReturnAttributes: @YES
        };
        CFTypeRef attrs = NULL;
        OSStatus status = SecItemCopyMatching((__bridge CFDictionaryRef)query, &attrs);
        if (status == errSecItemNotFound) {
            NSMutableDictionary *add = query.mutableCopy;
            add[(__bridge id)kSecValueData] = [NSData data];
            add[(__bridge id)kSecAttrAccessible] = (__bridge id)kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly;
            status = SecItemAdd((__bridge CFDictionaryRef)add, &attrs);
            if (status == errSecDuplicateItem) {
                if (attrs) { CFRelease(attrs); attrs = NULL; }
                status = SecItemCopyMatching((__bridge CFDictionaryRef)query, &attrs);
            }
        }
        if (status == errSecSuccess && attrs && CFGetTypeID(attrs) == CFDictionaryGetTypeID()) {
            NSDictionary *dictionary = (__bridge NSDictionary *)attrs;
            id value = dictionary[(__bridge id)kSecAttrAccessGroup];
            if ([value isKindOfClass:NSString.class] && [value length] > 0) group = [value copy];
        }
        if (attrs) CFRelease(attrs);
        // A locked keychain or transient OS error must not cache failure forever.
        return group;
    }
}

static id VAccessGroup(id self, SEL sel) {
    return VSigningAccessGroup() ?: (VOriginalAccessGroup ? ((id (*)(id, SEL))VOriginalAccessGroup)(self, sel) : nil);
}
static id VSharedGroup(id self, SEL sel) {
    return VSigningAccessGroup() ?: (VOriginalSharedGroup ? ((id (*)(id, SEL))VOriginalSharedGroup)(self, sel) : nil);
}
static id VCoreAccessGroup(id self, SEL sel) {
    return VSigningAccessGroup() ?: (VOriginalCoreAccessGroup ? ((id (*)(id, SEL))VOriginalCoreAccessGroup)(self, sel) : nil);
}
static id VCoreSharedGroup(id self, SEL sel) {
    return VSigningAccessGroup() ?: (VOriginalCoreSharedGroup ? ((id (*)(id, SEL))VOriginalCoreSharedGroup)(self, sel) : nil);
}

static id VClientID(__unused id self, __unused SEL sel) { return VOfficialClientID; }
static id VClientName(__unused id self, __unused SEL sel) { return @"YouTube"; }

static void VSetObject(id object, const char *name, id value) {
    SEL selector = sel_registerName(name);
    Method method = class_getInstanceMethod(object_getClass(object), selector);
    if (VHasABI(method, "v", 3)) ((void (*)(id, SEL, id))objc_msgSend)(object, selector, value);
}

static id VSSOInit(id self, SEL sel, id client, id services) {
    self = ((id (*)(id, SEL, id, id))VOriginalSSOInit)(self, sel, client, services);
    // The embedded Google client still expects its registered client identity.
    // The OS-visible bundle ID, signing identity, sandbox and keychain stay distinct.
    VSetObject(self, "setShortAppName:", @"YouTube");
    VSetObject(self, "setApplicationIdentifier:", VOfficialClientID);
    VSetObject(self, "setApplicationScheme:", @"youtubevanced");
    return self;
}

static id VGroupContainer(id self, SEL sel, NSString *identifier) {
    BOOL googleGroup = [identifier isKindOfClass:NSString.class] &&
        ([identifier isEqualToString:@"group.com.google.YouTube"] ||
         [identifier isEqualToString:@"group.com.google.common"]);
    if (!googleGroup) {
        return VOriginalGroupContainer ? ((id (*)(id, SEL, id))VOriginalGroupContainer)(self, sel, identifier) : nil;
    }
    // These original app groups aren't granted to a personal signing identity.
    // Give each a separate private folder inside THIS application's container.
    NSData *bytes = [identifier dataUsingEncoding:NSUTF8StringEncoding];
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(bytes.bytes, (CC_LONG)bytes.length, digest);
    NSMutableString *component = [NSMutableString string];
    for (NSUInteger i = 0; i < sizeof(digest); ++i) [component appendFormat:@"%02x", digest[i]];
    NSURL *base = [[NSFileManager defaultManager] URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL *url = [[base URLByAppendingPathComponent:@"VancedAppGroups" isDirectory:YES] URLByAppendingPathComponent:component isDirectory:YES];
    NSError *error = nil;
    if (!url || ![[NSFileManager defaultManager] createDirectoryAtURL:url withIntermediateDirectories:YES attributes:nil error:&error]) return nil;
    return url;
}

static void VInstallIdentity(void) {
    // Only Google's client metadata getters use the original registered client.
    // NSBundle, OS registration and file access retain the standalone identity.
    VHook("YTVersionUtils", "appID", YES, 2, (IMP)VClientID, &VOriginalClientIDs[0]);
    VHook("GCKBUtils", "appIdentifier", YES, 2, (IMP)VClientID, &VOriginalClientIDs[1]);
    VHook("GPCDeviceInfo", "bundleId", YES, 2, (IMP)VClientID, &VOriginalClientIDs[2]);
    VHook("OGLPhenotypeFlagServiceImpl", "bundleId", NO, 2, (IMP)VClientID, &VOriginalClientIDs[3]);
    VHook("YTVersionUtils", "appName", YES, 2, (IMP)VClientName, &VOriginalClientNames[0]);
    VHook("OGLBundle", "shortAppName", YES, 2, (IMP)VClientName, &VOriginalClientNames[1]);
    VHook("GVROverlayView", "appName", YES, 2, (IMP)VClientName, &VOriginalClientNames[2]);
    VHook("SSOConfiguration", "initWithClientID:supportedAccountServices:", NO, 4, (IMP)VSSOInit, &VOriginalSSOInit);
    VHook("SSOKeychainHelper", "accessGroup", YES, 2, (IMP)VAccessGroup, &VOriginalAccessGroup);
    VHook("SSOKeychainHelper", "sharedAccessGroup", YES, 2, (IMP)VSharedGroup, &VOriginalSharedGroup);
    VHook("SSOKeychainCore", "accessGroup", YES, 2, (IMP)VCoreAccessGroup, &VOriginalCoreAccessGroup);
    VHook("SSOKeychainCore", "sharedAccessGroup", YES, 2, (IMP)VCoreSharedGroup, &VOriginalCoreSharedGroup);
    VHook("NSFileManager", "containerURLForSecurityApplicationGroupIdentifier:", NO, 3, (IMP)VGroupContainer, &VOriginalGroupContainer);
}

__attribute__((constructor)) static void VIdentityInit(void) {
    @autoreleasepool {
        // Applies only to this standalone application process.
        if (![NSBundle.mainBundle.bundleIdentifier.lowercaseString containsString:@"youtubevanced"]) return;
        [[NSUserDefaults standardUserDefaults] registerDefaults:@{
            @"YouPiPEnabled": @YES,
            @"NonBackgroundableKey": @YES
        }];
        VInstallIdentity();
        dispatch_async(dispatch_get_main_queue(), ^{
            VInstallIdentity();
            for (NSNumber *delay in @[@1, @3, @8]) {
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(delay.doubleValue * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{ VInstallIdentity(); });
            }
        });
    }
}
