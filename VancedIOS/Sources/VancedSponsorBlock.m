#import <Foundation/Foundation.h>
#import <CommonCrypto/CommonDigest.h>
#import <dispatch/dispatch.h>
#import <math.h>
#import <objc/message.h>
#import <objc/runtime.h>

static NSString * const kSponsorBlockEnabledKey = @"VancedSponsorBlockEnabled";

@interface VSponsorState : NSObject
@property(nonatomic, copy) NSString *videoID;
@property(nonatomic, copy) NSArray<NSDictionary *> *segments;
@property(nonatomic, assign) double lastSkippedEnd;
@end

@implementation VSponsorState
@end

static IMP gOriginalActivateVideo = NULL;
static IMP gOriginalVideoTime = NULL;
static IMP gOriginalMutatedVideoTime = NULL;

static NSMapTable *VSBStateMap(void) {
    static NSMapTable *map;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        map = [NSMapTable weakToStrongObjectsMapTable];
    });
    return map;
}

static NSCache *VSBSegmentCache(void) {
    static NSCache *cache;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        cache = [NSCache new];
        cache.countLimit = 128;
    });
    return cache;
}

static BOOL VSBHook(const char *className, const char *selectorName, IMP replacement, IMP *original) {
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

static id VSBSendId(id object, const char *selectorName) {
    if (!object) return nil;
    SEL selector = sel_registerName(selectorName);
    if (![object respondsToSelector:selector]) return nil;
    return ((id (*)(id, SEL))objc_msgSend)(object, selector);
}

static BOOL VSBSendBool(id object, const char *selectorName) {
    if (!object) return NO;
    SEL selector = sel_registerName(selectorName);
    if (![object respondsToSelector:selector]) return NO;
    return ((BOOL (*)(id, SEL))objc_msgSend)(object, selector);
}

static NSString *VSBVideoID(id player) {
    id value = VSBSendId(player, "currentVideoID");
    if (![value isKindOfClass:[NSString class]] || [value length] == 0) {
        value = VSBSendId(player, "contentVideoID");
    }
    return [value isKindOfClass:[NSString class]] ? value : nil;
}

static NSString *VSBSHA256Prefix(NSString *videoID) {
    NSData *data = [videoID dataUsingEncoding:NSUTF8StringEncoding];
    if (!data) return nil;
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.bytes, (CC_LONG)data.length, digest);
    NSMutableString *hex = [NSMutableString stringWithCapacity:CC_SHA256_DIGEST_LENGTH * 2];
    for (NSUInteger i = 0; i < CC_SHA256_DIGEST_LENGTH; i++) {
        [hex appendFormat:@"%02x", digest[i]];
    }
    return [hex substringToIndex:MIN((NSUInteger)4, hex.length)];
}

static NSArray<NSDictionary *> *VSBValidatedSegments(NSArray *raw) {
    if (![raw isKindOfClass:[NSArray class]]) return @[];
    NSMutableArray *result = [NSMutableArray array];
    NSSet *allowed = [NSSet setWithArray:@[@"sponsor", @"selfpromo", @"interaction", @"intro", @"outro"]];
    for (id entry in raw) {
        if (![entry isKindOfClass:[NSDictionary class]]) continue;
        NSDictionary *dict = entry;
        NSString *category = dict[@"category"];
        NSString *actionType = dict[@"actionType"];
        NSArray *segment = dict[@"segment"];
        if (![allowed containsObject:category]) continue;
        if ([actionType isKindOfClass:[NSString class]] && ![actionType isEqualToString:@"skip"]) continue;
        if (![segment isKindOfClass:[NSArray class]] || segment.count < 2) continue;
        double start = [segment[0] doubleValue];
        double end = [segment[1] doubleValue];
        if (!isfinite(start) || !isfinite(end) || start < 0 || end <= start) continue;
        [result addObject:dict];
    }
    [result sortUsingComparator:^NSComparisonResult(NSDictionary *a, NSDictionary *b) {
        double left = [a[@"segment"][0] doubleValue];
        double right = [b[@"segment"][0] doubleValue];
        if (left < right) return NSOrderedAscending;
        if (left > right) return NSOrderedDescending;
        return NSOrderedSame;
    }];
    return result;
}

static void VSBFetchSegments(NSString *videoID, void (^completion)(NSArray<NSDictionary *> *segments)) {
    NSArray *cached = [VSBSegmentCache() objectForKey:videoID];
    if (cached) {
        completion(cached);
        return;
    }

    NSString *prefix = VSBSHA256Prefix(videoID);
    if (prefix.length != 4) {
        completion(@[]);
        return;
    }

    NSURLComponents *components = [NSURLComponents componentsWithString:
        [NSString stringWithFormat:@"https://sponsor.ajay.app/api/skipSegments/%@", prefix]];
    NSString *categories = @"[\"sponsor\",\"selfpromo\",\"interaction\",\"intro\",\"outro\"]";
    components.queryItems = @[
        [NSURLQueryItem queryItemWithName:@"service" value:@"YouTube"],
        [NSURLQueryItem queryItemWithName:@"categories" value:categories],
        [NSURLQueryItem queryItemWithName:@"actionTypes" value:@"[\"skip\"]"]
    ];
    NSURL *url = components.URL;
    if (!url) {
        completion(@[]);
        return;
    }

    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
    request.timeoutInterval = 8.0;
    [request setValue:@"application/json" forHTTPHeaderField:@"Accept"];
    [request setValue:@"VancedIOS/0.1" forHTTPHeaderField:@"User-Agent"];

    [[[NSURLSession sharedSession] dataTaskWithRequest:request
        completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        NSArray *segments = @[];
        NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
        if (!error && http.statusCode == 200 && data.length > 0) {
            id json = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            if ([json isKindOfClass:[NSArray class]]) {
                for (id candidate in (NSArray *)json) {
                    if (![candidate isKindOfClass:[NSDictionary class]]) continue;
                    if ([candidate[@"videoID"] isEqualToString:videoID]) {
                        segments = VSBValidatedSegments(candidate[@"segments"]);
                        break;
                    }
                }
            }
        }
        [VSBSegmentCache() setObject:segments forKey:videoID];
        dispatch_async(dispatch_get_main_queue(), ^{
            completion(segments);
        });
    }] resume];
}

