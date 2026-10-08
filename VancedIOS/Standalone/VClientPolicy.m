#import "VClientPolicy.h"
#import <objc/message.h>
#import <objc/runtime.h>
#import <dispatch/dispatch.h>
#import <string.h>

// Verified against Apple's lookup for YouTube on 2026-10-08. Updated from that
// same official source after launch; this is a reported client version, not a
// replacement of the original 20.21.6 binary or its protocol implementation.
static NSString * const VVersionKey = @"VancedReportedYouTubeVersionV1";
static NSString * const VVersionDateKey = @"VancedReportedYouTubeVersionDateV1";
static IMP VOriginalProtoVersion;
static NSObject *VVersionLock;
static NSString *VVersion;

static BOOL VValidVersion(id value) {
    if (![value isKindOfClass:NSString.class] || [value length] > 24) return NO;
    return [value rangeOfString:@"^[0-9]{1,3}(\\.[0-9]{1,4}){1,3}$" options:NSRegularExpressionSearch].location != NSNotFound;
}

NSString *VReportedVersion(void) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        VVersionLock = [NSObject new];
        id saved = [NSUserDefaults.standardUserDefaults stringForKey:VVersionKey];
        VVersion = VValidVersion(saved) && [saved compare:@"21.40.5" options:NSNumericSearch] != NSOrderedAscending ? [saved copy] : @"21.40.5";
    });
    @synchronized (VVersionLock) { return VVersion; }
}

BOOL VAcceptVersionLookup(NSData *data) {
    if (!data.length || data.length > 131072) return NO;
    id root = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    if (![root isKindOfClass:NSDictionary.class] || ![root[@"results"] isKindOfClass:NSArray.class]) return NO;
    for (id item in root[@"results"]) {
        if (![item isKindOfClass:NSDictionary.class] || ![item[@"trackId"] isKindOfClass:NSNumber.class] ||
            [item[@"trackId"] unsignedLongLongValue] != 544007664ULL ||
            ![item[@"bundleId"] isEqual:@"com.google.ios.youtube"] || !VValidVersion(item[@"version"])) continue;
        VReportedVersion();
        @synchronized (VVersionLock) {
            if ([item[@"version"] compare:VVersion options:NSNumericSearch] == NSOrderedAscending) return NO;
            VVersion = [item[@"version"] copy];
            [NSUserDefaults.standardUserDefaults setObject:VVersion forKey:VVersionKey];
            [NSUserDefaults.standardUserDefaults setDouble:NSDate.timeIntervalSinceReferenceDate forKey:VVersionDateKey];
        }
        return YES;
    }
    return NO;
}

void VRefreshReportedVersion(void) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NSTimeInterval age = NSDate.timeIntervalSinceReferenceDate - [NSUserDefaults.standardUserDefaults doubleForKey:VVersionDateKey];
        if (age >= 0 && age < 86400) return;
        NSURLSessionConfiguration *config = NSURLSessionConfiguration.ephemeralSessionConfiguration;
        config.timeoutIntervalForRequest = 8;
        config.timeoutIntervalForResource = 12;
        NSURLSession *session = [NSURLSession sessionWithConfiguration:config];
        NSURL *url = [NSURL URLWithString:@"https://itunes.apple.com/lookup?id=544007664&country=us"];
        [[session dataTaskWithURL:url completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
            if (!error && [response isKindOfClass:NSHTTPURLResponse.class] && [(NSHTTPURLResponse *)response statusCode] == 200)
                VAcceptVersionLookup(data);
            [session finishTasksAndInvalidate];
        }] resume];
    });
}

