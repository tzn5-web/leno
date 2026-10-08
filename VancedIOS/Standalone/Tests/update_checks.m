#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import "../VUpdatePolicy.h"

static void Require(BOOL ok, NSString *message) {
    if (!ok) { NSLog(@"FAIL: %@", message); exit(1); }
}
@interface YTGlobalConfig : NSObject
- (_Bool)shouldBlockUpgradeDialog;
- (_Bool)shouldShowUpgradeDialog;
- (_Bool)shouldShowUpgrade;
- (_Bool)shouldForceUpgrade;
- (id)upgradeDialog;
@end
@implementation YTGlobalConfig
- (_Bool)shouldBlockUpgradeDialog { return 0; }
- (_Bool)shouldShowUpgradeDialog { return 1; }
- (_Bool)shouldShowUpgrade { return 1; }
- (_Bool)shouldForceUpgrade { return 1; }
- (id)upgradeDialog { return @"server upgrade renderer"; }
@end
@interface YTUpgradeController : NSObject
@property NSUInteger dialogs;
- (void)showUpgradeDialog;
- (void)showOldUpgradeDialog;
- (void)requestUpgradeCheckWithCompletionBlock:(void (^)(void))block;
@end
@implementation YTUpgradeController
- (void)showUpgradeDialog { self.dialogs++; }
- (void)showOldUpgradeDialog { self.dialogs++; }
- (void)requestUpgradeCheckWithCompletionBlock:(void (^)(void))block { [self showUpgradeDialog]; block(); }
@end
@interface YTUpgradeWorker : NSObject
@property NSUInteger checks;
- (_Bool)isTimeForUpgradeCheck;
- (void)startWorkWithCompletionBlock:(void (^)(void))block errorBlock:(void (^)(void))error;
@end
@implementation YTUpgradeWorker
- (_Bool)isTimeForUpgradeCheck { return 1; }
- (void)startWorkWithCompletionBlock:(void (^)(void))block errorBlock:(void (^)(void))error {
    if ([self isTimeForUpgradeCheck]) self.checks++;
    block();
}
@end
int main(void) {
    @autoreleasepool {
        IMP worker = class_getMethodImplementation(YTUpgradeWorker.class, @selector(startWorkWithCompletionBlock:errorBlock:));
        IMP request = class_getMethodImplementation(YTUpgradeController.class, @selector(requestUpgradeCheckWithCompletionBlock:));
        VInstallUpdatePolicy();
        VInstallUpdatePolicy();
        YTGlobalConfig *config = [YTGlobalConfig new];
        Require(config.shouldBlockUpgradeDialog && !config.shouldShowUpgradeDialog && !config.shouldShowUpgrade && !config.shouldForceUpgrade && !config.upgradeDialog, @"upgrade flags and renderer suppressed");
        YTUpgradeController *controller = [YTUpgradeController new];
        __block NSUInteger completions = 0;
        [controller showOldUpgradeDialog];
        [controller requestUpgradeCheckWithCompletionBlock:^{ completions++; }];
        YTUpgradeWorker *runner = [YTUpgradeWorker new];
        [runner startWorkWithCompletionBlock:^{ completions++; } errorBlock:^{ exit(2); }];
        Require(controller.dialogs == 0 && runner.checks == 0 && completions == 2, @"no dialog or check; both native completions preserved");
        Require(worker == class_getMethodImplementation(YTUpgradeWorker.class, @selector(startWorkWithCompletionBlock:errorBlock:)) && request == class_getMethodImplementation(YTUpgradeController.class, @selector(requestUpgradeCheckWithCompletionBlock:)), @"worker and request lifecycle unchanged");
        puts("PASS");
    }
}
