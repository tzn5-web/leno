#import <UIKit/UIKit.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <math.h>
#import <YouTubeHeader/YTSettingsSectionItem.h>
#import <YouTubeHeader/YTSettingsSectionItemManager.h>
#import <YouTubeHeader/YTSettingsViewController.h>
#import <YouTubeHeader/YTSettingsGroupData.h>
#import "VGuestEntry.h"
#import "VGuestStore.h"
#import "VGuestUI.h"

static __weak id VIdentityProvider;
static NSDictionary *VActiveRecord;
static CFTimeInterval VLastFlush;
static const NSUInteger VGuestSection = 900001;

static id VGetObject(id object, NSString *name) {
    SEL selector = NSSelectorFromString(name);
    Method method = class_getInstanceMethod(object_getClass(object), selector);
    if (!method && [object respondsToSelector:selector]) method = class_getInstanceMethod(object_getClass(object), selector);
    if (!method || method_getNumberOfArguments(method) != 2) return nil;
    char *type = method_copyReturnType(method);
    BOOL valid = type && type[0] == '@';
    free(type);
    return valid ? ((id (*)(id, SEL))objc_msgSend)(object, selector) : nil;
}

static BOOL VNativeBool(id object, SEL selector) {
    Method method = class_getInstanceMethod(object_getClass(object), selector);
    if (!method || strcmp(method_getTypeEncoding(method), "B16@0:8") != 0) return NO;
    return ((BOOL (*)(id, SEL))objc_msgSend)(object, selector);
}

static BOOL VRecordingEnabled(void) {
    return ![NSUserDefaults.standardUserDefaults boolForKey:@"VancedGuestHistoryPaused"] &&
           !VNativeBool(VIdentityProvider, @selector(isSignedIn)) &&
           !VNativeBool(VIdentityProvider, @selector(isIncognitoActive));
}

static void VRecordContent(id content) {
    id data = VGetObject(content, @"playbackData");
    id video = VGetObject(data, @"video");
    id details = VGetObject(video, @"videoDetails");
    id videoID = VGetObject(content, @"videoId") ?: VGetObject(video, @"ID");
    if (![videoID isKindOfClass:NSString.class]) return;
    NSMutableDictionary *record = [@{@"id":videoID} mutableCopy];
    for (NSString *key in @[@"title", @"author", @"channelId"]) {
        id value = VGetObject(details, key);
        if ([value isKindOfClass:NSString.class]) record[[key isEqual:@"channelId"] ? @"channel" : key] = value;
    }
    VActiveRecord = record;
    VGuestSetCurrentRecord(record);
    if (VRecordingEnabled()) [VGuestStore.shared recordVideo:record];
}

%hook YTInlineIdentityStrategy
- (void)firstTimeSignInWithTransaction:(id)transaction {
    // Complete the real native guest transaction without presenting OAuth UI.
    if (strcmp(method_getTypeEncoding(class_getInstanceMethod(object_getClass(self), _cmd)), "v24@0:8@16") == 0 &&
        VGuestCompleteFirstTimeTransaction(self, transaction)) return;
    %orig;
}
%end

%hook YTUserDefaults
- (BOOL)shouldSuppressFrictionlessSignIn { return YES; }
%end

%hook YTIdentityController
- (id)nonNilActiveIdentity { VIdentityProvider = self; return %orig; }
- (BOOL)isSignedIn { VIdentityProvider = self; return %orig; }
%end

%hook YTPlayerViewController
- (void)playbackController:(id)controller didActivateNewPlaybackWithContentVideo:(id)video {
    %orig;
    VRecordContent(video);
}
- (void)potentiallyMutatedSingleVideo:(id)video currentVideoTimeDidChange:(id)time {
    %orig;
    NSString *videoID = VGetObject(video, @"videoId");
    if (![videoID isEqual:VActiveRecord[@"id"]]) return;
    SEL getter = @selector(time);
    Method method = class_getInstanceMethod(object_getClass(time), getter);
    if (!method || strcmp(method_getTypeEncoding(method), "d16@0:8") != 0) return;
    double position = ((double (*)(id, SEL))objc_msgSend)(time, getter);
    if (!isfinite(position) || position < 0) return;
    NSMutableDictionary *record = VActiveRecord.mutableCopy;
    record[@"position"] = @(position);
    VActiveRecord = record;
    VGuestSetCurrentRecord(record);
    if (VRecordingEnabled()) [VGuestStore.shared updateVideo:videoID position:position];
    CFTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
    if (now - VLastFlush > 15) { [VGuestStore.shared flush]; VLastFlush = now; }
}
%end

