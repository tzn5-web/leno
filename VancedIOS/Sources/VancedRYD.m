#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <dispatch/dispatch.h>
#import <math.h>
#import <objc/message.h>
#import <objc/runtime.h>

static NSString * const kRYDEnabledKey = @"VancedReturnYouTubeDislikeEnabled";
static const void *kRYDButtonVideoKey = &kRYDButtonVideoKey;

static IMP gRYDOriginalActivateVideo = NULL;
static IMP gRYDOriginalButtonDidMoveToWindow = NULL;
static IMP gRYDOriginalButtonLayoutSubviews = NULL;
static IMP gRYDOriginalReelUpdate = NULL;
static NSString *gRYDCurrentVideoID = nil;

static NSCache *VRYDCache(void) {
    static NSCache *cache;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        cache = [NSCache new];
        cache.countLimit = 256;
    });
    return cache;
}

static NSMutableDictionary<NSString *, NSMutableArray *> *VRYDInflight(void) {
    static NSMutableDictionary *requests;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        requests = [NSMutableDictionary dictionary];
    });
    return requests;
}

static BOOL VRYDHook(const char *className, const char *selectorName, IMP replacement, IMP *original) {
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

static id VRYDSendId(id object, const char *selectorName) {
    if (!object) return nil;
    SEL selector = sel_registerName(selectorName);
    if (![object respondsToSelector:selector]) return nil;
    return ((id (*)(id, SEL))objc_msgSend)(object, selector);
}

static NSString *VRYDVideoIDFromPlayer(id player) {
    id value = VRYDSendId(player, "currentVideoID");
    if (![value isKindOfClass:[NSString class]] || [value length] == 0) {
        value = VRYDSendId(player, "contentVideoID");
    }
    return [value isKindOfClass:[NSString class]] ? value : nil;
}

static NSString *VRYDVideoIDFromRenderer(id renderer) {
    id target = VRYDSendId(renderer, "target");
    id value = VRYDSendId(target, "videoId");
    if (![value isKindOfClass:[NSString class]] || [value length] == 0) {
        value = VRYDSendId(target, "videoID");
    }
    return [value isKindOfClass:[NSString class]] ? value : nil;
}

static NSString *VRYDCompactCount(unsigned long long value) {
    if (value < 1000) return [NSString stringWithFormat:@"%llu", value];
    static NSArray<NSString *> *suffixes;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ suffixes = @[@"K", @"M", @"B", @"T"]; });
    double scaled = (double)value;
    NSUInteger index = 0;
    while (scaled >= 1000.0 && index < suffixes.count) {
        scaled /= 1000.0;
        index++;
    }
    NSString *suffix = suffixes[MIN(index, suffixes.count) - 1];
    if (scaled >= 100.0 || fabs(scaled - round(scaled)) < 0.05) {
        return [NSString stringWithFormat:@"%.0f%@", scaled, suffix];
    }
    return [NSString stringWithFormat:@"%.1f%@", scaled, suffix];
}

static void VRYDFetch(NSString *videoID, void (^completion)(NSString *count)) {
    if (videoID.length == 0) { completion(nil); return; }
    NSString *cached = [VRYDCache() objectForKey:videoID];
    if (cached) { completion(cached); return; }

    NSMutableArray *waiters = VRYDInflight()[videoID];
    if (waiters) {
        [waiters addObject:[completion copy]];
        return;
    }
    VRYDInflight()[videoID] = [NSMutableArray arrayWithObject:[completion copy]];

    NSURLComponents *components = [NSURLComponents componentsWithString:@"https://returnyoutubedislikeapi.com/votes"];
    components.queryItems = @[[NSURLQueryItem queryItemWithName:@"videoId" value:videoID]];
    NSURL *url = components.URL;
    if (!url) {
        NSArray *callbacks = [VRYDInflight()[videoID] copy];
        [VRYDInflight() removeObjectForKey:videoID];
        for (id callback in callbacks) {
            ((void (^)(NSString *))callback)(nil);
        }
        return;
    }

    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
    request.timeoutInterval = 8.0;
    [request setValue:@"application/json" forHTTPHeaderField:@"Accept"];
    [request setValue:@"VancedIOS/0.1" forHTTPHeaderField:@"User-Agent"];

    [[[NSURLSession sharedSession] dataTaskWithRequest:request
        completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        NSString *formatted = nil;
        NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
        if (!error && http.statusCode == 200 && data.length > 0) {
            id json = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            if ([json isKindOfClass:[NSDictionary class]]) {
                NSNumber *dislikes = ((NSDictionary *)json)[@"dislikes"];
                if ([dislikes isKindOfClass:[NSNumber class]] && dislikes.longLongValue >= 0) {
                    formatted = VRYDCompactCount(dislikes.unsignedLongLongValue);
                }
            }
        }
        if (formatted) [VRYDCache() setObject:formatted forKey:videoID];
        dispatch_async(dispatch_get_main_queue(), ^{
            NSArray *callbacks = [VRYDInflight()[videoID] copy];
            [VRYDInflight() removeObjectForKey:videoID];
            for (id callback in callbacks) {
                ((void (^)(NSString *))callback)(formatted);
            }
        });
    }] resume];
}

