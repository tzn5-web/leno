#import <Foundation/Foundation.h>
#import "../VancedIdentity.m"

@interface FixtureSSO : NSObject
@property NSString *applicationScheme;
@property NSString *applicationIdentifier;
@property NSString *shortAppName;
- (id)initWithClientID:(id)client supportedAccountServices:(id)services;
@end
@implementation FixtureSSO
- (id)initWithClientID:(id)client supportedAccountServices:(id)services {
    if ((self = [super init])) {
        self.applicationScheme = @"com.google.sso.fixture-client";
        self.applicationIdentifier = @"ro.ion.youtubevanced";
    }
    return self;
}
@end

int main(void) {
    @autoreleasepool {
        SEL selector = @selector(initWithClientID:supportedAccountServices:);
        VOriginalSSOInit = class_getMethodImplementation(FixtureSSO.class, selector);
        FixtureSSO *object = VSSOInit([FixtureSSO alloc], selector, @"fixture-client", nil);
        if (![object.applicationScheme isEqual:@"com.google.sso.fixture-client"] ||
            ![object.applicationIdentifier isEqual:@"com.google.ios.youtube"] ||
            ![object.shortAppName isEqual:@"YouTube"]) return 1;
        NSString *osIdentity = NSBundle.mainBundle.bundleIdentifier ?: @"";
        if (![osIdentity isEqual:@"com.google.ios.youtube"]) puts("PASS");
        else return 1;
    }
}
