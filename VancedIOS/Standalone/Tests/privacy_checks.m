#import <Foundation/Foundation.h>
#import "../VPrivacy.m"

static void Require(BOOL ok, NSString *message) { if (!ok) { NSLog(@"FAIL: %@",message); exit(1); } }
@interface FixtureClient : NSObject <NSURLProtocolClient>
@property NSHTTPURLResponse *response;
@property NSMutableData *body;
@property NSUInteger finishes;
@end
@implementation FixtureClient
- (void)URLProtocol:(NSURLProtocol *)protocol didReceiveResponse:(NSURLResponse *)response cacheStoragePolicy:(NSURLCacheStoragePolicy)policy { self.response = (id)response; }
- (void)URLProtocol:(NSURLProtocol *)protocol didLoadData:(NSData *)data { if (!self.body) self.body = [NSMutableData data]; [self.body appendData:data]; }
- (void)URLProtocolDidFinishLoading:(NSURLProtocol *)protocol { self.finishes++; }
- (void)URLProtocol:(NSURLProtocol *)protocol didFailWithError:(NSError *)error { exit(2); }
- (void)URLProtocol:(NSURLProtocol *)protocol wasRedirectedToRequest:(NSURLRequest *)request redirectResponse:(NSURLResponse *)response { exit(3); }
- (void)URLProtocol:(NSURLProtocol *)protocol cachedResponseIsValid:(NSCachedURLResponse *)response {}
- (void)URLProtocol:(NSURLProtocol *)protocol didReceiveAuthenticationChallenge:(NSURLAuthenticationChallenge *)challenge { exit(4); }
- (void)URLProtocol:(NSURLProtocol *)protocol didCancelAuthenticationChallenge:(NSURLAuthenticationChallenge *)challenge {}
@end

int main(void) {
    @autoreleasepool {
        for (NSString *s in @[@"https://www.youtube.com/api/stats/watchtime?v=private", @"https://youtube.com/youtubei/v1/log_event", @"https://firebaselogging.googleapis.com/v0cc/log/batch", @"https://www.google-analytics.com/g/collect"]) Require(VPrivacyBlocksURL([NSURL URLWithString:s]), @"identified telemetry/watch route intercepted");
        for (NSString *s in @[@"https://accounts.google.com/o/oauth2/auth", @"https://oauth2.googleapis.com/token", @"https://youtube.com/youtubei/v1/player", @"https://youtube.com/youtubei/v1/browse", @"https://r1.googlevideo.com/videoplayback", @"https://youtube.com/api/stats", @"https://youtube.com.evil.example/api/stats/watchtime", @"https://evil.example/youtubei/v1/log_event", @"https://itunes.apple.com/lookup?id=544007664", @"file:///api/stats/watchtime"]) Require(!VPrivacyBlocksURL([NSURL URLWithString:s]), @"auth/media/feed/Apple and unrelated hosts remain native");
        for (NSString *mime in @[@"application/json", @"application/x-protobuf"]) {
            NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:[NSURL URLWithString:@"https://youtube.com/youtubei/v1/log_event"]];
            [request setValue:mime forHTTPHeaderField:@"Content-Type"];
            request.HTTPBody = [@"private-history-payload" dataUsingEncoding:NSUTF8StringEncoding];
            FixtureClient *client = [FixtureClient new];
            VPrivateTelemetryProtocol *protocol = [[VPrivateTelemetryProtocol alloc] initWithRequest:request cachedResponse:nil client:client];
            [protocol startLoading];
            Require(client.finishes == 1 && client.response.statusCode == 200, @"local acknowledgement finishes the caller once");
            Require(client.body.length == ([mime containsString:@"protobuf"] ? 0 : 2), @"valid empty protobuf/JSON acknowledgements");
        }
        VInstallPrivacy(); VInstallPrivacy();
        NSURLSessionConfiguration *config = NSURLSessionConfiguration.ephemeralSessionConfiguration;
        NSUInteger count = 0; for (Class cls in config.protocolClasses) if (cls == VPrivateTelemetryProtocol.class) count++;
        Require(count == 1, @"session configuration contains one intercepting protocol");
        dispatch_semaphore_t done = dispatch_semaphore_create(0);
        __block NSInteger code = 0; __block BOOL failed = NO;
        NSURLSession *session = [NSURLSession sessionWithConfiguration:config];
        [[session dataTaskWithURL:[NSURL URLWithString:@"https://www.youtube.com/api/stats/watchtime"] completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
            failed = error != nil; code = [(NSHTTPURLResponse *)response statusCode]; dispatch_semaphore_signal(done);
        }] resume];
        Require(dispatch_semaphore_wait(done, dispatch_time(DISPATCH_TIME_NOW, 5*NSEC_PER_SEC)) == 0 && !failed && code == 204, @"NSURLSession completes blocked telemetry locally");
        [session finishTasksAndInvalidate];
        puts("PASS");
    }
}
