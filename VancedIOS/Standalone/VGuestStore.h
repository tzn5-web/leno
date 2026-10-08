#import <Foundation/Foundation.h>

@interface VGuestStore : NSObject
@property (nonatomic, readonly) NSString *lastError;
+ (instancetype)shared;
- (instancetype)initWithDirectory:(NSURL *)directory;
- (NSDictionary *)snapshot;
- (void)recordVideo:(NSDictionary *)record;
- (void)updateVideo:(NSString *)videoID position:(double)position;
- (void)flush;
- (void)saveVideo:(NSDictionary *)record inList:(NSString *)list;
- (void)removeVideo:(NSString *)videoID fromList:(NSString *)list;
- (void)createPlaylist:(NSString *)name;
- (void)deletePlaylist:(NSString *)name;
- (void)clearHistory;
@end