static void VRYDSetButtonTitle(id button, NSString *title) {
    if (!button || title.length == 0) return;
    SEL selector = sel_registerName("setTitle:forState:");
    if (![button respondsToSelector:selector]) return;
    ((void (*)(id, SEL, id, NSUInteger))objc_msgSend)(button, selector, title, UIControlStateNormal);
    ((void (*)(id, SEL, id, NSUInteger))objc_msgSend)(button, selector, title, UIControlStateSelected);
    if ([button respondsToSelector:@selector(setAccessibilityValue:)]) {
        [button setAccessibilityValue:[NSString stringWithFormat:@"%@ dislikes", title]];
    }
}

static BOOL VRYDIsDislikeButton(id button) {
    NSString *identifier = [button respondsToSelector:@selector(accessibilityIdentifier)]
        ? [button accessibilityIdentifier]
        : nil;
    if (![identifier isKindOfClass:[NSString class]]) return NO;
    return [identifier.lowercaseString containsString:@"dislike"];
}

static void VRYDUpdateButton(id button, NSString *videoID) {
    if (![[NSUserDefaults standardUserDefaults] boolForKey:kRYDEnabledKey]) return;
    if (!VRYDIsDislikeButton(button) || videoID.length == 0) return;

    NSString *last = objc_getAssociatedObject(button, kRYDButtonVideoKey);
    if ([last isEqualToString:videoID]) return;
    objc_setAssociatedObject(button, kRYDButtonVideoKey, videoID, OBJC_ASSOCIATION_COPY_NONATOMIC);

    __weak id weakButton = button;
    VRYDFetch(videoID, ^(NSString *count) {
        id strongButton = weakButton;
        if (!strongButton) return;
        NSString *current = objc_getAssociatedObject(strongButton, kRYDButtonVideoKey);
        if (![current isEqualToString:videoID]) return;
        if (count.length > 0) {
            VRYDSetButtonTitle(strongButton, count);
            return;
        }
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(15 * NSEC_PER_SEC)),
                       dispatch_get_main_queue(), ^{
            id retryButton = weakButton;
            if (!retryButton) return;
            NSString *retryCurrent = objc_getAssociatedObject(retryButton, kRYDButtonVideoKey);
            if ([retryCurrent isEqualToString:videoID]) {
                objc_setAssociatedObject(retryButton, kRYDButtonVideoKey, nil, OBJC_ASSOCIATION_ASSIGN);
            }
        });
    });
}

static void VRYDActivateVideo(id self, SEL _cmd, id controller, id video, id playbackData) {
    if (gRYDOriginalActivateVideo) {
        ((void (*)(id, SEL, id, id, id))gRYDOriginalActivateVideo)(self, _cmd, controller, video, playbackData);
    }
    NSString *videoID = VRYDVideoIDFromPlayer(self);
    if (videoID.length) gRYDCurrentVideoID = [videoID copy];
}

static void VRYDButtonDidMoveToWindow(id self, SEL _cmd) {
    if (gRYDOriginalButtonDidMoveToWindow) {
        ((void (*)(id, SEL))gRYDOriginalButtonDidMoveToWindow)(self, _cmd);
    }
    if ([self respondsToSelector:@selector(window)] && [self window]) {
        VRYDUpdateButton(self, gRYDCurrentVideoID);
    }
}

static void VRYDButtonLayoutSubviews(id self, SEL _cmd) {
    if (gRYDOriginalButtonLayoutSubviews) {
        ((void (*)(id, SEL))gRYDOriginalButtonLayoutSubviews)(self, _cmd);
    }
    VRYDUpdateButton(self, gRYDCurrentVideoID);
}

static void VRYDReelUpdate(id self, SEL _cmd, id renderer) {
    if (gRYDOriginalReelUpdate) {
        ((void (*)(id, SEL, id))gRYDOriginalReelUpdate)(self, _cmd, renderer);
    }
    if (![[NSUserDefaults standardUserDefaults] boolForKey:kRYDEnabledKey]) return;
    NSString *videoID = VRYDVideoIDFromRenderer(renderer);
    id button = VRYDSendId(self, "dislikeButton");
    if (videoID.length && button) VRYDUpdateButton(button, videoID);
}

static void VRYDInstallHooks(void) {
    VRYDHook("YTPlayerViewController",
             "playbackController:didActivateVideo:withPlaybackData:",
             (IMP)VRYDActivateVideo,
             &gRYDOriginalActivateVideo);
    VRYDHook("YTQTMButton",
             "didMoveToWindow",
             (IMP)VRYDButtonDidMoveToWindow,
             &gRYDOriginalButtonDidMoveToWindow);
    VRYDHook("YTQTMButton",
             "layoutSubviews",
             (IMP)VRYDButtonLayoutSubviews,
             &gRYDOriginalButtonLayoutSubviews);
    VRYDHook("YTReelWatchLikesController",
             "updateLikeButtonWithRenderer:",
             (IMP)VRYDReelUpdate,
             &gRYDOriginalReelUpdate);
}

__attribute__((constructor))
static void VancedRYDInitialize(void) {
    @autoreleasepool {
        NSString *bundleID = NSBundle.mainBundle.bundleIdentifier ?: @"";
        if (![bundleID.lowercaseString containsString:@"youtube"]) return;
        [[NSUserDefaults standardUserDefaults] registerDefaults:@{kRYDEnabledKey: @YES}];
        dispatch_async(dispatch_get_main_queue(), ^{
            VRYDInstallHooks();
            for (NSNumber *delay in @[@1, @3, @8, @20, @60]) {
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW,
                                             (int64_t)(delay.doubleValue * NSEC_PER_SEC)),
                               dispatch_get_main_queue(), ^{ VRYDInstallHooks(); });
            }
        });
    }
}
