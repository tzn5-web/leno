#import "VPrivacy.h"
#import <objc/runtime.h>
#import <string.h>

static BOOL VHost(NSString *host, NSString *domain) {
    return [host isEqual:domain] || [host hasSuffix:[@"." stringByAppendingString:domain]];
}

BOOL VPrivacyBlocksURL(NSURL *url) {
    if (![@[@"https", @"http"] containsObject:url.scheme.lowercaseString]) return NO;
    NSString *host = url.host.lowercaseString;
    NSString *path = url.path;
    if (VHost(host, @"youtube.com") || VHost(host, @"youtube-nocookie.com") || VHost(host, @"googlevideo.com"))
        return [path hasPrefix:@"/api/stats/"] || [path isEqual:@"/youtubei/v1/log_event"];
    if (VHost(host, @"google-analytics.com"))
        return [@[@"/collect", @"/j/collect", @"/g/collect"] containsObject:path];
    if ([host isEqual:@"play.googleapis.com"] || [host isEqual:@"play.google.com"])
        return [path isEqual:@"/log"];
    if ([host isEqual:@"firebaselogging.googleapis.com"])
        return [path isEqual:@"/v0cc/log/batch"];
    if ([host isEqual:@"crashlyticsreports-pa.googleapis.com"])
        return [path isEqual:@"/v1/firelog/legacy/batchlog"];
    return NO;
}

@interface VPrivateTelemetryProtocol : NSURLProtocol
@end
@implementation VPrivateTelemetryProtocol
+ (BOOL)canInitWithRequest:(NSURLRequest *)request { return VPrivacyBlocksURL(request.URL); }
+ (NSURLRequest *)canonicalRequestForRequest:(NSURLRequest *)request { return request; }
- (void)startLoading {
    // Complete only the identified statistics/telemetry routes locally.
    // OAuth, player/browse/search, attestations and media never enter this path.
    NSURL *url = self.request.URL;
    NSInteger status = 204;
    NSData *body = [NSData data];
    NSString *type = @"text/plain";
    if ([url.path isEqual:@"/youtubei/v1/log_event"]) {
        status = 200;
        BOOL proto = [[self.request valueForHTTPHeaderField:@"Content-Type"].lowercaseString containsString:@"protobuf"];
        type = proto ? @"application/x-protobuf" : @"application/json";
        if (!proto) body = [@"{}" dataUsingEncoding:NSUTF8StringEncoding];
    } else if ([url.host.lowercaseString hasSuffix:@"googleapis.com"] || [url.host.lowercaseString isEqual:@"play.google.com"]) {
        status = 200;
        type = @"application/json";
        body = [@"{\"nextRequestWaitMillis\":\"86400000\"}" dataUsingEncoding:NSUTF8StringEncoding];
        NSString *requestType = [self.request valueForHTTPHeaderField:@"Content-Type"].lowercaseString;
        if ([requestType containsString:@"protobuf"]) {
            type = @"application/x-protobuf";
            // CCT LogResponse: optional field 1, next_request_wait_millis=86400000.
            const unsigned char ack[] = {0x08,0x80,0xb8,0x99,0x29};
            body = [NSData dataWithBytes:ack length:sizeof(ack)];
        } else {
            for (NSURLQueryItem *item in [NSURLComponents componentsWithURL:url resolvingAgainstBaseURL:NO].queryItems)
                if ([item.name isEqual:@"format"] && [item.value isEqual:@"json_proto"])
                    body = [@"[86400000]" dataUsingEncoding:NSUTF8StringEncoding];
        }
    }
    NSHTTPURLResponse *response = [[NSHTTPURLResponse alloc] initWithURL:url statusCode:status HTTPVersion:@"HTTP/1.1"
        headerFields:@{@"Content-Type":type, @"Content-Length":@(body.length).stringValue}];
    [self.client URLProtocol:self didReceiveResponse:response cacheStoragePolicy:NSURLCacheStorageNotAllowed];
    if (body.length) [self.client URLProtocol:self didLoadData:body];
    [self.client URLProtocolDidFinishLoading:self];
}
- (void)stopLoading {}
@end

static IMP VOriginalDefault;
static IMP VOriginalEphemeral;
static NSURLSessionConfiguration *VAddProtocol(NSURLSessionConfiguration *config) {
    if (!config) return nil;
    NSMutableArray *classes = [config.protocolClasses mutableCopy] ?: [NSMutableArray array];
    if (![classes containsObject:VPrivateTelemetryProtocol.class]) [classes insertObject:VPrivateTelemetryProtocol.class atIndex:0];
    config.protocolClasses = classes;
    return config;
}
static id VDefault(id object, SEL selector) { return VAddProtocol(((id (*)(id, SEL))VOriginalDefault)(object, selector)); }
static id VEphemeral(id object, SEL selector) { return VAddProtocol(((id (*)(id, SEL))VOriginalEphemeral)(object, selector)); }

void VInstallPrivacy(void) {
    [NSURLProtocol registerClass:VPrivateTelemetryProtocol.class];
    Class meta = object_getClass(NSURLSessionConfiguration.class);
    for (NSString *name in @[@"defaultSessionConfiguration", @"ephemeralSessionConfiguration"]) {
        IMP *original = [name isEqual:@"defaultSessionConfiguration"] ? &VOriginalDefault : &VOriginalEphemeral;
        if (*original) continue;
        SEL selector = NSSelectorFromString(name);
        Method method = class_getInstanceMethod(meta, selector);
        if (!method || strcmp(method_getTypeEncoding(method), "@16@0:8")) continue;
        IMP replacement = [name isEqual:@"defaultSessionConfiguration"] ? (IMP)VDefault : (IMP)VEphemeral;
        *original = method_setImplementation(method, replacement);
    }
}
