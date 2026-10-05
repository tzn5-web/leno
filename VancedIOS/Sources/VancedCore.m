#import <Foundation/Foundation.h>

__attribute__((constructor))
static void VancedCoreInitialize(void) {
    @autoreleasepool {
        NSString *bundleID = NSBundle.mainBundle.bundleIdentifier ?: @"";
        if (![bundleID.lowercaseString containsString:@"youtube"]) {
            return;
        }
        if ([[NSUserDefaults standardUserDefaults] boolForKey:@"VancedDiagnosticsEnabled"]) {
            NSLog(@"[VancedCore] scaffold loaded in %@", bundleID);
        }
    }
}
