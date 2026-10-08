#import <Foundation/Foundation.h>
#import "../VDiagnostics.h"

static void Require(BOOL ok, NSString *message) {
    if (!ok) { NSLog(@"FAIL: %@", message); exit(1); }
}
@interface TestStatus : NSObject
@property int status;
@property NSString *reason;
@end
@implementation TestStatus
@end
@interface TestStreams : NSObject
@property NSArray *formatsArray;
@property NSArray *adaptiveFormatsArray;
@end
@implementation TestStreams
@end
@interface TestData : NSObject
@property TestStatus *playabilityStatus;
@property TestStreams *streamingData;
@end
@implementation TestData
@end
@interface TestResponse : NSObject
@property TestData *playerData;
@end
@implementation TestResponse
@end

int main(void) {
    @autoreleasepool {
        TestStatus *status = [TestStatus new]; status.status = 5;
        status.reason = @"Update your app. https://example.com/?token=secret jane@example.com abcdefghijklmnopqrstuvwxyz1234567890";
        VDiagnosticsRecordPlayability(status);
        VDiagnosticsRecordPlayability(status);
        NSString *report = VDiagnosticsReport();
        NSDictionary *json = [NSJSONSerialization JSONObjectWithData:[report dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
        NSArray *events = json[@"events"];
        Require(events.count == 1 && [events[0][@"count"] intValue] == 2, @"repeated polling does not flood the report");
        Require([events[0][@"details"][@"status_code"] intValue] == 5, @"native status enum is retained");
        Require([report containsString:@"Update your app"] && ![report containsString:@"secret"] && ![report containsString:@"jane@example"] && ![report containsString:@"abcdefghijklmnopqrstuvwxyz123"], @"message survives while URLs, emails and long credentials are redacted");
        TestResponse *response = [TestResponse new]; response.playerData = [TestData new];
        response.playerData.playabilityStatus = status;
        response.playerData.streamingData = [TestStreams new];
        response.playerData.streamingData.formatsArray = @[@"signed-url-never-recorded"];
        response.playerData.streamingData.adaptiveFormatsArray = @[@1,@2];
        NSError *error = [NSError errorWithDomain:@"FixturePlayer" code:14 userInfo:@{NSLocalizedDescriptionKey:@"private-auth-secret"}];
        VDiagnosticsRecordError(@"player_error", error, response);
        report = VDiagnosticsReport();
        json = [NSJSONSerialization JSONObjectWithData:[report dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
        Require([json[@"events"][1][@"details"][@"stream_format_count"] intValue] == 3, @"formats are counted without saving signed URLs");
        Require(![report containsString:@"signed-url-never-recorded"] && ![report containsString:@"private-auth-secret"], @"request contents and error userInfo are omitted");
        VDiagnosticsRecordPlayability([NSObject new]);
        VDiagnosticsRecordError(@"google_auth_session", nil, nil);
        for (int n=0;n<150;n++) VDiagnosticsRecordRequest(n%2, NO);
        report = VDiagnosticsReport();
        json = [NSJSONSerialization JSONObjectWithData:[report dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
        Require([json[@"events"] count] == 100, @"bounded ring retains only 100 events");
        Require([report containsString:@"NOT_CONFIRMED"], @"report never claims that runtime passed");
        puts("PASS");
    }
}
