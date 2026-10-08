#import "VUpdatePolicy.h"
#import <objc/runtime.h>
#import <string.h>

static _Bool VNo(__unused id object, __unused SEL selector) { return 0; }
static _Bool VYes(__unused id object, __unused SEL selector) { return 1; }
static id VNil(__unused id object, __unused SEL selector) { return nil; }
static void VSkip(__unused id object, __unused SEL selector) {}

static void VReplace(const char *name, const char *selector, const char *encoding, IMP replacement) {
    Class cls = objc_getClass(name);
    SEL sel = sel_registerName(selector);
    Method method = class_getInstanceMethod(cls, sel);
    if (!method || strcmp(method_getTypeEncoding(method), encoding)) return;
    if (!class_addMethod(cls, sel, replacement, encoding)) method_setImplementation(method, replacement);
}

void VInstallUpdatePolicy(void) {
    VReplace("YTGlobalConfig", "shouldBlockUpgradeDialog", "B16@0:8", (IMP)VYes);
    for (NSString *selector in @[@"shouldShowUpgradeDialog", @"shouldShowUpgrade", @"shouldForceUpgrade"])
        VReplace("YTGlobalConfig", selector.UTF8String, "B16@0:8", (IMP)VNo);
    // The renderer path in showUpgradeDialog does not check the flag above.
    VReplace("YTGlobalConfig", "upgradeDialog", "@16@0:8", (IMP)VNil);
    VReplace("YTUpgradeController", "showUpgradeDialog", "v16@0:8", (IMP)VSkip);
    VReplace("YTUpgradeController", "showOldUpgradeDialog", "v16@0:8", (IMP)VSkip);
    // Native startWork keeps its no-check branch and completes its worker.
    VReplace("YTUpgradeWorker", "isTimeForUpgradeCheck", "B16@0:8", (IMP)VNo);
}
