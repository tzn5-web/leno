#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <dispatch/dispatch.h>
#import <objc/message.h>
#import <objc/runtime.h>

static const NSUInteger kVancedSettingsCategory = 987654;
static NSString * const kVancedSettingsAccessibilityID = @"VancedIOSSettingsItem";
static NSString * const kRememberSpeedKey = @"VancedRememberPlaybackSpeed";
static NSString * const kRememberQualityKey = @"VancedRememberVideoQuality";
static NSString * const kHideShortsKey = @"VancedHideShortsInFeeds";
static NSString * const kSponsorBlockEnabledKey = @"VancedSponsorBlockEnabled";
static NSString * const kRYDEnabledKey = @"VancedReturnYouTubeDislikeEnabled";
static NSString * const kHideShortsTabKey = @"VancedHideShortsTab";

static IMP gOriginalSettingsCategoryOrder = NULL;
static IMP gOriginalUpdateSection = NULL;

static BOOL VSettingsHookInstanceMethod(const char *className,
                                        const char *selectorName,
                                        IMP replacement,
                                        IMP *original) {
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

static BOOL VSettingsHookClassMethod(const char *className,
                                     const char *selectorName,
                                     IMP replacement,
                                     IMP *original) {
    if (*original != NULL) return YES;
    Class cls = objc_getClass(className);
    if (!cls) return NO;
    Class meta = object_getClass(cls);
    SEL selector = sel_registerName(selectorName);
    Method method = class_getClassMethod(cls, selector);
    if (!method) return NO;
    IMP previous = method_getImplementation(method);
    const char *types = method_getTypeEncoding(method);
    if (class_addMethod(meta, selector, replacement, types)) {
        *original = previous;
    } else {
        *original = method_setImplementation(class_getClassMethod(cls, selector), replacement);
    }
    return YES;
}

static id VSwitchItem(NSString *title, NSString *description, NSString *key) {
    Class itemClass = objc_getClass("YTSettingsSectionItem");
    if (!itemClass) return nil;
    SEL selector = sel_registerName("switchItemWithTitle:titleDescription:accessibilityIdentifier:switchOn:switchBlock:settingItemId:");
    if (![itemClass respondsToSelector:selector]) return nil;

    BOOL current = [[NSUserDefaults standardUserDefaults] boolForKey:key];
    BOOL (^block)(id, BOOL) = ^BOOL(id cell, BOOL enabled) {
        (void)cell;
        [[NSUserDefaults standardUserDefaults] setBool:enabled forKey:key];
        if ([key isEqualToString:kHideShortsTabKey]) {
            Class refreshClass = objc_getClass("YTHeaderContentComboViewController");
            SEL refreshSelector = sel_registerName("refreshPivotBar");
            if (refreshClass) {
                id refreshObject = ((id (*)(id, SEL))objc_msgSend)(refreshClass, sel_registerName("alloc"));
                refreshObject = ((id (*)(id, SEL))objc_msgSend)(refreshObject, sel_registerName("init"));
                if ([refreshObject respondsToSelector:refreshSelector]) {
                    ((void (*)(id, SEL))objc_msgSend)(refreshObject, refreshSelector);
                }
            }
        }
        return YES;
    };

    return ((id (*)(id, SEL, id, id, id, BOOL, id, NSInteger))objc_msgSend)(
        itemClass, selector, title, description, kVancedSettingsAccessibilityID, current, block, 0);
}

static NSArray *VSettingsCategoryOrder(id self, SEL _cmd) {
    NSArray *original = gOriginalSettingsCategoryOrder
        ? ((id (*)(id, SEL))gOriginalSettingsCategoryOrder)(self, _cmd)
        : @[];
    NSMutableArray *order = [original mutableCopy] ?: [NSMutableArray array];
    NSNumber *category = @(kVancedSettingsCategory);
    if (![order containsObject:category]) {
        NSUInteger index = [order indexOfObject:@(1)];
        if (index == NSNotFound || index + 1 > order.count) {
            [order addObject:category];
        } else {
            [order insertObject:category atIndex:index + 1];
        }
    }
    return order;
}

static id VSettingsDelegate(id manager) {
    @try {
        return [manager valueForKey:@"_settingsViewControllerDelegate"];
    } @catch (NSException *exception) {
        (void)exception;
        return nil;
    }
}

static void VRenderVancedSettings(id manager) {
    id settingsVC = VSettingsDelegate(manager);
    if (!settingsVC) return;

    NSMutableArray *items = [NSMutableArray array];
    id speed = VSwitchItem(@"Remember playback speed",
                           @"Use the last playback speed for the next video.",
                           kRememberSpeedKey);
    id quality = VSwitchItem(@"Remember video quality",
                             @"Use the last selected quality when an equivalent format is available.",
                             kRememberQualityKey);
    id hideShorts = VSwitchItem(@"Hide Shorts in feeds",
                                @"Hide Shorts shelves and Shorts cells outside watch history.",
                                kHideShortsKey);
    if (speed) [items addObject:speed];
    if (quality) [items addObject:quality];
    id sponsorBlock = VSwitchItem(@"SponsorBlock",
                                  @"Automatically skip sponsor, self-promotion, interaction, intro and outro segments.",
                                  kSponsorBlockEnabledKey);
    id hideShortsTab = VSwitchItem(@"Hide Shorts tab",
                                   @"Remove the Shorts tab from the native YouTube tab bar.",
                                   kHideShortsTabKey);
    if (hideShorts) [items addObject:hideShorts];
    if (hideShortsTab) [items addObject:hideShortsTab];
    id ryd = VSwitchItem(@"Return YouTube Dislike",
                         @"Show dislike counts using the Return YouTube Dislike public API.",
                         kRYDEnabledKey);
    if (sponsorBlock) [items addObject:sponsorBlock];
    if (ryd) [items addObject:ryd];
    if (items.count == 0) return;

    SEL newSelector = sel_registerName("setSectionItems:forCategory:title:icon:titleDescription:headerHidden:");
    SEL oldSelector = sel_registerName("setSectionItems:forCategory:title:titleDescription:headerHidden:");

    if ([settingsVC respondsToSelector:newSelector]) {
        ((void (*)(id, SEL, id, NSUInteger, id, id, id, BOOL))objc_msgSend)(
            settingsVC, newSelector, items, kVancedSettingsCategory, @"Vanced", nil, nil, NO);
    } else if ([settingsVC respondsToSelector:oldSelector]) {
        ((void (*)(id, SEL, id, NSUInteger, id, id, BOOL))objc_msgSend)(
            settingsVC, oldSelector, items, kVancedSettingsCategory, @"Vanced", nil, NO);
    }
}

static void VUpdateSectionForCategory(id self, SEL _cmd, NSUInteger category, id entry) {
    if (category == kVancedSettingsCategory) {
        VRenderVancedSettings(self);
        return;
    }
    if (gOriginalUpdateSection) {
        ((void (*)(id, SEL, NSUInteger, id))gOriginalUpdateSection)(self, _cmd, category, entry);
    }
}

static void VInstallSettingsHooks(void) {
    VSettingsHookClassMethod("YTAppSettingsPresentationData",
                             "settingsCategoryOrder",
                             (IMP)VSettingsCategoryOrder,
                             &gOriginalSettingsCategoryOrder);
    VSettingsHookInstanceMethod("YTSettingsSectionItemManager",
                                "updateSectionForCategory:withEntry:",
                                (IMP)VUpdateSectionForCategory,
                                &gOriginalUpdateSection);
}

__attribute__((constructor))
static void VancedSettingsInitialize(void) {
    @autoreleasepool {
        NSString *bundleID = NSBundle.mainBundle.bundleIdentifier ?: @"";
        if (![bundleID.lowercaseString containsString:@"youtube"]) return;
        dispatch_async(dispatch_get_main_queue(), ^{
            VInstallSettingsHooks();
            for (NSNumber *delay in @[@1, @3, @8, @20, @60]) {
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW,
                                             (int64_t)(delay.doubleValue * NSEC_PER_SEC)),
                               dispatch_get_main_queue(), ^{
                    VInstallSettingsHooks();
                });
            }
        });
    }
}
