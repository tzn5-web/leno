#import "VGuestEntry.h"
#import <objc/message.h>
#import <objc/runtime.h>
#import <string.h>

static BOOL VMatch(id object, SEL selector, const char *type) {
    Method method = class_getInstanceMethod(object_getClass(object), selector);
    return method && strcmp(method_getTypeEncoding(method), type) == 0;
}

BOOL VGuestCompleteFirstTimeTransaction(id strategy, id transaction) {
    SEL future = @selector(setFutureIdentity:);
    SEL success = @selector(successBlockForTransaction:firstTime:);
    if (!transaction || !VMatch(transaction, future, "v24@0:8@16") ||
        !VMatch(strategy, success, "@?28@0:8@16B24")) return NO;
    // Reverse-checked against the native Continue as Guest implementation in
    // YouTube 20.21.6: nil future identity is converted into a real guest by the
    // native identity store; its success block commits AND finishes the coalescer.
    void (^completion)(void) = ((id (*)(id, SEL, id, BOOL))objc_msgSend)(strategy, success, transaction, YES);
    if (!completion) return NO;
    ((void (*)(id, SEL, id))objc_msgSend)(transaction, future, nil);
    completion();
    return YES;
}