static _Bool VYes(__unused id object, __unused SEL selector) { return 1; }
static _Bool VNo(__unused id object, __unused SEL selector) { return 0; }
static id VLatest(__unused id object, __unused SEL selector) { return VReportedVersion(); }
static Method VResolvedMethod(Class cls, SEL selector);
static id VProtoVersion(id object, SEL selector) {
    SEL name = @selector(clientName);
    Method method = VResolvedMethod(object_getClass(object), name);
    if (method && strcmp(method_getTypeEncoding(method), "i16@0:8") == 0 &&
        ((int (*)(id, SEL))objc_msgSend)(object, name) == 5) return VReportedVersion();
    return VOriginalProtoVersion ? ((id (*)(id, SEL))VOriginalProtoVersion)(object, selector) : nil;
}

static Method VResolvedMethod(Class cls, SEL selector) {
    Method method = class_getInstanceMethod(cls, selector);
    if (!method && cls && class_getProperty(cls, sel_getName(selector))) {
        // Only resolve a declared dynamic protobuf property. No invented
        // isPremium selector is installed on an unrelated identity object.
        Method resolver = class_getClassMethod(cls, @selector(resolveInstanceMethod:));
        if (resolver && strcmp(method_getTypeEncoding(resolver), "B24@0:8:16") == 0)
            ((BOOL (*)(id, SEL, SEL))objc_msgSend)(cls, @selector(resolveInstanceMethod:), selector);
        method = class_getInstanceMethod(cls, selector);
    }
    return method;
}

static void VReplace(const char *name, const char *selector, BOOL isClass,
                     const char *encoding, IMP replacement, IMP *original) {
    if (original && *original) return;
    Class cls = objc_getClass(name);
    if (isClass) cls = object_getClass(cls);
    SEL sel = sel_registerName(selector);
    Method method = VResolvedMethod(cls, sel);
    if (!method || strcmp(method_getTypeEncoding(method), encoding)) return;
    IMP previous = method_getImplementation(method);
    if (!class_addMethod(cls, sel, replacement, encoding)) previous = method_setImplementation(method, replacement);
    if (original) *original = previous;
}

void VInstallClientPolicy(void) {
    VReplace("YTVersionUtils", "appVersion", YES, "@16@0:8", (IMP)VLatest, NULL);
    VReplace("YTVersionUtils", "appVersionLong", YES, "@16@0:8", (IMP)VLatest, NULL);
    VReplace("YTIClientInfo", "clientVersion", NO, "@16@0:8", (IMP)VProtoVersion, &VOriginalProtoVersion);
    // Local Premium membership/branding and the requested feature gates.
    // These returns do not create a paid Google account or new media URLs.
    VReplace("YTITopbarMenuButtonRenderer", "hasUnlimitedEntitlement", NO, "B16@0:8", (IMP)VYes, NULL);
    VReplace("YTITopbarMenuButtonRenderer", "hasHasUnlimitedEntitlement", NO, "B16@0:8", (IMP)VYes, NULL);
    VReplace("YTHeaderLogoControllerImpl", "isPremiumLogo", NO, "B16@0:8", (IMP)VYes, NULL);
    VReplace("YTIPlayabilityStatus", "isPlayableInBackground", NO, "B16@0:8", (IMP)VYes, NULL);
    VReplace("YTIPlayabilityStatus", "isPlayableInPictureInPicture", NO, "B16@0:8", (IMP)VYes, NULL);
    VReplace("YTBackgroundabilityPolicyImpl", "isBackgroundableByUserSettings", NO, "B16@0:8", (IMP)VYes, NULL);
    VReplace("YTBackgroundabilityPolicyImpl", "isPlayableInPictureInPictureByUserSettings", NO, "B16@0:8", (IMP)VYes, NULL);
    VReplace("YTPlayerPIPController", "isEligibleForPictureInPicture", NO, "B16@0:8", (IMP)VYes, NULL);
    VReplace("YTHotConfig", "iosPlayerClientSharedConfigDefaultOffPremiumPip", NO, "B16@0:8", (IMP)VNo, NULL);
    VReplace("YTHotConfig", "premiumClientSharedConfigEnableNonMemberPremiumPlaybackCap", NO, "B16@0:8", (IMP)VNo, NULL);
}
