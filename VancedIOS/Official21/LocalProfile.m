#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
static NSString *const KName=@"VancedLocalName21";
static NSString *const KSaved=@"VancedLocalBookmarks21";
static char KButton;
static NSArray *Saved(void){
 id value=[NSUserDefaults.standardUserDefaults objectForKey:KSaved];
 return [value isKindOfClass:NSArray.class]?value:@[];
}
static NSString *VideoID(NSString *input){
 NSURLComponents *url=[NSURLComponents componentsWithString:input?:@""];
 NSString *host=url.host.lowercaseString, *identifier=nil;
 if([host isEqualToString:@"youtu.be"])identifier=[url.path stringByTrimmingCharactersInSet:[NSCharacterSet characterSetWithCharactersInString:@"/"]];
 else if([host isEqualToString:@"youtube.com"]||[host isEqualToString:@"www.youtube.com"]||[host isEqualToString:@"m.youtube.com"])
  for(NSURLQueryItem *item in url.queryItems)if([item.name isEqualToString:@"v"])identifier=item.value;
 if(identifier.length!=11)return nil;
 NSCharacterSet *allowed=[NSCharacterSet characterSetWithCharactersInString:@"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"];
 return [identifier rangeOfCharacterFromSet:allowed.invertedSet].location==NSNotFound?identifier:nil;
}
@interface VLocalController:UITableViewController
@property(nonatomic,copy) NSArray *videos;
@end
@implementation VLocalController
-(void)viewDidLoad{
 [super viewDidLoad];
 self.title=@"Profil local";self.videos=Saved();
 self.navigationItem.leftBarButtonItem=[[UIBarButtonItem alloc]initWithBarButtonSystemItem:UIBarButtonSystemItemDone target:self action:@selector(close)];
}
-(void)close{[self dismissViewControllerAnimated:YES completion:nil];}
-(NSInteger)numberOfSectionsInTableView:(UITableView *)t{(void)t;return 2;}
-(NSInteger)tableView:(UITableView *)t numberOfRowsInSection:(NSInteger)s{(void)t;return s?(NSInteger)self.videos.count:2;}
-(NSString *)tableView:(UITableView *)t titleForHeaderInSection:(NSInteger)s{(void)t;return s?@"Linkuri salvate local":@"Identitate locală";}
-(NSString *)tableView:(UITableView *)t titleForFooterInSection:(NSInteger)s{
 (void)t;return s?nil:@"Fără token Google, abonament Premium sau sincronizare cu serverul.";
}
-(UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)p{
 UITableViewCell *cell=[tableView dequeueReusableCellWithIdentifier:@"VLocalCell"];
 if(!cell)cell=[[UITableViewCell alloc]initWithStyle:UITableViewCellStyleSubtitle reuseIdentifier:@"VLocalCell"];
 cell.accessoryType=UITableViewCellAccessoryDisclosureIndicator;
 if(p.section){cell.textLabel.text=self.videos[(NSUInteger)p.row];cell.detailTextLabel.text=@"Copiază linkul";}
 else if(p.row==0){
  cell.textLabel.text=[NSUserDefaults.standardUserDefaults stringForKey:KName]?:@"Utilizator local";
  cell.detailTextLabel.text=@"Modifică numele";
 }else{
  cell.textLabel.text=@"Adaugă din clipboard";cell.detailTextLabel.text=@"Copiază un URL YouTube înainte";
 }
 return cell;
}
-(void)message:(NSString *)info{
 UIAlertController *dialog=[UIAlertController alertControllerWithTitle:@"Profil local" message:info preferredStyle:UIAlertControllerStyleAlert];
 [dialog addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
 [self presentViewController:dialog animated:YES completion:nil];
}
-(void)tableView:(UITableView *)tableView didSelectRowAtIndexPath:(NSIndexPath *)p{
 [tableView deselectRowAtIndexPath:p animated:YES];
 if(p.section){
  UIPasteboard.generalPasteboard.string=[@"https://www.youtube.com/watch?v=" stringByAppendingString:self.videos[(NSUInteger)p.row]];
  [self message:@"Link copiat"];return;
 }
 if(p.row==1){
  NSString *video=VideoID(UIPasteboard.generalPasteboard.string);
  if(!video){[self message:@"URL YouTube invalid"];return;}
  NSMutableArray *a=Saved().mutableCopy;
  if(![a containsObject:video])[a insertObject:video atIndex:0];
  if(a.count>500)[a removeObjectsInRange:NSMakeRange(500,a.count-500)];
  [NSUserDefaults.standardUserDefaults setObject:a forKey:KSaved];
  self.videos=a.copy;[self.tableView reloadData];return;
 }
 UIAlertController *dialog=[UIAlertController alertControllerWithTitle:@"Nume local" message:nil preferredStyle:UIAlertControllerStyleAlert];
 [dialog addTextFieldWithConfigurationHandler:^(UITextField *field){field.placeholder=@"Utilizator local";}];
 [dialog addAction:[UIAlertAction actionWithTitle:@"Anulează" style:UIAlertActionStyleCancel handler:nil]];
 __weak typeof(self) weakSelf=self;
 [dialog addAction:[UIAlertAction actionWithTitle:@"Salvează" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action){
  NSString *name=[dialog.textFields.firstObject.text stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
  if(name.length>0&&name.length<=48)[NSUserDefaults.standardUserDefaults setObject:name forKey:KName];
  [weakSelf.tableView reloadData];
 }]];
 [self presentViewController:dialog animated:YES completion:nil];
}
@end
@interface VLocalButton:UIButton
@end
@implementation VLocalButton
-(void)showProfile:(UIButton *)sender{
 UIWindow *window=(UIWindow *)sender.superview;
 if(![window isKindOfClass:UIWindow.class])return;
 UIViewController *top=window.rootViewController;
 while(top.presentedViewController)top=top.presentedViewController;
 if(top)[top presentViewController:[[UINavigationController alloc]initWithRootViewController:[VLocalController new]] animated:YES completion:nil];
}
@end
static void Attach(void){
 if(!NSThread.isMainThread){dispatch_async(dispatch_get_main_queue(),^{Attach();});return;}
 for(UIScene *scene in UIApplication.sharedApplication.connectedScenes){
  if(![scene isKindOfClass:UIWindowScene.class]||scene.activationState!=UISceneActivationStateForegroundActive)continue;
  for(UIWindow *window in ((UIWindowScene *)scene).windows){
   if(!window.isKeyWindow||window.hidden||objc_getAssociatedObject(window,&KButton))continue;
   VLocalButton *button=[VLocalButton buttonWithType:UIButtonTypeSystem];
   [button setTitle:@"LOCAL" forState:UIControlStateNormal];
   button.frame=CGRectMake(MAX(8,CGRectGetWidth(window.bounds)-75),MAX(14,CGRectGetHeight(window.bounds)-window.safeAreaInsets.bottom-125),65,28);
   button.backgroundColor=UIColor.secondarySystemBackgroundColor;
   button.layer.cornerRadius=10;
   button.autoresizingMask=UIViewAutoresizingFlexibleLeftMargin|UIViewAutoresizingFlexibleTopMargin;
   [button addTarget:button action:@selector(showProfile:) forControlEvents:UIControlEventTouchUpInside];
   [window addSubview:button];
   objc_setAssociatedObject(window,&KButton,button,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
  }
 }
}
__attribute__((constructor)) static void Setup(void){
 @autoreleasepool{
  [NSNotificationCenter.defaultCenter addObserverForName:UIApplicationDidBecomeActiveNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(__unused NSNotification *n){Attach();}];
  [NSNotificationCenter.defaultCenter addObserverForName:UIWindowDidBecomeKeyNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(__unused NSNotification *n){Attach();}];
  dispatch_async(dispatch_get_main_queue(),^{Attach();});
 }
}
