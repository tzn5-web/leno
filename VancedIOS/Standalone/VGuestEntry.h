#import <Foundation/Foundation.h>
BOOL VGuestCompleteWithoutPresentation(id controller);
void VGuestBeginAutomaticSignIn(void);
void VGuestEndAutomaticSignIn(void);
void VGuestBeginExplicitSignIn(void);
void VGuestEndExplicitSignIn(void);
void VGuestTagSignInTransaction(id transaction);
void VGuestRunSignIn(BOOL explicitRequest, void (^work)(void));
BOOL VGuestAcceptProgress(unsigned long long monotonicNanoseconds);
BOOL VGuestConfigureNativeHistory(id nativeDefaults);
