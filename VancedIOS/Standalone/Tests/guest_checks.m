#import <Foundation/Foundation.h>
#import "../VGuestStore.h"
#import "../VGuestEntry.h"
#import <math.h>

static void Require(BOOL ok, NSString *message) {
    if (!ok) { NSLog(@"FAIL: %@", message); exit(1); }
}

@interface TestTransaction : NSObject
@property id futureIdentity;
@property BOOL committed;
@end
@implementation TestTransaction
@end

@interface TestState : NSObject
@property NSUInteger endings;
@property NSUInteger shows;
- (void)endedSignIn;
- (void)showViewController;
@end
@implementation TestState
- (void)endedSignIn { self.endings++; }
- (void)showViewController { Require(self.endings == 1, @"sign-in ends before Home"); self.shows++; }
@end

@interface TestController : NSObject
@property TestTransaction *transaction;
@property TestState *stateController;
@property (copy) void (^successBlock)(void);
@property NSUInteger completions;
@property BOOL nativeSignedIn;
- (void)setFutureIdentityForGoogleAccount:(id)account accountItem:(id)item;
@end
@implementation TestController
- (void)setFutureIdentityForGoogleAccount:(id)account accountItem:(id)item {
    self.transaction.futureIdentity = account;
}
@end

@interface TestNativeDefaults : NSObject
@property _Bool watchHistoryPaused;
@end
@implementation TestNativeDefaults
@end

