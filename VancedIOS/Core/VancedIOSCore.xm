#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

static NSString * const VIOProfileVersionKey = @"VancedIOSProfileVersion";
static NSString * const VIOProfileVersion = @"1";

static NSDictionary<NSString *, id> *VIOVancedDefaults(void) {
    return @{
        // YouMod: background playback.
        @"YouModEnablesBackgroundPlayback": @YES,

        // YouMod: SponsorBlock defaults. YouMod itself owns fetching/skipping;
        // these keys only choose the Vanced-style out-of-box profile.
        @"YouModSBEnabled": @YES,
        @"YouModSBShowButton": @YES,
        @"YouModSBShowNotifications": @YES,
        @"YouModSBSegmentsInPlayer": @YES,
        @"YouModSBSegmentsInFeed": @YES,
        @"YouModSBSegmentsInMiniPlayer": @YES,

        // YouPiP.
        @"YouPiPEnabled": @YES,

        // Avoid forced upgrade nags in sideloaded builds where YouMod supports it.
        @"YouModBlockUpgradeDialogs": @YES,

        // Vanced-like uninterrupted playback.
        @"YouModHideAreYouThereDialog": @YES
    };
}

static void VIORegisterDefaults(void) {
    NSUserDefaults *defaults = NSUserDefaults.standardUserDefaults;
    [defaults registerDefaults:VIOVancedDefaults()];

    // Marker is diagnostic only. We deliberately do not write feature values
    // here, so user selections always win over the registered defaults.
    [defaults setObject:VIOProfileVersion forKey:VIOProfileVersionKey];
}

static NSDictionary<NSString *, NSNumber *> *VIORuntimeStatus(void) {
    return @{
        @"YouMod": @(objc_getClass("YouModPrefsManager") != Nil ||
                     objc_getClass("SBSettingsViewController") != Nil),
        @"YouPiP": @(objc_getClass("AVPictureInPictureController") != Nil),
        @"YouTubeHost": @(objc_getClass("YTAppDelegate") != Nil)
    };
}

%hook YTAppDelegate

- (BOOL)application:(UIApplication *)application
didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    VIORegisterDefaults();

    BOOL result = %orig(application, launchOptions);

    NSDictionary *status = VIORuntimeStatus();
    NSLog(@"[VancedIOS] profile=%@ host=%@ youmod=%@ pip=%@",
          VIOProfileVersion,
          status[@"YouTubeHost"],
          status[@"YouMod"],
          status[@"YouPiP"]);

    return result;
}

%end

%ctor {
    @autoreleasepool {
        VIORegisterDefaults();
        %init;
    }
}
