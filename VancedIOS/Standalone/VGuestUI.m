#import "VGuestUI.h"
#import "VGuestStore.h"
#import <objc/message.h>
#import <objc/runtime.h>
#import <math.h>

static NSDictionary *VCurrentRecord;
static __weak id VAppController;
void VGuestSetCurrentRecord(NSDictionary *record) { VCurrentRecord = [record copy]; }
void VGuestSetAppController(id controller) { VAppController = controller; }

static UIViewController *VTopController(void) {
    UIWindow *window;
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (![scene isKindOfClass:UIWindowScene.class] || scene.activationState != UISceneActivationStateForegroundActive) continue;
        for (UIWindow *candidate in ((UIWindowScene *)scene).windows) if (candidate.isKeyWindow) window = candidate;
    }
    UIViewController *controller = window.rootViewController;
    while (controller.presentedViewController && !controller.presentedViewController.isBeingDismissed) controller = controller.presentedViewController;
    if ([controller isKindOfClass:UINavigationController.class]) controller = ((UINavigationController *)controller).visibleViewController;
    return controller;
}

@interface VGuestLibraryController : UITableViewController
@property (nonatomic, copy) NSString *listName;
@property (nonatomic, copy) NSArray *rows;
@end

@implementation VGuestLibraryController
- (instancetype)initWithList:(NSString *)list title:(NSString *)title {
    if ((self = [super initWithStyle:UITableViewStyleInsetGrouped])) { self.listName = list; self.title = title; }
    return self;
}
- (void)viewDidLoad {
    [super viewDidLoad];
    self.tableView.rowHeight = UITableViewAutomaticDimension;
    self.tableView.estimatedRowHeight = 72;
    if (!self.listName) {
        self.navigationItem.leftBarButtonItem = [[UIBarButtonItem alloc] initWithBarButtonSystemItem:UIBarButtonSystemItemDone target:self action:@selector(close)];
        self.navigationItem.rightBarButtonItem = [[UIBarButtonItem alloc] initWithTitle:@"Salvează clipul" style:UIBarButtonItemStylePlain target:self action:@selector(saveCurrent)];
    } else if ([self.listName isEqual:@"playlists"]) {
        self.navigationItem.rightBarButtonItem = [[UIBarButtonItem alloc] initWithBarButtonSystemItem:UIBarButtonSystemItemAdd target:self action:@selector(newPlaylist)];
    }
}
- (void)viewWillAppear:(BOOL)animated { [super viewWillAppear:animated]; [self reload]; }
- (void)close { [self dismissViewControllerAnimated:YES completion:nil]; }
- (void)reload {
    NSDictionary *state = VGuestStore.shared.snapshot;
    if (!self.listName) self.rows = @[@"Istoric", @"Favorite", @"Mai târziu", @"Liste de redare", @"Pauză istoric", @"Șterge istoricul"];
    else if ([self.listName isEqual:@"playlists"]) self.rows = [state[@"playlists"] allKeys];
    else if ([self.listName hasPrefix:@"playlist:"]) self.rows = state[@"playlists"][[self.listName substringFromIndex:9]] ?: @[];
    else self.rows = state[self.listName] ?: @[];
    self.tableView.backgroundView = nil;
    if (!self.rows.count) {
        UILabel *empty = [[UILabel alloc] initWithFrame:self.tableView.bounds];
        empty.text = @"Niciun clip salvat încă.";
        empty.textColor = UIColor.secondaryLabelColor;
        empty.textAlignment = NSTextAlignmentCenter;
        self.tableView.backgroundView = empty;
    }
    [self.tableView reloadData];
}
- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section { return self.rows.count; }
- (NSString *)tableView:(UITableView *)tableView titleForFooterInSection:(NSInteger)section {
    if (VGuestStore.shared.lastError) return [@"Salvarea locală necesită atenție: " stringByAppendingString:VGuestStore.shared.lastError];
    return !self.listName ? @"Profil Guest local. Datele rămân în această aplicație, pe telefon. Nu se sincronizează cu Google și se pierd la dezinstalare. Favoritele și listele locale se gestionează aici." : nil;
}
- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)path {
    UITableViewCell *cell = [tableView dequeueReusableCellWithIdentifier:@"record"];
    if (!cell) cell = [[UITableViewCell alloc] initWithStyle:UITableViewCellStyleSubtitle reuseIdentifier:@"record"];
    cell.textLabel.numberOfLines = 2;
    cell.detailTextLabel.numberOfLines = 2;
    cell.textLabel.font = [UIFont preferredFontForTextStyle:UIFontTextStyleBody];
    cell.detailTextLabel.font = [UIFont preferredFontForTextStyle:UIFontTextStyleCaption1];
    cell.accessoryType = UITableViewCellAccessoryDisclosureIndicator;
    cell.detailTextLabel.text = nil;
    if (!self.listName || [self.listName isEqual:@"playlists"]) {
        cell.textLabel.text = self.rows[path.row];
        if (!self.listName && path.row == 4) {
            cell.accessoryType = [[NSUserDefaults standardUserDefaults] boolForKey:@"VancedGuestHistoryPaused"] ? UITableViewCellAccessoryCheckmark : UITableViewCellAccessoryNone;
        }
    } else {
        NSDictionary *record = self.rows[path.row];
        cell.textLabel.text = record[@"title"];
        NSUInteger position = MIN([record[@"position"] doubleValue], 8640000);
        cell.detailTextLabel.text = [NSString stringWithFormat:@"%@ · %lu:%02lu", record[@"author"], (unsigned long)position / 60, (unsigned long)position % 60];
        cell.accessoryType = UITableViewCellAccessoryDetailButton;
    }
    return cell;
}
- (void)tableView:(UITableView *)tableView didSelectRowAtIndexPath:(NSIndexPath *)path {
    [tableView deselectRowAtIndexPath:path animated:YES];
    if (!self.listName) {
        if (path.row < 4) {
            NSString *key = @[@"history", @"favorites", @"later", @"playlists"][path.row];
            [self.navigationController pushViewController:[[VGuestLibraryController alloc] initWithList:key title:self.rows[path.row]] animated:YES];
        } else if (path.row == 4) {
            NSUserDefaults *defaults = NSUserDefaults.standardUserDefaults;
            [defaults setBool:![defaults boolForKey:@"VancedGuestHistoryPaused"] forKey:@"VancedGuestHistoryPaused"];
            [self reload];
        } else {
            UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Ștergi istoricul local?" message:@"Favoritele și listele de redare vor fi păstrate." preferredStyle:UIAlertControllerStyleAlert];
            [alert addAction:[UIAlertAction actionWithTitle:@"Anulează" style:UIAlertActionStyleCancel handler:nil]];
            [alert addAction:[UIAlertAction actionWithTitle:@"Șterge" style:UIAlertActionStyleDestructive handler:^(UIAlertAction *action) { [VGuestStore.shared clearHistory]; [self reload]; }]];
            [self presentViewController:alert animated:YES completion:nil];
        }
    } else if ([self.listName isEqual:@"playlists"]) {
        NSString *name = self.rows[path.row];
        [self.navigationController pushViewController:[[VGuestLibraryController alloc] initWithList:[@"playlist:" stringByAppendingString:name] title:name] animated:YES];
    } else [self play:self.rows[path.row]];
}
- (void)play:(NSDictionary *)record {
    id controller = VAppController;
    if (!controller) {
        @try { controller = [UIApplication.sharedApplication.delegate valueForKey:@"_appViewController"]; } @catch (NSException *exception) {}
    }
    SEL selector = NSSelectorFromString(@"openURL:fromView:withCallbackURL:referringApp:trackingParams:isOriginExternal:shouldResolve:firstResponder:linkOpenerOptions:");
    Method method = class_getInstanceMethod(object_getClass(controller), selector);
    if (!method || strcmp(method_getTypeEncoding(method), "v80@0:8@16@24@32@40@48B56B60@64@72") != 0) {
        UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Clipul nu poate fi deschis automat" message:[@"Caută în YouTube codul: " stringByAppendingString:record[@"id"]] preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
        [self presentViewController:alert animated:YES completion:nil];
        return;
    }
    double position = [record[@"position"] doubleValue];
    NSUInteger seconds = isfinite(position) && position >= 0 ? MIN(position, 8640000) : 0;
    NSURL *url = [NSURL URLWithString:[NSString stringWithFormat:@"https://www.youtube.com/watch?v=%@&t=%lu", record[@"id"], (unsigned long)seconds]];
    [self dismissViewControllerAnimated:YES completion:^{
        // Invoke THIS app's internal URL navigator. Never ask iOS to open YouTube.
        ((void (*)(id, SEL, id, id, id, id, id, BOOL, BOOL, id, id))objc_msgSend)(controller, selector, url, nil, nil, nil, nil, NO, YES, controller, nil);
    }];
}
- (void)tableView:(UITableView *)tableView accessoryButtonTappedForRowWithIndexPath:(NSIndexPath *)path { [self actionsFor:self.rows[path.row]]; }
- (void)saveCurrent {
    if (VCurrentRecord) [self actionsFor:VCurrentRecord];
    else {
        UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Niciun clip activ" message:@"Deschide un clip înainte de a-l salva." preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
        [self presentViewController:alert animated:YES completion:nil];
    }
}
- (void)actionsFor:(NSDictionary *)record {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:record[@"title"] message:nil preferredStyle:UIAlertControllerStyleActionSheet];
    [alert addAction:[UIAlertAction actionWithTitle:@"Redă" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) { [self play:record]; }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Salvează la Favorite" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) { [VGuestStore.shared saveVideo:record inList:@"favorites"]; [self reload]; }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Salvează pentru mai târziu" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) { [VGuestStore.shared saveVideo:record inList:@"later"]; [self reload]; }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Adaugă într-o listă" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) { [self choosePlaylist:record]; }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Anulează" style:UIAlertActionStyleCancel handler:nil]];
    alert.popoverPresentationController.sourceView = self.view;
    alert.popoverPresentationController.sourceRect = CGRectMake(self.view.bounds.size.width / 2, self.view.bounds.size.height / 2, 1, 1);
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)choosePlaylist:(NSDictionary *)record {
    NSArray *names = [VGuestStore.shared.snapshot[@"playlists"] allKeys];
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Listă locală" message:names.count ? nil : @"Creează o listă din Biblioteca Guest → Liste de redare." preferredStyle:UIAlertControllerStyleAlert];
    for (NSString *name in names) [alert addAction:[UIAlertAction actionWithTitle:name style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) { [VGuestStore.shared saveVideo:record inList:[@"playlist:" stringByAppendingString:name]]; [self reload]; }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Anulează" style:UIAlertActionStyleCancel handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)newPlaylist {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Listă nouă" message:@"Alege un nume de până la 80 de caractere." preferredStyle:UIAlertControllerStyleAlert];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *field) { field.placeholder = @"Numele listei"; }];
    [alert addAction:[UIAlertAction actionWithTitle:@"Anulează" style:UIAlertActionStyleCancel handler:nil]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Creează" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) { [VGuestStore.shared createPlaylist:alert.textFields.firstObject.text]; [self reload]; }]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (BOOL)tableView:(UITableView *)tableView canEditRowAtIndexPath:(NSIndexPath *)path { return self.listName != nil; }
- (void)tableView:(UITableView *)tableView commitEditingStyle:(UITableViewCellEditingStyle)style forRowAtIndexPath:(NSIndexPath *)path {
    if (style != UITableViewCellEditingStyleDelete) return;
    if ([self.listName isEqual:@"playlists"]) [VGuestStore.shared deletePlaylist:self.rows[path.row]];
    else [VGuestStore.shared removeVideo:self.rows[path.row][@"id"] fromList:self.listName];
    [self reload];
}
@end

void VGuestPresentLibrary(void) {
    dispatch_async(dispatch_get_main_queue(), ^{
        UIViewController *top = VTopController();
        if (!top || [top isKindOfClass:VGuestLibraryController.class]) return;
        VGuestLibraryController *library = [[VGuestLibraryController alloc] initWithList:nil title:@"Biblioteca Guest"];
        [top presentViewController:[[UINavigationController alloc] initWithRootViewController:library] animated:YES completion:nil];
    });
}
