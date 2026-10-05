#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>
#import <math.h>
#import <stdarg.h>
#import <stdlib.h>
#import <objc/message.h>
#import <objc/runtime.h>

static NSString * const kDiagnosticsKey = @"VancedDiagnosticsEnabled";
static NSString * const kRememberSpeedKey = @"VancedRememberPlaybackSpeed";
static NSString * const kLastSpeedKey = @"VancedLastPlaybackRate";
static NSString * const kRememberQualityKey = @"VancedRememberVideoQuality";
static NSString * const kLastQualityKey = @"VancedLastVideoQualityLabel";

static IMP gOriginalPlayerLoad = NULL;
static IMP gOriginalOverlaySetPlaybackRate = NULL;
static IMP gOriginalQualityOriginalSelection = NULL;
static IMP gOriginalQualityRedesignedSelection = NULL;

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
    IMP previous = method_getImplementation(method);
    const char *types = method_getTypeEncoding(method);
    if (class_addMethod(cls, selector, replacement, types)) {
        *original = previous;
    } else {
        Method ownMethod = class_getInstanceMethod(cls, selector);
        *original = method_setImplementation(ownMethod, replacement);
    }
    VLog(@"hooked %s %s", className, selectorName);
    return YES;
}

static id VSendId(id object, const char *selectorName) {
    if (!object) return nil;
    SEL selector = sel_registerName(selectorName);
    if (![object respondsToSelector:selector]) return nil;
    return ((id (*)(id, SEL))objc_msgSend)(object, selector);
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

static void VRememberQualityFromFormat(id format) {
    if (![[NSUserDefaults standardUserDefaults] boolForKey:kRememberQualityKey]) return;
    NSString *label = VSendId(format, "qualityLabel");
    if (![label isKindOfClass:[NSString class]] || label.length == 0) return;
    [[NSUserDefaults standardUserDefaults] setObject:label forKey:kLastQualityKey];
    VLog(@"remembered video quality %@", label);
}

static void VQualityOriginalSelection(id self, SEL _cmd, id video, id format) {
    VRememberQualityFromFormat(format);
    if (gOriginalQualityOriginalSelection) {
        ((void (*)(id, SEL, id, id))gOriginalQualityOriginalSelection)(self, _cmd, video, format);
    }
}

static void VQualityRedesignedSelection(id self, SEL _cmd, id video, id format) {
    VRememberQualityFromFormat(format);
    if (gOriginalQualityRedesignedSelection) {
        ((void (*)(id, SEL, id, id))gOriginalQualityRedesignedSelection)(self, _cmd, video, format);
    }
}

static NSInteger VResolutionFromLabel(NSString *label) {
    if (![label isKindOfClass:[NSString class]]) return NSNotFound;
    NSRange p = [label rangeOfString:@"p" options:NSCaseInsensitiveSearch];
    if (p.location == NSNotFound) return NSNotFound;
    NSString *prefix = [label substringToIndex:p.location];
    NSCharacterSet *nonDigits = [[NSCharacterSet decimalDigitCharacterSet] invertedSet];
    NSString *digits = [[prefix componentsSeparatedByCharactersInSet:nonDigits] componentsJoinedByString:@""];
    return digits.length ? digits.integerValue : NSNotFound;
}

static NSString *VBestAvailableQualityLabel(NSArray *formats, NSString *requested) {
    if (![formats isKindOfClass:[NSArray class]] || formats.count == 0) return nil;
    NSInteger requestedResolution = VResolutionFromLabel(requested);
    NSInteger bestDifference = NSIntegerMax;
    NSString *closest = nil;

    for (id format in formats) {
        NSString *label = VSendId(format, "qualityLabel");
        if (![label isKindOfClass:[NSString class]] || label.length == 0) continue;
        if ([label isEqualToString:requested]) return label;
        NSInteger resolution = VResolutionFromLabel(label);
        if (requestedResolution != NSNotFound && resolution != NSNotFound) {
            NSInteger difference = labs(resolution - requestedResolution);
            if (difference < bestDifference) {
                bestDifference = difference;
                closest = label;
            }
        }
    }
    return closest;
}

static void VApplyRememberedSpeed(id playerController) {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    if (![defaults boolForKey:kRememberSpeedKey]) return;
    if ([defaults objectForKey:kLastSpeedKey] == nil) return;
    double rate = [defaults doubleForKey:kLastSpeedKey];
    if (!isfinite(rate) || rate < 0.1 || rate > 8.0) return;

    id overlay = VSendId(playerController, "activeVideoPlayerOverlay");
    SEL setRateSelector = sel_registerName("setPlaybackRate:");
    if (!overlay || ![overlay respondsToSelector:setRateSelector]) return;
    ((void (*)(id, SEL, double))objc_msgSend)(overlay, setRateSelector, rate);
    VLog(@"restored playback rate %.2fx", rate);
}

static void VApplyRememberedQuality(id playerController) {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    if (![defaults boolForKey:kRememberQualityKey]) return;
    NSString *requested = [defaults stringForKey:kLastQualityKey];
    if (requested.length == 0) return;

    id activeVideo = VSendId(playerController, "activeVideo");
    NSArray *formats = VSendId(activeVideo, "selectableVideoFormats");
    NSString *qualityLabel = VBestAvailableQualityLabel(formats, requested);
    if (qualityLabel.length == 0) return;

    Class constraintClass = objc_getClass("MLQuickMenuVideoQualitySettingFormatConstraint");
    if (!constraintClass) return;
    id constraint = ((id (*)(id, SEL))objc_msgSend)(constraintClass, sel_registerName("alloc"));
    SEL initSelector = sel_registerName("initWithVideoQualitySetting:formatSelectionReason:qualityLabel:");
    if (!constraint || ![constraint respondsToSelector:initSelector]) return;
    constraint = ((id (*)(id, SEL, NSInteger, NSInteger, id))objc_msgSend)(
        constraint, initSelector, 3, 2, qualityLabel);

    SEL setConstraintSelector = sel_registerName("setVideoFormatConstraint:");
    if (constraint && activeVideo && [activeVideo respondsToSelector:setConstraintSelector]) {
        ((void (*)(id, SEL, id))objc_msgSend)(activeVideo, setConstraintSelector, constraint);
        VLog(@"restored video quality %@", qualityLabel);
    }
}

static void VPlayerLoad(id self, SEL _cmd, id transition, id playbackConfig) {
    if (gOriginalPlayerLoad) {
        ((void (*)(id, SEL, id, id))gOriginalPlayerLoad)(self, _cmd, transition, playbackConfig);
    }
    __weak id weakSelf = self;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(750 * NSEC_PER_MSEC)),
                   dispatch_get_main_queue(), ^{
        id strongSelf = weakSelf;
        if (!strongSelf) return;
        VApplyRememberedSpeed(strongSelf);
        VApplyRememberedQuality(strongSelf);
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
    VHookInstanceMethod("YTVideoQualitySwitchOriginalController",
                        "singleVideo:didSelectVideoFormat:",
                        (IMP)VQualityOriginalSelection,
                        &gOriginalQualityOriginalSelection);
    VHookInstanceMethod("YTVideoQualitySwitchRedesignedController",
                        "singleVideo:didSelectVideoFormat:",
                        (IMP)VQualityRedesignedSelection,
                        &gOriginalQualityRedesignedSelection);
}

__attribute__((constructor))
static void VancedCoreInitialize(void) {
    @autoreleasepool {
        NSString *bundleID = NSBundle.mainBundle.bundleIdentifier ?: @"";
        if (![bundleID.lowercaseString containsString:@"youtube"]) return;

        [[NSUserDefaults standardUserDefaults] registerDefaults:@{
            kDiagnosticsKey: @NO,
            kRememberSpeedKey: @YES,
            kRememberQualityKey: @YES
        }];

        dispatch_async(dispatch_get_main_queue(), ^{
            VInstallSafeCustomizationHooks();
            for (NSNumber *delay in @[@1, @3, @8, @20, @60]) {
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW,
                                             (int64_t)(delay.doubleValue * NSEC_PER_SEC)),
                               dispatch_get_main_queue(), ^{
                    VInstallSafeCustomizationHooks();
                });
            }
        });
    }
}
