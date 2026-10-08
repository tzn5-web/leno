#import "VGuestEntry.h"
#import <objc/message.h>
#import <objc/runtime.h>
#import <string.h>
#import <stdatomic.h>

static BOOL VMatch(id object, SEL selector, const char *type) {
    Method method = class_getInstanceMethod(object_getClass(object), selector);
    return method && strcmp(method_getTypeEncoding(method), type) == 0;
}

static id VObjectIvar(id object, const char *name, const char *type) {
    Ivar ivar = class_getInstanceVariable(object_getClass(object), name);
    const char *encoding = ivar ? ivar_getTypeEncoding(ivar) : NULL;
    if (!encoding || (type ? strcmp(encoding, type) != 0 : encoding[0] != '@')) return nil;
    return object_getIvar(object, ivar);
}

BOOL VGuestCompleteWithoutPresentation(id controller) {
    id transaction = VObjectIvar(controller, "_transaction", NULL);
    id state = VObjectIvar(controller, "_stateController", NULL);
    void (^completion)(void) = VObjectIvar(controller, "_successBlock", "@?");
    SEL future = @selector(setFutureIdentityForGoogleAccount:accountItem:);
    SEL ended = @selector(endedSignIn);
    SEL show = @selector(showViewController);
    if (!transaction || !state || !completion ||
        !VMatch(controller, future, "v32@0:8@16@24") ||
        !VMatch(state, ended, "v16@0:8") || !VMatch(state, show, "v16@0:8")) return NO;
    static char completedKey;
    if (objc_getAssociatedObject(controller, &completedKey) == transaction) return YES;
    objc_setAssociatedObject(controller, &completedKey, transaction, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    // Native launchSignIn already installed the transaction and callbacks.
    // Continue as Guest sets nil future identity and invokes this native block.
    // No dismissal event is sent: no sign-in view was ever presented.
    ((void (*)(id, SEL, id, id))objc_msgSend)(controller, future, nil, nil);
    completion();
    // The previous shortcut skipped both native state-controller operations.
    ((void (*)(id, SEL))objc_msgSend)(state, ended);
    ((void (*)(id, SEL))objc_msgSend)(state, show);
    return YES;
}

BOOL VGuestAcceptProgress(unsigned long long now) {
    static _Atomic unsigned long long next;
    unsigned long long expected = atomic_load_explicit(&next, memory_order_relaxed);
    if (now < expected) return NO;
    return atomic_compare_exchange_strong_explicit(&next, &expected, now + 1000000000ULL,
                                                  memory_order_relaxed, memory_order_relaxed);
}
