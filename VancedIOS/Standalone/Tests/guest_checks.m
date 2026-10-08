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

@interface TestStrategy : NSObject
@property NSUInteger completions;
@property BOOL firstTime;
@property BOOL nativeSignedIn;
- (void (^)(void))successBlockForTransaction:(TestTransaction *)transaction firstTime:(_Bool)first;
@end
@implementation TestStrategy
- (void (^)(void))successBlockForTransaction:(TestTransaction *)transaction firstTime:(_Bool)first {
    self.firstTime = first;
    return ^{ transaction.committed = YES; self.completions++; self.nativeSignedIn = transaction.futureIdentity != nil; };
}
@end

int main(int argc, const char **argv) {
    @autoreleasepool {
        Require(argc == 3, @"expected case and directory");
        NSString *mode = @(argv[1]);
        NSURL *root = [NSURL fileURLWithPath:@(argv[2]) isDirectory:YES];
        if ([mode isEqual:@"transaction"]) {
            TestStrategy *strategy = [TestStrategy new];
            TestTransaction *transaction = [TestTransaction new];
            transaction.futureIdentity = @"old pending identity";
            Require(VGuestCompleteFirstTimeTransaction(strategy, transaction), @"native guest completion available");
            Require(transaction.committed && transaction.futureIdentity == nil && strategy.firstTime && strategy.completions == 1 && !strategy.nativeSignedIn, @"guest commits once without faking login");
            Require(!VGuestCompleteFirstTimeTransaction([NSObject new], transaction), @"unsupported native ABI falls back");
            Require(!VGuestCompleteFirstTimeTransaction(strategy, nil), @"missing transaction falls back");
            Require(strategy.completions == 1, @"fallback does not invoke callbacks");
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