int main(int argc, const char **argv) {
    @autoreleasepool {
        Require(argc == 3, @"expected case and directory");
        NSString *mode = @(argv[1]);
        NSURL *root = [NSURL fileURLWithPath:@(argv[2]) isDirectory:YES];
        if ([mode isEqual:@"transaction"]) {
            TestController *controller = [TestController new];
            TestTransaction *transaction = [TestTransaction new];
            transaction.futureIdentity = @"old pending identity";
            controller.transaction = transaction;
            controller.stateController = [TestState new];
            __weak TestController *weakController = controller;
            controller.successBlock = ^{
                transaction.committed = YES;
                weakController.completions++;
                weakController.nativeSignedIn = transaction.futureIdentity != nil;
            };
            Require(!VGuestCompleteWithoutPresentation(controller), @"unmarked manual login is preserved");
            VGuestBeginAutomaticSignIn();
            VGuestTagSignInTransaction(transaction);
            VGuestEndAutomaticSignIn();
            [NSUserDefaults.standardUserDefaults removeObjectForKey:@"VancedLegacyAutomaticGuest"];
            Require(!VGuestCompleteWithoutPresentation(controller), @"default preserves native sign-in presentation");
            [NSUserDefaults.standardUserDefaults setBool:YES forKey:@"VancedLegacyAutomaticGuest"];
            Require(VGuestCompleteWithoutPresentation(controller), @"marked automatic guest completion remains available after launch scope ends");
            Require(transaction.committed && transaction.futureIdentity == nil && controller.completions == 1 && !controller.nativeSignedIn, @"guest commits without faking login");
            Require(controller.stateController.endings == 1 && controller.stateController.shows == 1, @"startup state completes and Home is shown");
            Require(VGuestCompleteWithoutPresentation(controller) && controller.completions == 1, @"repeat callback does not create another guest");
            VGuestBeginAutomaticSignIn();
            VGuestBeginExplicitSignIn();
            VGuestTagSignInTransaction(transaction);
            VGuestEndExplicitSignIn();
            VGuestEndAutomaticSignIn();
            Require(!VGuestCompleteWithoutPresentation(controller), @"explicit coalesced login clears the automatic marker");
            VGuestBeginAutomaticSignIn();
            VGuestTagSignInTransaction(transaction);
            VGuestEndAutomaticSignIn();
            Require(!VGuestCompleteWithoutPresentation(controller), @"later automatic coalescing cannot override an explicit login");
            @try { VGuestRunSignIn(NO, ^{ @throw [NSException exceptionWithName:@"Fixture" reason:nil userInfo:nil]; }); }
            @catch (NSException *exception) {}
            controller.transaction = [TestTransaction new];
            VGuestTagSignInTransaction(controller.transaction);
            Require(!VGuestCompleteWithoutPresentation(controller), @"exception unwinds startup scope instead of suppressing later manual login");
            Require(!VGuestCompleteWithoutPresentation([NSObject new]), @"unsupported native ABI falls back");
            controller.transaction = nil;
            Require(!VGuestCompleteWithoutPresentation(controller), @"missing transaction falls back");
            Require(controller.completions == 1, @"fallback does not invoke callbacks");
            [NSUserDefaults.standardUserDefaults removeObjectForKey:@"VancedLegacyAutomaticGuest"];
        } else if ([mode isEqual:@"native-history"]) {
            NSString *key = @"VancedLocalHistoryOnlyConfiguredV2";
            [NSUserDefaults.standardUserDefaults removeObjectForKey:key];
            TestNativeDefaults *native = [TestNativeDefaults new];
            native.watchHistoryPaused = 0;
            Require(!VGuestConfigureNativeHistory([NSObject new]), @"unknown ABI does not mark native setup complete");
            Require(VGuestConfigureNativeHistory(native) && native.watchHistoryPaused, @"app-local native history flag pauses service watch tracking");
            Require(VGuestConfigureNativeHistory(native) && native.watchHistoryPaused, @"repeated setup keeps service watch tracking paused");
            [NSUserDefaults.standardUserDefaults removeObjectForKey:key];
        } else if ([mode isEqual:@"progress"]) {
            NSUInteger accepted = 0;
            // 100,000 callbacks over ten seconds must admit only ten updates.
            for (unsigned long long n = 0; n < 100000; n++)
                if (VGuestAcceptProgress(1000000000ULL + n * 100000ULL)) accepted++;
            Require(accepted == 10, @"progress flood is throttled before queueing");
        } else if ([mode isEqual:@"persistence"]) {
            VGuestStore *store = [[VGuestStore alloc] initWithDirectory:root];
            NSDictionary *record = @{@"id":@"dQw4w9WgXcQ", @"title":@"Test video", @"author":@"Test author"};
            [store recordVideo:record];
            [store updateVideo:record[@"id"] position:42.5];
            [store flush];
            [store recordVideo:record];
            [store saveVideo:record inList:@"favorites"];
            [store saveVideo:record inList:@"favorites"];
            [store saveVideo:record inList:@"later"];
            [store createPlaylist:@"  My list  "];
            [store saveVideo:record inList:@"playlist:My list"];
            VGuestStore *reloaded = [[VGuestStore alloc] initWithDirectory:root];
            NSDictionary *state = reloaded.snapshot;
            Require(!reloaded.lastError, @"valid library reloads");
            Require([state[@"history"] count] == 1 && [state[@"history"][0][@"position"] doubleValue] == 42.5, @"deduplicated history retains progress");
            Require([state[@"favorites"] count] == 1 && [state[@"later"] count] == 1 && [state[@"playlists"][@"My list"] count] == 1, @"saved collections persist independently");
            [reloaded clearHistory];
            [reloaded updateVideo:record[@"id"] position:99];
            [reloaded flush];
            VGuestStore *cleared = [[VGuestStore alloc] initWithDirectory:root];
            Require([cleared.snapshot[@"history"] count] == 0 && [cleared.snapshot[@"favorites"] count] == 1, @"cleared history is not resurrected by progress or shared with favorites");
            [cleared recordVideo:@{@"id":@"not-valid"}];
            [cleared recordVideo:record];
            [cleared updateVideo:record[@"id"] position:NAN];
            Require([cleared.snapshot[@"history"][0][@"position"] doubleValue] == 0, @"invalid IDs and nonfinite positions rejected");
        } else if ([mode isEqual:@"corruption"]) {
            [[NSFileManager defaultManager] createDirectoryAtURL:root withIntermediateDirectories:YES attributes:nil error:NULL];
            NSURL *file = [root URLByAppendingPathComponent:@"library.json"];
            NSData *damaged = [@"{invalid-json" dataUsingEncoding:NSUTF8StringEncoding];
            [damaged writeToURL:file atomically:YES];
            VGuestStore *store = [[VGuestStore alloc] initWithDirectory:root];
            [store recordVideo:@{@"id":@"dQw4w9WgXcQ"}];
            [store clearHistory];
            [store flush];
            Require(store.lastError.length > 0, @"corruption is visible");
            Require([[NSData dataWithContentsOfURL:file] isEqual:damaged], @"corrupt library preserved instead of silently replaced");
        } else return 2;
        puts("PASS");
    }
}
