#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>
#import <objc/message.h>
#import <objc/runtime.h>

static NSString * const kHideShortsTabKey = @"VancedHideShortsTab";
static IMP gOriginalPivotSetRenderer = NULL;

static BOOL VShortsHook(const char *className, const char *selectorName, IMP replacement, IMP *original) {
    if (*original != NULL) return YES;
    Class cls = objc_getClass(className);
    if (!cls) return NO;
    SEL selector = sel_registerName(selectorName);
    Method method = class_getInstanceMethod(cls, selector);
    if (!method) return NO;
    IMP previous = method_getImplementation(method);
    const char *types = method_getTypeEncoding(method);
    if (class_addMethod(cls, selector, replacement, types)) {
        *original = previous;
    } else {
        *original = method_setImplementation(class_getInstanceMethod(cls, selector), replacement);
    }
    return YES;
}

static id VShortsSendId(id object, const char *selectorName) {
    if (!object) return nil;
    SEL selector = sel_registerName(selectorName);
    if (![object respondsToSelector:selector]) return nil;
    return ((id (*)(id, SEL))objc_msgSend)(object, selector);
}

static void VShortsPivotSetRenderer(id self, SEL _cmd, id renderer) {
    if ([[NSUserDefaults standardUserDefaults] boolForKey:kHideShortsTabKey]) {
        id items = VShortsSendId(renderer, "itemsArray");
        if ([items isKindOfClass:[NSMutableArray class]]) {
            NSMutableArray *mutableItems = items;
            NSIndexSet *indexes = [mutableItems indexesOfObjectsPassingTest:^BOOL(id item, NSUInteger idx, BOOL *stop) {
                (void)idx;
                (void)stop;
                id itemRenderer = VShortsSendId(item, "pivotBarItemRenderer");
                NSString *identifier = VShortsSendId(itemRenderer, "pivotIdentifier");
                return [identifier isKindOfClass:[NSString class]] && [identifier isEqualToString:@"FEshorts"];
            }];
            if (indexes.count > 0) [mutableItems removeObjectsAtIndexes:indexes];
        }
    }
    if (gOriginalPivotSetRenderer) {
        ((void (*)(id, SEL, id))gOriginalPivotSetRenderer)(self, _cmd, renderer);
    }
}

static void VShortsInstallHooks(void) {
    VShortsHook("YTPivotBarView",
                "setRenderer:",
                (IMP)VShortsPivotSetRenderer,
                &gOriginalPivotSetRenderer);
}

__attribute__((constructor))
static void VancedShortsUIInitialize(void) {
    @autoreleasepool {
        NSString *bundleID = NSBundle.mainBundle.bundleIdentifier ?: @"";
        if (![bundleID.lowercaseString containsString:@"youtube"]) return;
        [[NSUserDefaults standardUserDefaults] registerDefaults:@{kHideShortsTabKey: @NO}];
        dispatch_async(dispatch_get_main_queue(), ^{
            VShortsInstallHooks();
            for (NSNumber *delay in @[@1, @3, @8, @20, @60]) {
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW,
                                             (int64_t)(delay.doubleValue * NSEC_PER_SEC)),
                               dispatch_get_main_queue(), ^{ VShortsInstallHooks(); });
            }
        });
    }
}