%hook YTAppViewControllerImpl
- (void)viewDidLoad { VGuestSetAppController(self); %orig; }
%end

%hook YTMainAppControlsOverlayView
- (UIImage *)buttonImage:(NSString *)tweakId {
    return [tweakId isEqual:@"VancedGuest"] ? [UIImage systemImageNamed:@"clock.arrow.circlepath"] : %orig;
}
%new(v@:@)
- (void)didPressVancedGuest:(id)sender { VGuestPresentLibrary(); }
%end

%hook YTInlinePlayerBarContainerView
- (UIImage *)buttonImage:(NSString *)tweakId {
    return [tweakId isEqual:@"VancedGuest"] ? [UIImage systemImageNamed:@"clock.arrow.circlepath"] : %orig;
}
%new(v@:@)
- (void)didPressVancedGuest:(id)sender { VGuestPresentLibrary(); }
%end

%hook YTAppSettingsPresentationData
+ (NSArray *)settingsCategoryOrder {
    NSMutableArray *order = [%orig mutableCopy];
    if (![order containsObject:@(VGuestSection)]) [order addObject:@(VGuestSection)];
    return order;
}
%end

%hook YTSettingsGroupData
- (NSArray *)orderedCategories {
    NSArray *categories = %orig;
    if (self.type != 1) return categories;
    NSMutableArray *order = categories.mutableCopy;
    if (![order containsObject:@(VGuestSection)]) [order insertObject:@(VGuestSection) atIndex:0];
    return order;
}
%end

%hook YTSettingsSectionItemManager
- (void)updateSectionForCategory:(NSUInteger)category withEntry:(id)entry {
    if (category != VGuestSection) { %orig; return; }
    YTSettingsSectionItem *item = [%c(YTSettingsSectionItem) itemWithTitle:@"Deschide Biblioteca Guest"
        titleDescription:@"Istoric, favorite și liste salvate pe acest telefon."
        accessibilityIdentifier:@"VancedGuestLibrary" detailTextBlock:nil
        selectBlock:^BOOL(id cell, NSUInteger index) { VGuestPresentLibrary(); return YES; }];
    id delegate;
    @try { delegate = [self valueForKey:@"_dataDelegate"]; } @catch (NSException *exception) { return; }
    SEL selector = NSSelectorFromString(@"setSectionItems:forCategory:title:icon:titleDescription:headerHidden:");
    Method method = class_getInstanceMethod(object_getClass(delegate), selector);
    if (item && method && strcmp(method_getTypeEncoding(method), "v60@0:8@16Q24@32@40@48B56") == 0) {
        ((void (*)(id,SEL,id,NSUInteger,id,id,id,BOOL))objc_msgSend)(delegate,selector,@[item],category,@"Biblioteca Guest",nil,nil,NO);
    }
}
%end

%ctor {
    if (![NSBundle.mainBundle.bundleIdentifier.lowercaseString containsString:@"youtubevanced"]) return;
    [NSUserDefaults.standardUserDefaults registerDefaults:@{@"VancedGuestButtonEnabled":@YES}];
    // YTVideoOverlay is a required dylib dependency, so its register method and
    // metadata dictionary exist before this constructor executes.
    id manager = objc_getClass("YTSettingsSectionItemManager");
    SEL registerSelector = NSSelectorFromString(@"registerTweak:metadata:");
    if ([manager respondsToSelector:registerSelector]) {
        ((void (*)(id, SEL, id, id))objc_msgSend)(manager, registerSelector, @"VancedGuest",
            @{@"accessibilityLabel":@"Biblioteca Guest", @"selector":@"didPressVancedGuest:", @"toggle":@"VancedGuestButtonEnabled"});
    }
    %init;
    for (NSNotificationName name in @[UIApplicationDidEnterBackgroundNotification, UIApplicationWillTerminateNotification]) {
        [NSNotificationCenter.defaultCenter addObserverForName:name object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) { [VGuestStore.shared flush]; }];
    }
}
