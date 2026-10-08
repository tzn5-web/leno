#import <Foundation/Foundation.h>
void VDiagnosticsRecordPlayability(id status);
void VDiagnosticsRecordRequest(BOOL proofProvided, BOOL offline);
void VDiagnosticsRecordError(NSString *event, id error, id playerResponse);
NSString *VDiagnosticsReport(void);
