#import "VGuestStore.h"
#import <math.h>
#import <TargetConditionals.h>

@implementation VGuestStore {
    NSURL *_file;
    NSMutableDictionary *_state;
    NSString *_lastError;
    BOOL _readOnly;
    BOOL _dirty;
}

+ (instancetype)shared {
    static VGuestStore *store;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NSURL *root = [[NSFileManager defaultManager] URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask].firstObject;
        store = [[self alloc] initWithDirectory:[root URLByAppendingPathComponent:@"VancedGuest" isDirectory:YES]];
    });
    return store;
}

- (instancetype)initWithDirectory:(NSURL *)directory {
    if (!(self = [super init])) return nil;
    _file = [directory URLByAppendingPathComponent:@"library.json"];
    _state = [@{@"schema":@1, @"history":[NSMutableArray array], @"favorites":[NSMutableArray array],
                @"later":[NSMutableArray array], @"playlists":[NSMutableDictionary dictionary]} mutableCopy];
    NSError *error;
    if (!directory || ![[NSFileManager defaultManager] createDirectoryAtURL:directory withIntermediateDirectories:YES attributes:nil error:&error]) {
        _lastError = error.localizedDescription ?: @"Folderul bibliotecii nu poate fi creat.";
        _readOnly = YES;
        return self;
    }
    if ([[NSFileManager defaultManager] fileExistsAtPath:_file.path]) {
        NSData *data = [NSData dataWithContentsOfURL:_file options:0 error:&error];
        id loaded = data ? [NSJSONSerialization JSONObjectWithData:data options:NSJSONReadingMutableContainers error:&error] : nil;
        BOOL valid = [loaded isKindOfClass:NSDictionary.class] && [loaded[@"schema"] isEqual:@1];
        for (NSString *key in @[@"history", @"favorites", @"later"]) {
            id rows = valid ? loaded[key] : nil;
            valid = valid && [rows isKindOfClass:NSArray.class] && [rows count] <= 1000;
            for (id row in valid ? rows : @[]) if (![self cleanRecord:row]) valid = NO;
        }
        id playlists = valid ? loaded[@"playlists"] : nil;
        valid = valid && [playlists isKindOfClass:NSDictionary.class] && [playlists count] <= 100;
        for (id name in valid ? playlists : @{}) {
            id rows = playlists[name];
            if (![name isKindOfClass:NSString.class] || ![name length] || [name length] > 80 ||
                ![rows isKindOfClass:NSArray.class] || [rows count] > 1000) { valid = NO; break; }
            for (id row in rows) if (![self cleanRecord:row]) valid = NO;
        }
        if (valid) {
            for (NSString *key in @[@"history", @"favorites", @"later"]) {
                NSMutableArray *rows = [NSMutableArray array];
                for (id row in loaded[key]) [rows addObject:[self cleanRecord:row]];
                loaded[key] = rows;
            }
            for (NSString *name in [playlists allKeys]) {
                NSMutableArray *rows = [NSMutableArray array];
                for (id row in playlists[name]) [rows addObject:[self cleanRecord:row]];
                playlists[name] = rows;
            }
            _state = loaded;
        }
        else {
            // Preserve a damaged or unsupported library rather than replacing it.
            _lastError = error.localizedDescription ?: @"Biblioteca existentă nu poate fi citită. Fișierul a fost păstrat.";
            _readOnly = YES;
        }
    }
    return self;
}

- (NSString *)lastError { @synchronized (self) { return _lastError; } }

- (NSDictionary *)cleanRecord:(id)value {
    if (![value isKindOfClass:NSDictionary.class]) return nil;
    NSString *videoID = value[@"id"];
    if (![videoID isKindOfClass:NSString.class] || videoID.length != 11) return nil;
    NSCharacterSet *allowed = [NSCharacterSet characterSetWithCharactersInString:@"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"];
    if ([videoID rangeOfCharacterFromSet:allowed.invertedSet].location != NSNotFound) return nil;
    NSMutableDictionary *record = [@{@"id":videoID} mutableCopy];
    for (NSString *key in @[@"title", @"author", @"channel"]) {
        id text = value[key];
        record[key] = [text isKindOfClass:NSString.class] ? [text substringToIndex:MIN([text length], 2048)] : @"";
    }
    if (![record[@"title"] length]) record[@"title"] = videoID;
    for (NSString *key in @[@"position", @"seen"]) {
        id number = value[key];
        double n = [number isKindOfClass:NSNumber.class] ? [number doubleValue] : 0;
        record[key] = @(isfinite(n) && n >= 0 ? n : 0);
    }
    return record;
}