static void VSBSetStateForPlayer(id player, NSString *videoID) {
    if (!player || videoID.length == 0) return;
    VSponsorState *state = [VSponsorState new];
    state.videoID = videoID;
    state.segments = @[];
    state.lastSkippedEnd = -1;
    [VSBStateMap() setObject:state forKey:player];

    VSBFetchSegments(videoID, ^(NSArray<NSDictionary *> *segments) {
        VSponsorState *current = [VSBStateMap() objectForKey:player];
        if (!current || ![current.videoID isEqualToString:videoID]) return;
        current.segments = segments ?: @[];
    });
}

static void VSBSeek(id player, double time) {
    SEL seek = sel_registerName("seekToTime:");
    SEL scrub = sel_registerName("scrubToTime:");
    if ([player respondsToSelector:seek]) {
        ((void (*)(id, SEL, double))objc_msgSend)(player, seek, time);
    } else if ([player respondsToSelector:scrub]) {
        ((void (*)(id, SEL, double))objc_msgSend)(player, scrub, time);
    }
}

static double VSBTime(id timeObject) {
    if (!timeObject) return NAN;
    SEL selector = sel_registerName("time");
    if (![timeObject respondsToSelector:selector]) return NAN;
    return ((double (*)(id, SEL))objc_msgSend)(timeObject, selector);
}

static void VSBHandleTick(id player, id timeObject) {
    if (![[NSUserDefaults standardUserDefaults] boolForKey:kSponsorBlockEnabledKey]) return;
    if (VSBSendBool(player, "isPlayingAd")) return;
    VSponsorState *state = [VSBStateMap() objectForKey:player];
    if (!state || state.segments.count == 0) return;

    double now = VSBTime(timeObject);
    if (!isfinite(now)) return;
    for (NSDictionary *entry in state.segments) {
        NSArray *range = entry[@"segment"];
        double start = [range[0] doubleValue];
        double end = [range[1] doubleValue];
        if (fabs(state.lastSkippedEnd - end) < 0.01) continue;
        if (now + 0.15 >= start && now < end - 0.05) {
            state.lastSkippedEnd = end;
            VSBSeek(player, end);
            break;
        }
    }
}

static void VSBActivateVideo(id self, SEL _cmd, id controller, id video, id playbackData) {
    if (gOriginalActivateVideo) {
        ((void (*)(id, SEL, id, id, id))gOriginalActivateVideo)(self, _cmd, controller, video, playbackData);
    }
    if (![[NSUserDefaults standardUserDefaults] boolForKey:kSponsorBlockEnabledKey]) return;
    NSString *videoID = VSBVideoID(self);
    if (videoID.length) VSBSetStateForPlayer(self, videoID);
}

static void VSBVideoTime(id self, SEL _cmd, id video, id timeObject) {
    if (gOriginalVideoTime) {
        ((void (*)(id, SEL, id, id))gOriginalVideoTime)(self, _cmd, video, timeObject);
    }
    VSBHandleTick(self, timeObject);
}

static void VSBMutatedVideoTime(id self, SEL _cmd, id video, id timeObject) {
    if (gOriginalMutatedVideoTime) {
        ((void (*)(id, SEL, id, id))gOriginalMutatedVideoTime)(self, _cmd, video, timeObject);
    }
    VSBHandleTick(self, timeObject);
}

static void VSBInstallHooks(void) {
    VSBHook("YTPlayerViewController",
            "playbackController:didActivateVideo:withPlaybackData:",
            (IMP)VSBActivateVideo,
            &gOriginalActivateVideo);
    VSBHook("YTPlayerViewController",
            "singleVideo:currentVideoTimeDidChange:",
            (IMP)VSBVideoTime,
            &gOriginalVideoTime);
    VSBHook("YTPlayerViewController",
            "potentiallyMutatedSingleVideo:currentVideoTimeDidChange:",
            (IMP)VSBMutatedVideoTime,
            &gOriginalMutatedVideoTime);
}

__attribute__((constructor))
static void VancedSponsorBlockInitialize(void) {
    @autoreleasepool {
        NSString *bundleID = NSBundle.mainBundle.bundleIdentifier ?: @"";
        if (![bundleID.lowercaseString containsString:@"youtube"]) return;
        [[NSUserDefaults standardUserDefaults] registerDefaults:@{kSponsorBlockEnabledKey: @YES}];
        dispatch_async(dispatch_get_main_queue(), ^{
            VSBInstallHooks();
            for (NSNumber *delay in @[@1, @3, @8, @20, @60]) {
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW,
                                             (int64_t)(delay.doubleValue * NSEC_PER_SEC)),
                               dispatch_get_main_queue(), ^{
                    VSBInstallHooks();
                });
            }
        });
    }
}
