#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <mach-o/dyld.h>
#import <objc/runtime.h>

static NSString * const VIOProfileVersionKey = @"VancedIOSProfileVersion";
static NSString * const VIOProfileVersion = @"3";

static NSDictionary<NSString *, id> *VIOVancedDefaults(void) {
    return @{
        // YouMod playback / resilience.
        @"YouModEnablesBackgroundPlayback": @YES,
        @"YouModBlockUpgradeDialogs": @YES,
        @"YouModHideAreYouThereDialog": @YES,
        @"YouModDisableHints": @YES,
        @"YouModFixPlaybackIssues": @YES,

        // YouMod persists user changes to these settings. Zero means no forced
        // quality/speed on first launch while retaining persistent controls.
        @"YouModWifiQualityIndex": @0,
        @"YouModCellQualityIndex": @0,
        @"YouModLowPowerQualityIndex": @0,
        @"YouModAutoSpeedIndex": @0,

        // Vanced-like player conveniences.
        @"YouModTapToSeek": @YES,
        @"YouModAddExtraSpeed": @YES,
        @"YouModSkipBackwardEnabled": @YES,
        @"YouModSkipForwardEnabled": @YES,
        @"YouModRewindSeconds": @10,
        @"YouModForwardSeconds": @10,

        // Remove YouTube promo clutter that YouMod exposes as toggles.
        @"YouModHidePaidPromoOverlay": @YES,
        @"YouModHideSurveys": @YES,

        // SponsorBlock. YouMod owns segment fetching and category behavior.
        @"YouModSBEnabled": @YES,
        @"YouModSBShowButton": @YES,
        @"YouModSBShowNotifications": @YES,
        @"YouModSBSegmentsInPlayer": @YES,
        @"YouModSBSegmentsInFeed": @YES,
        @"YouModSBSegmentsInMiniPlayer": @YES,

        // YouPiP.
        @"YouPiPEnabled": @YES
    };
}

static BOOL VIOImageLoaded(NSString *needle) {
    const uint32_t count = _dyld_image_count();
    for (uint32_t index = 0; index < count; index++) {
        const char *name = _dyld_get_image_name(index);
        if (name == NULL) continue;

        NSString *path = [NSString stringWithUTF8String:name];
        if ([path rangeOfString:needle options:NSCaseInsensitiveSearch].location != NSNotFound) {
            return YES;
        }
    }
    return NO;
}

static NSDictionary<NSString *, NSNumber *> *VIORuntimeStatus(void) {
    return @{
        @"YouTubeHost": @(objc_getClass("YTAppDelegate") != Nil),
        @"YouMod": @(VIOImageLoaded(@"YouMod.dylib")),
        @"YTVideoOverlay": @(VIOImageLoaded(@"YTVideoOverlay.dylib")),
        @"YouPiP": @(VIOImageLoaded(@"YouPiP.dylib")),
        @"YTUHD": @(VIOImageLoaded(@"YTUHD.dylib")),
        @"ReturnYouTubeDislikes": @(VIOImageLoaded(@"YouTubeDislikesReturn.dylib")),
        @"VancedIOSCore": @(VIOImageLoaded(@"VancedIOSCore.dylib"))
    };
}

static void VIORegisterDefaults(void) {
    NSUserDefaults *defaults = NSUserDefaults.standardUserDefaults;
    [defaults registerDefaults:VIOVancedDefaults()];

    // Diagnostic marker only. Registered defaults do not overwrite explicit
    // choices later made in YouMod/YouPiP settings.
    [defaults setObject:VIOProfileVersion forKey:VIOProfileVersionKey];
}

static void VIOLogRuntimeStatus(void) {
    NSDictionary<NSString *, NSNumber *> *status = VIORuntimeStatus();

    NSMutableArray<NSString *> *missing = [NSMutableArray array];
    for (NSString *key in @[
        @"YouTubeHost",
        @"YouMod",
        @"YTVideoOverlay",
        @"YouPiP",
        @"YTUHD",
        @"ReturnYouTubeDislikes",
        @"VancedIOSCore"
    ]) {
        if (![status[key] boolValue]) {
            [missing addObject:key];
        }
    }

    NSLog(@"[VancedIOS] profile=%@ status=%@ missing=%@",
          VIOProfileVersion,
          status,
          missing);

    if (missing.count > 0) {
        [[NSUserDefaults standardUserDefaults]
            setObject:missing
               forKey:@"VancedIOSMissingRuntimeModules"];
    } else {
        [[NSUserDefaults standardUserDefaults]
            removeObjectForKey:@"VancedIOSMissingRuntimeModules"];
    }
}

%hook YTAppDelegate

- (BOOL)application:(UIApplication *)application
didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    VIORegisterDefaults();

    BOOL result = %orig(application, launchOptions);

    // Diagnostic only. Playback, lock-screen controls, background lifecycle
    // and PiP remain owned by YouTube plus the pinned feature tweaks.
    dispatch_async(dispatch_get_main_queue(), ^{
        VIOLogRuntimeStatus();
    });

    return result;
}

%end

%ctor {
    @autoreleasepool {
        VIORegisterDefaults();
        %init;
    }
}