- (NSDictionary *)snapshot {
    @synchronized (self) {
        NSData *data = [NSJSONSerialization dataWithJSONObject:_state options:0 error:nil];
        return [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    }
}

- (NSMutableArray *)list:(NSString *)name {
    if ([@[@"history", @"favorites", @"later"] containsObject:name]) return _state[name];
    if ([name hasPrefix:@"playlist:"]) return _state[@"playlists"][[name substringFromIndex:9]];
    return nil;
}

- (void)flush {
    @synchronized (self) {
        if (_readOnly || !_dirty) return;
        NSError *error;
        NSData *data = [NSJSONSerialization dataWithJSONObject:_state options:0 error:&error];
        NSDataWritingOptions options = NSDataWritingAtomic;
#if TARGET_OS_IPHONE
        options |= NSDataWritingFileProtectionCompleteUntilFirstUserAuthentication;
#endif
        if (data && [data writeToURL:_file options:options error:&error]) { _dirty = NO; _lastError = nil; }
        else _lastError = error.localizedDescription ?: @"Biblioteca nu a putut fi salvată.";
    }
}

- (void)recordVideo:(NSDictionary *)value {
    @synchronized (self) {
        NSMutableDictionary *record = [[self cleanRecord:value] mutableCopy];
        if (!record || _readOnly) return;
        NSMutableArray *history = _state[@"history"];
        NSDictionary *previous = nil;
        for (NSDictionary *row in history) if ([row[@"id"] isEqual:record[@"id"]]) { previous = row; break; }
        // Metadata callbacks must not erase a saved playback position.
        if (previous && [record[@"position"] doubleValue] == 0) record[@"position"] = previous[@"position"];
        record[@"seen"] = @([NSDate date].timeIntervalSince1970);
        [history filterUsingPredicate:[NSPredicate predicateWithBlock:^BOOL(NSDictionary *row, NSDictionary *bindings) { return ![row[@"id"] isEqual:record[@"id"]]; }]];
        [history insertObject:record atIndex:0];
        if (history.count > 1000) [history removeObjectsInRange:NSMakeRange(1000, history.count - 1000)];
        _dirty = YES;
        [self flush];
    }
}

- (void)updateVideo:(NSString *)videoID position:(double)position {
    if (!isfinite(position) || position < 0) return;
    @synchronized (self) {
        if (_readOnly) return;
        NSMutableArray *history = _state[@"history"];
        for (NSUInteger i = 0; i < history.count; ++i) {
            if (![history[i][@"id"] isEqual:videoID]) continue;
            NSMutableDictionary *row = [history[i] mutableCopy];
            row[@"position"] = @(position);
            history[i] = row;
            _dirty = YES;
            break;
        }
    }
}

- (void)saveVideo:(NSDictionary *)value inList:(NSString *)name {
    @synchronized (self) {
        NSDictionary *record = [self cleanRecord:value];
        NSMutableArray *list = [self list:name];
        if (_readOnly || !record || !list) return;
        [list filterUsingPredicate:[NSPredicate predicateWithBlock:^BOOL(NSDictionary *row, NSDictionary *bindings) { return ![row[@"id"] isEqual:record[@"id"]]; }]];
        [list insertObject:record atIndex:0];
        if (list.count > 1000) [list removeLastObject];
        _dirty = YES;
        [self flush];
    }
}

- (void)removeVideo:(NSString *)videoID fromList:(NSString *)name {
    @synchronized (self) {
        if (_readOnly) return;
        [[self list:name] filterUsingPredicate:[NSPredicate predicateWithBlock:^BOOL(NSDictionary *row, NSDictionary *bindings) { return ![row[@"id"] isEqual:videoID]; }]];
        _dirty = YES;
        [self flush];
    }
}

- (void)createPlaylist:(NSString *)name {
    @synchronized (self) {
        name = [name stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
        NSMutableDictionary *lists = _state[@"playlists"];
        if (_readOnly || !name.length || name.length > 80 || lists.count >= 100 || lists[name]) return;
        lists[name] = [NSMutableArray array];
        _dirty = YES;
        [self flush];
    }
}

- (void)deletePlaylist:(NSString *)name {
    @synchronized (self) {
        if (_readOnly) return;
        [_state[@"playlists"] removeObjectForKey:name];
        _dirty = YES;
        [self flush];
    }
}

- (void)clearHistory {
    @synchronized (self) {
        if (_readOnly) return;
        [_state[@"history"] removeAllObjects];
        _dirty = YES;
        [self flush];
    }
}
@end
