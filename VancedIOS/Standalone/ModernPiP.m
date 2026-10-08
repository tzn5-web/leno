#import <Foundation/Foundation.h>

// This build targets iOS 15+. It keeps YouTube's modern sample-buffer PiP
// path and deliberately excludes the upstream compatibility code for iOS 11-14.
BOOL LegacyPiP(void) { return NO; }
