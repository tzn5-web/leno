#import "VDiagnostics.h"
#import <objc/message.h>
#import <objc/runtime.h>
#import <string.h>
#import <dispatch/dispatch.h>

static NSMutableArray *VEvents;
static NSObject *VEventLock;
static void VPrepare(void) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{ VEvents = [NSMutableArray array]; VEventLock = [NSObject new]; });
}

static id VObject(id object, const char *name) {
    SEL selector = sel_registerName(name);
    // GPB accessors are resolved dynamically. Do not interpret their absence
    // from static metadata as proof that they cannot be called at runtime.
    if (![object respondsToSelector:selector]) return nil;
    Method method = class_getInstanceMethod(object_getClass(object), selector);
    if (!method || method_getNumberOfArguments(method) != 2) return nil;
    char *type = method_copyReturnType(method);
    BOOL valid = type && type[0] == '@';
    free(type);
    return valid ? ((id (*)(id, SEL))objc_msgSend)(object, selector) : nil;
}

static NSString *VReason(id value) {
    if (![value isKindOfClass:NSString.class]) return nil;
    NSString *text = [value substringToIndex:MIN([value length], 512)];
    // Never retain a URL, email address or long credential-like string in a
    // free-form server message. Structured diagnostics omit all request bodies.
    static NSArray *filters;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NSMutableArray *compiled = [NSMutableArray array];
        for (NSString *pattern in @[@"https?://\\S+", @"[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}", @"[A-Z0-9_+/=-]{32,}"])
            [compiled addObject:[NSRegularExpression regularExpressionWithPattern:pattern options:NSRegularExpressionCaseInsensitive error:nil]];
        filters = compiled.copy;
    });
    for (NSRegularExpression *regex in filters) {
        text = [regex stringByReplacingMatchesInString:text options:0 range:NSMakeRange(0, text.length) withTemplate:@"[redactat]"];
    }
    return text;
}

static NSDictionary *VStatusFields(id status) {
    NSMutableDictionary *fields = [NSMutableDictionary dictionary];
    SEL selector = sel_registerName("status");
    if ([status respondsToSelector:selector]) {
        Method method = class_getInstanceMethod(object_getClass(status), selector);
        if (method && strcmp(method_getTypeEncoding(method), "i16@0:8") == 0)
            fields[@"status_code"] = @(((int (*)(id, SEL))objc_msgSend)(status, selector));
    }
    NSString *reason = VReason(VObject(status, "reason"));
    if (reason.length) fields[@"server_reason"] = reason;
    if (!fields.count) fields[@"status_accessors"] = @"unavailable";
    return fields;
}

static void VRecord(NSString *event, NSDictionary *fields) {
    VPrepare();
    @synchronized (VEventLock) {
        NSMutableDictionary *last = VEvents.lastObject;
        NSTimeInterval now = NSDate.timeIntervalSinceReferenceDate;
        if ([last[@"event"] isEqual:event] && [last[@"details"] isEqual:fields]) {
            last[@"count"] = @([last[@"count"] unsignedIntegerValue] + 1);
            last[@"last"] = @(now);
            return;
        }
        [VEvents addObject:[@{@"event":event, @"details":fields, @"first":@(now), @"last":@(now), @"count":@1} mutableCopy]];
        if (VEvents.count > 100) [VEvents removeObjectAtIndex:0];
    }
}

void VDiagnosticsRecordPlayability(id status) {
    VRecord(@"playability_denied", VStatusFields(status));
}

void VDiagnosticsRecordRequest(BOOL proofProvided, BOOL offline) {
    VRecord(@"player_request", @{@"proof_argument_nonnull":@(proofProvided), @"offline":@(offline)});
}

void VDiagnosticsRecordError(NSString *event, id error, id playerResponse) {
    NSMutableDictionary *fields = [NSMutableDictionary dictionary];
    if ([error isKindOfClass:NSError.class]) {
        fields[@"error_domain"] = VReason([(NSError *)error domain]) ?: @"unknown";
        fields[@"error_code"] = @([(NSError *)error code]);
        // localizedDescription/userInfo can contain account IDs or signed URLs.
        // Record only the domain and code, not the entire error object.
    } else if (error) fields[@"error_class"] = NSStringFromClass([error class]);
    id data = VObject(playerResponse, "playerData");
    id status = VObject(data, "playabilityStatus");
    if (status) [fields addEntriesFromDictionary:VStatusFields(status)];
    id streaming = VObject(data, "streamingData");
    id formats = VObject(streaming, "formatsArray");
    id adaptive = VObject(streaming, "adaptiveFormatsArray");
    if ([formats isKindOfClass:NSArray.class] || [adaptive isKindOfClass:NSArray.class])
        fields[@"stream_format_count"] = @(([formats isKindOfClass:NSArray.class] ? [formats count] : 0) + ([adaptive isKindOfClass:NSArray.class] ? [adaptive count] : 0));
    VRecord(event, fields);
}

NSString *VDiagnosticsReport(void) {
    VPrepare();
    NSData *json;
    @synchronized (VEventLock) {
        json = [NSJSONSerialization dataWithJSONObject:@{
            @"candidate":@"20.21.6-auth-diagnostics-v1",
            @"runtime_validation":@"NOT_CONFIRMED",
            @"bundle_id":NSBundle.mainBundle.bundleIdentifier ?: @"unknown",
            @"os":NSProcessInfo.processInfo.operatingSystemVersionString,
            @"events":VEvents,
            @"limits":@"Maximum 100 events in this process. No event does not prove success. A nonnull proof argument does not prove its validity. Server reasons are truncated and redacted."
        } options:NSJSONWritingPrettyPrinted error:nil];
    }
    return json ? [[NSString alloc] initWithData:json encoding:NSUTF8StringEncoding] : @"Raport indisponibil.";
}
