#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import "../VClientPolicy.h"

static void Require(BOOL ok, NSString *message) { if (!ok) { NSLog(@"FAIL: %@",message); exit(1); } }
@interface YTVersionUtils : NSObject
+ (NSString *)appVersion;
+ (NSString *)appVersionLong;
@end
@implementation YTVersionUtils
+ (NSString *)appVersion { return @"20.21.6"; }
+ (NSString *)appVersionLong { return @"20.21.6"; }
@end
static id FixtureVersion(__unused id self, __unused SEL sel) { return @"native-client-version"; }
@interface YTIClientInfo : NSObject
@property int clientKind;
@property (readonly) int clientName;
@property (readonly) NSString *clientVersion;
@end
static int FixtureKind(YTIClientInfo *self, __unused SEL sel) { return self.clientKind; }
@implementation YTIClientInfo
@dynamic clientName, clientVersion;
+ (_Bool)resolveInstanceMethod:(SEL)sel {
    if (sel == @selector(clientVersion)) return class_addMethod(self, sel, (IMP)FixtureVersion, "@16@0:8");
    if (sel == @selector(clientName)) return class_addMethod(self, sel, (IMP)FixtureKind, "i16@0:8");
    return NO;
}
@end
static _Bool FixtureNo(__unused id self, __unused SEL sel) { return 0; }
@interface YTITopbarMenuButtonRenderer : NSObject
@property (readonly) _Bool hasUnlimitedEntitlement;
@property (readonly) _Bool hasHasUnlimitedEntitlement;
@end
@implementation YTITopbarMenuButtonRenderer
@dynamic hasUnlimitedEntitlement, hasHasUnlimitedEntitlement;
+ (_Bool)resolveInstanceMethod:(SEL)sel {
    if (sel == @selector(hasUnlimitedEntitlement) || sel == @selector(hasHasUnlimitedEntitlement))
        return class_addMethod(self, sel, (IMP)FixtureNo, "B16@0:8");
    return NO;
}
@end
@interface YTIPlayabilityStatus : NSObject
- (_Bool)isPlayable;
- (_Bool)isPlayableInBackground;
- (_Bool)isPlayableInPictureInPicture;
@end
@implementation YTIPlayabilityStatus
- (_Bool)isPlayable { return 0; }
- (_Bool)isPlayableInBackground { return 0; }
- (_Bool)isPlayableInPictureInPicture { return 0; }
@end

int main(void) {
    @autoreleasepool {
        [NSUserDefaults.standardUserDefaults removeObjectForKey:@"VancedReportedYouTubeVersionV1"];
        [NSUserDefaults.standardUserDefaults removeObjectForKey:@"VancedReportedYouTubeVersionDateV1"];
        VInstallClientPolicy(); VInstallClientPolicy();
        Require([YTVersionUtils.appVersion isEqual:@"21.40.5"], @"verified initial reported version");
        YTIClientInfo *ios = [YTIClientInfo new]; ios.clientKind = 5;
        YTIClientInfo *other = [YTIClientInfo new]; other.clientKind = 75;
        Require([ios.clientVersion isEqual:VReportedVersion()], @"dynamic native IOS proto getter uses reported version");
        Require([other.clientVersion isEqual:@"native-client-version"], @"casting and other client types retain native version");
        YTITopbarMenuButtonRenderer *account = [YTITopbarMenuButtonRenderer new];
        Require(account.hasUnlimitedEntitlement && account.hasHasUnlimitedEntitlement, @"declared dynamic local Premium membership flag enabled");
        YTIPlayabilityStatus *status = [YTIPlayabilityStatus new];
        Require(status.isPlayableInBackground && status.isPlayableInPictureInPicture && !status.isPlayable, @"local feature gates enabled without inventing playable media");
        NSData *wrong = [@"{\"results\":[{\"trackId\":544007664,\"bundleId\":\"other.app\",\"version\":\"99.1.1\"}]}" dataUsingEncoding:NSUTF8StringEncoding];
        Require(!VAcceptVersionLookup(wrong), @"different app lookup rejected");
        NSData *invalid = [@"{\"results\":[{\"trackId\":544007664,\"bundleId\":\"com.google.ios.youtube\",\"version\":\"latest\"}]}" dataUsingEncoding:NSUTF8StringEncoding];
        Require(!VAcceptVersionLookup(invalid), @"malformed version rejected");
        NSData *valid = [@"{\"results\":[{\"trackId\":544007664,\"bundleId\":\"com.google.ios.youtube\",\"version\":\"22.0.1\"}]}" dataUsingEncoding:NSUTF8StringEncoding];
        Require(VAcceptVersionLookup(valid) && [ios.clientVersion isEqual:@"22.0.1"] && [YTVersionUtils.appVersionLong isEqual:@"22.0.1"], @"new official-format fixture updates cached reported version");
        Require(!VAcceptVersionLookup([@"{\"results\":[{\"trackId\":544007664,\"bundleId\":\"com.google.ios.youtube\",\"version\":\"20.21.6\"}]}" dataUsingEncoding:NSUTF8StringEncoding]), @"older lookup cannot downgrade cache");
        puts("PASS");
    }
}
