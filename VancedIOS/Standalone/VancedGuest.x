#import <UIKit/UIKit.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <math.h>
#import <time.h>
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

static dispatch_queue_t VStoreQueue(void) {
    static dispatch_queue_t queue;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ queue = dispatch_queue_create("ro.ion.youtubevanced.guest-store", DISPATCH_QUEUE_SERIAL); });
    return queue;
}

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
    return VIdentityProvider != nil &&
           ![NSUserDefaults.standardUserDefaults boolForKey:@"VancedGuestHistoryPaused"] &&
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
    NSDictionary *snapshot = record.copy;
    dispatch_async(dispatch_get_main_queue(), ^{
        VActiveRecord = snapshot;
        VGuestSetCurrentRecord(snapshot);
        if (VRecordingEnabled()) dispatch_async(VStoreQueue(), ^{ [VGuestStore.shared recordVideo:snapshot]; });
    });
}

static void VUpdatePosition(NSString *videoID, double position) {
    if (!isfinite(position) || position < 0) return;
    dispatch_async(dispatch_get_main_queue(), ^{
        if (![videoID isEqual:VActiveRecord[@"id"]]) return;
        NSMutableDictionary *record = VActiveRecord.mutableCopy;
        record[@"position"] = @(position);
        VActiveRecord = record;
        VGuestSetCurrentRecord(record);
        if (VRecordingEnabled()) dispatch_async(VStoreQueue(), ^{
            [VGuestStore.shared updateVideo:videoID position:position];
            CFTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
            if (now - VLastFlush > 15) { [VGuestStore.shared flush]; VLastFlush = now; }
        });
    });
}

%hook YTFirstTimeSignInController
- (void)launchViewController {
    // Native launchSignIn initialized the transaction; suppress only its UI.
    if (VGuestCompleteWithoutPresentation(self)) return;
    %orig;
}
%end

%hook YTUserDefaults
- (BOOL)shouldSuppressFrictionlessSignIn { return YES; }
- (BOOL)watchHistoryPaused { return YES; }
%end

%hook YTRetroactiveSignInController
- (BOOL)shouldShowRetroactiveSignIn { return NO; }
%end

%hook YTIdentityController
- (void)launchFirstTimeSignInWithSuccessBlock:(id)success errorBlock:(id)error cancelBlock:(id)cancel {
    VGuestRunSignIn(NO, ^{ %orig; });
}
- (void)requestSignInWithSuccessBlock:(id)success errorBlock:(id)error cancelBlock:(id)cancel {
    VGuestRunSignIn(YES, ^{ %orig; });
}
- (void)requestSignInWithSuccessBlock:(id)success errorBlock:(id)error cancelBlock:(id)cancel fromView:(id)view {
    VGuestRunSignIn(YES, ^{ %orig; });
}
- (id)nonNilActiveIdentity {
    VIdentityProvider = self;
    return %orig;
}
- (BOOL)isSignedIn {
    VIdentityProvider = self;
    BOOL signedIn = %orig;
    if (!VNativeBool(self, @selector(isIncognitoActive)))
        VGuestConfigureNativeHistory(VGetObject(self, @"userDefaults"));
    return signedIn;
}
%end

%hook YTIdentityTransactionCoalescer
- (id)transactionForRequestWithSuccessBlock:(id)success errorBlock:(id)error cancelBlock:(id)cancel {
    id transaction = %orig;
    VGuestTagSignInTransaction(transaction);
    return transaction;
}
%end

%hook YTPlayerViewController
- (void)playbackController:(id)controller didActivateNewPlaybackWithContentVideo:(id)video {
    %orig;
    VRecordContent(video);
}
- (void)potentiallyMutatedSingleVideo:(id)video currentVideoTimeDidChange:(id)time {
    %orig;
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 ||
        !VGuestAcceptProgress((unsigned long long)now.tv_sec * 1000000000ULL + now.tv_nsec)) return;
    NSString *videoID = VGetObject(video, @"videoId");
    SEL getter = @selector(time);
    Method method = class_getInstanceMethod(object_getClass(time), getter);
    if (!method || strcmp(method_getTypeEncoding(method), "d16@0:8") != 0) return;
    double position = ((double (*)(id, SEL))objc_msgSend)(time, getter);
    VUpdatePosition(videoID, position);
}
%end

%hook YTAppViewControllerImpl
- (void)viewDidLoad {
    VGuestSetAppController(self);
    %orig;
}
%end

%hook YTMainAppControlsOverlayView
- (UIImage *)buttonImage:(NSString *)tweakId {
    if ([tweakId isEqual:@"VancedGuest"]) return [UIImage systemImageNamed:@"clock.arrow.circlepath"];
    return %orig;
}
%new(v@:@)
- (void)didPressVancedGuest:(id)sender { VGuestPresentLibrary(); }
%end

%hook YTInlinePlayerBarContainerView
- (UIImage *)buttonImage:(NSString *)tweakId {
    if ([tweakId isEqual:@"VancedGuest"]) return [UIImage systemImageNamed:@"clock.arrow.circlepath"];
    return %orig;
}
%new(v@:@)
- (void)didPressVancedGuest:(id)sender { VGuestPresentLibrary(); }
%end

%hook YTAppSettingsPresentationData
+ (NSArray *)settingsCategoryOrder {
    NSArray *original = %orig;
    NSMutableArray *order = original.mutableCopy;
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
    if (category != VGuestSection) {
        %orig;
        return;
    }
    YTSettingsSectionItem *item = [%c(YTSettingsSectionItem) itemWithTitle:@"Deschide Biblioteca locală"
        titleDescription:@"Istoric, favorite și liste salvate pe acest telefon."
        accessibilityIdentifier:@"VancedGuestLibrary" detailTextBlock:nil
        selectBlock:^BOOL(id cell, NSUInteger index) { VGuestPresentLibrary(); return YES; }];
    id delegate;
    @try { delegate = [self valueForKey:@"_dataDelegate"]; } @catch (NSException *exception) { return; }
    SEL selector = NSSelectorFromString(@"setSectionItems:forCategory:title:icon:titleDescription:headerHidden:");
    Method method = class_getInstanceMethod(object_getClass(delegate), selector);
    if (item && method && strcmp(method_getTypeEncoding(method), "v60@0:8@16Q24@32@40@48B56") == 0) {
        ((void (*)(id,SEL,id,NSUInteger,id,id,id,BOOL))objc_msgSend)(delegate,selector,@[item],category,@"Biblioteca locală",nil,nil,NO);
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
        @{@"accessibilityLabel":@"Biblioteca locală", @"selector":@"didPressVancedGuest:", @"toggle":@"VancedGuestButtonEnabled"});
    }
    %init;
    for (NSNotificationName name in @[UIApplicationDidEnterBackgroundNotification, UIApplicationWillTerminateNotification]) {
        [NSNotificationCenter.defaultCenter addObserverForName:name object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
            if ([note.name isEqual:UIApplicationWillTerminateNotification]) {
                dispatch_sync(VStoreQueue(), ^{ [VGuestStore.shared flush]; });
                return;
            }
            UIBackgroundTaskIdentifier task = [UIApplication.sharedApplication beginBackgroundTaskWithExpirationHandler:nil];
            dispatch_async(VStoreQueue(), ^{
                [VGuestStore.shared flush];
                dispatch_async(dispatch_get_main_queue(), ^{
                    if (task != UIBackgroundTaskInvalid) [UIApplication.sharedApplication endBackgroundTask:task];
                });
            });
        }];
    }
}
