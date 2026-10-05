#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>
#import <math.h>
#import <stdarg.h>
#import <objc/message.h>
#import <objc/runtime.h>

static NSString * const kDiagnosticsKey = @"VancedDiagnosticsEnabled";
static NSString * const kRememberSpeedKey = @"VancedRememberPlaybackSpeed";
static NSString * const kLastSpeedKey = @"VancedLastPlaybackRate";

static IMP gOriginalPlayerLoad = NULL;
static IMP gOriginalOverlaySetPlaybackRate = NULL;

static void VLog(NSString *format, ...) {
    if (![[NSUserDefaults standardUserDefaults] boolForKey:kDiagnosticsKey]) return;
    va_list args;
    va_start(args, format);
    NSString *message = [[NSString alloc] initWithFormat:format arguments:args];
    va_end(args);
    NSLog(@"[VancedCore] %@", message);
}

static BOOL VHookInstanceMethod(const char *className,
                                const char *selectorName,
                                IMP replacement,
                                IMP *original) {
    if (*original != NULL) return YES;
    Class cls = objc_getClass(className);
    if (!cls) {
        VLog(@"class unavailable: %s", className);
        return NO;
    }
    SEL selector = sel_registerName(selectorName);
    Method method = class_getInstanceMethod(cls, selector);
    if (!method) {
        VLog(@"selector unavailable: %s %s", className, selectorName);
        return NO;
    }
    *original = method_setImplementation(method, replacement);
    VLog(@"hooked %s %s", className, selectorName);
    return YES;
}

static void VOverlaySetPlaybackRate(id self, SEL _cmd, double rate) {
    if ([[NSUserDefaults standardUserDefaults] boolForKey:kRememberSpeedKey] &&
        isfinite(rate) && rate >= 0.1 && rate <= 8.0) {
        [[NSUserDefaults standardUserDefaults] setDouble:rate forKey:kLastSpeedKey];
    }
    if (gOriginalOverlaySetPlaybackRate) {
        ((void (*)(id, SEL, double))gOriginalOverlaySetPlaybackRate)(self, _cmd, rate);
    }
}

static void VApplyRememberedSpeed(id playerController) {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    if (![defaults boolForKey:kRememberSpeedKey]) return;
    if ([defaults objectForKey:kLastSpeedKey] == nil) return;

    double rate = [defaults doubleForKey:kLastSpeedKey];
    if (!isfinite(rate) || rate < 0.1 || rate > 8.0) return;

    SEL overlaySelector = sel_registerName("activeVideoPlayerOverlay");
    if (![playerController respondsToSelector:overlaySelector]) return;
    id overlay = ((id (*)(id, SEL))objc_msgSend)(playerController, overlaySelector);
    if (!overlay) return;

    SEL setRateSelector = sel_registerName("setPlaybackRate:");
    if (![overlay respondsToSelector:setRateSelector]) return;
    ((void (*)(id, SEL, double))objc_msgSend)(overlay, setRateSelector, rate);
    VLog(@"restored playback rate %.2fx", rate);
}

static void VPlayerLoad(id self, SEL _cmd, id transition, id playbackConfig) {
    if (gOriginalPlayerLoad) {
        ((void (*)(id, SEL, id, id))gOriginalPlayerLoad)(self, _cmd, transition, playbackConfig);
    }
    __weak id weakSelf = self;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(750 * NSEC_PER_MSEC)),
                   dispatch_get_main_queue(), ^{
        id strongSelf = weakSelf;
        if (strongSelf) VApplyRememberedSpeed(strongSelf);
    });
}

static void VInstallSafeCustomizationHooks(void) {
    VHookInstanceMethod("YTMainAppVideoPlayerOverlayViewController",
                        "setPlaybackRate:",
                        (IMP)VOverlaySetPlaybackRate,
                        &gOriginalOverlaySetPlaybackRate);
    VHookInstanceMethod("YTPlayerViewController",
                        "loadWithPlayerTransition:playbackConfig:",
                        (IMP)VPlayerLoad,
                        &gOriginalPlayerLoad);
}

__attribute__((constructor))
static void VancedCoreInitialize(void) {
    @autoreleasepool {
        NSString *bundleID = NSBundle.mainBundle.bundleIdentifier ?: @"";
        if (![bundleID.lowercaseString containsString:@"youtube"]) return;

        [[NSUserDefaults standardUserDefaults] registerDefaults:@{
            kDiagnosticsKey: @NO,
            kRememberSpeedKey: @YES
        }];

        dispatch_async(dispatch_get_main_queue(), ^{
            VInstallSafeCustomizationHooks();
            for (NSNumber *delay in @[@1, @3, @8]) {
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW,
                                             (int64_t)(delay.doubleValue * NSEC_PER_SEC)),
                               dispatch_get_main_queue(), ^{
                    VInstallSafeCustomizationHooks();
                });
            }
        });
    }
}
