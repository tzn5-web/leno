package ro.evolauncher.k2401;
import android.app.*;import android.content.*;import android.graphics.*;import android.media.*;import android.media.session.*;import android.net.*;import android.os.*;import android.provider.*;import android.view.*;import java.lang.ref.*;import java.text.*;import java.util.*;
public final class MainActivity extends Activity {
  static WeakReference<MainActivity> active=new WeakReference<>(null);
  Handler handler=new Handler(); MediaController media; Dashboard view; ObdReader obd; LiveMapPanel liveMap; LauncherSettings launcherSettings; ShortcutDock shortcutDock; android.widget.FrameLayout stage; android.widget.TextView mapRecoveryPlaceholder; int page=0; String mediaPackage=""; String mediaName="Alege playerul";
  final MediaController.Callback mediaCallback=new MediaController.Callback(){@Override public void onPlaybackStateChanged(PlaybackState s){if(view!=null)view.invalidate();}@Override public void onMetadataChanged(MediaMetadata m){if(view!=null)view.invalidate();}@Override public void onSessionDestroyed(){refresh();if(view!=null)view.invalidate();}};
  final Runnable update=new Runnable(){public void run(){if(media==null)refresh();if(view!=null)view.invalidate();handler.postDelayed(this,1000);}};
  private final Runnable mapBootConfirmed=()->getSharedPreferences("evo_startup_recovery",MODE_PRIVATE)
    .edit().putBoolean("map_boot_pending",false).apply();
  void retryEmbeddedMap(){
    getSharedPreferences("evo_startup_recovery",MODE_PRIVATE).edit()
      .putBoolean("map_disabled",false).putBoolean("map_boot_pending",false)
      .remove("last_crash_wallclock").commit();
    recreate();
  }

  public void onCreate(Bundle state){super.onCreate(state);try{
    // A physical K2401 can crash before emulator-only checks reproduce the OEM
    // driver problem. Recovery is a separate Activity without maps or Bluetooth.
    long last=getSharedPreferences("evo_startup_recovery",MODE_PRIVATE).getLong("last_crash_wallclock",0L);
    if(last>0&&System.currentTimeMillis()-last<180000L){
      startActivity(new Intent(this,SafeModeActivity.class));finish();return;
    }
    getWindow().getDecorView().setSystemUiVisibility(5894|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);mediaPackage=getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE).getString("evo_media_package","");
   mediaName=labelForMedia(mediaPackage);launcherSettings=new LauncherSettings(this,()->{if(view!=null)view.invalidate();});view=new Dashboard();obd=new ObdReader(this,()->runOnUiThread(()->{if(view!=null)view.invalidate();}));stage=new android.widget.FrameLayout(this);stage.addView(view,new android.widget.FrameLayout.LayoutParams(-1,-1));
   // Do not allow an OEM-only map renderer failure to prevent all launcher UI.
   // A pending map boot after a process crash automatically disables only map.
   SharedPreferences mapRecovery=getSharedPreferences("evo_startup_recovery",MODE_PRIVATE);
   boolean previouslyPending=mapRecovery.getBoolean("map_boot_pending",false);
   boolean disabled=mapRecovery.getBoolean("map_disabled",false)||previouslyPending;
   if(previouslyPending)mapRecovery.edit().putBoolean("map_disabled",true)
      .putBoolean("map_boot_pending",false).commit();
   if(!disabled){
     mapRecovery.edit().putBoolean("map_boot_pending",true).commit();
     try{
       liveMap=new LiveMapPanel(this);
       stage.addView(liveMap,new android.widget.FrameLayout.LayoutParams(200,200));
     }catch(RuntimeException|LinkageError rendererFailure){
       mapRecovery.edit().putString("map_renderer_error",
         rendererFailure.toString()).putBoolean("map_disabled",true)
         .putBoolean("map_boot_pending",false).commit();
       liveMap=null;
     }
   }
   if(liveMap==null){
     mapRecoveryPlaceholder=new android.widget.TextView(this);
     mapRecoveryPlaceholder.setText("HARTĂ TEMPORAR DEZACTIVATĂ\nPORNIRE RECUPERATĂ\nSetări EVO → Reîncearcă harta");
     mapRecoveryPlaceholder.setTextColor(0xfff1f4fb);
     mapRecoveryPlaceholder.setTextSize(20);
     mapRecoveryPlaceholder.setGravity(android.view.Gravity.CENTER);
     mapRecoveryPlaceholder.setBackgroundColor(0xff15202d);
     stage.addView(mapRecoveryPlaceholder,new android.widget.FrameLayout.LayoutParams(200,200));
   }
   shortcutDock=new ShortcutDock(this);stage.addView(shortcutDock,new android.widget.FrameLayout.LayoutParams(200,100));stage.addView(launcherSettings,new android.widget.FrameLayout.LayoutParams(200,200));stage.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or2,ob)->placeMap());setContentView(stage);active=new WeakReference<>(this);placeMap();
    }catch(RuntimeException|LinkageError failure){
      // A Java failure during widget / GPU / OEM view setup must not cause
      // an endless HOME crash loop. The independent recovery UI remains usable.
      try{
        java.io.StringWriter trace=new java.io.StringWriter();
        failure.printStackTrace(new java.io.PrintWriter(trace));
        getSharedPreferences("evo_startup_recovery",MODE_PRIVATE).edit()
          .putString("last_exception",trace.toString())
          .putLong("last_crash_wallclock",System.currentTimeMillis())
          .putBoolean("map_disabled",true).putBoolean("map_boot_pending",false).commit();
        startActivity(new Intent(this,SafeModeActivity.class));
      }catch(RuntimeException ignored){}
      finish();
    }
  }
  protected void onStart(){super.onStart();if(liveMap!=null){
    try{liveMap.onHostStart();}catch(RuntimeException|LinkageError e){disableMapRenderer(e);}
  }}
  protected void onResume(){super.onResume();if(isFinishing()||stage==null)return;if(liveMap!=null)try{liveMap.onHostResume();}catch(RuntimeException|LinkageError e){disableMapRenderer(e);}handler.removeCallbacks(mapBootConfirmed);if(liveMap!=null)handler.postDelayed(mapBootConfirmed,1000);refresh();handler.removeCallbacks(update);handler.post(update);startObd();if(checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)!=android.content.pm.PackageManager.PERMISSION_GRANTED&&checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)!=android.content.pm.PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{android.Manifest.permission.ACCESS_FINE_LOCATION,android.Manifest.permission.ACCESS_COARSE_LOCATION},2402);}}
  protected void onPause(){handler.removeCallbacks(update);handler.removeCallbacks(mapBootConfirmed);if(liveMap!=null){getSharedPreferences("evo_startup_recovery",MODE_PRIVATE).edit().putBoolean("map_boot_pending",false).apply();}if(obd!=null)obd.stop();if(liveMap!=null)try{liveMap.onHostPause();}catch(RuntimeException|LinkageError e){disableMapRenderer(e);}super.onPause();}
  protected void onStop(){if(liveMap!=null)try{liveMap.onHostStop();}catch(RuntimeException|LinkageError e){disableMapRenderer(e);}super.onStop();}
  protected void onDestroy(){if(media!=null){try{media.unregisterCallback(mediaCallback);}catch(Exception ignored){}}if(obd!=null)obd.close();if(liveMap!=null)try{liveMap.onHostDestroy();}catch(RuntimeException|LinkageError ignored){}if(launcherSettings!=null)launcherSettings.dispose();active.clear();super.onDestroy();}
  void startObd(){
    // OEM-specific Android 10 Bluetooth drivers are NOT touched automatically
    // during initial startup. Enable only after the user chooses a paired ELM.
    if(obd!=null&&!getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE)
       .getBoolean("evo_skip_obd_at_start",true))obd.start();
  }
  @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grantResults){super.onRequestPermissionsResult(code,permissions,grantResults);if(code==2402&&liveMap!=null){liveMap.onHostPause();liveMap.onHostStart();}if(code==2401&&obd!=null){for(int result:grantResults)if(result!=android.content.pm.PackageManager.PERMISSION_GRANTED)return;if(grantResults.length>0)obd.start();}}
  @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(launcherSettings!=null)launcherSettings.onPicked(request,result,data);}
  public void onBackPressed(){if(view==null){super.onBackPressed();return;}page=0;view.invalidate();placeMap();}
  private void disableMapRenderer(Throwable problem){
    android.content.SharedPreferences recovery=getSharedPreferences("evo_startup_recovery",MODE_PRIVATE);
    recovery.edit().putBoolean("map_disabled",true).putBoolean("map_boot_pending",false)
      .putString("map_renderer_error",problem.toString()).commit();
    if(liveMap!=null&&stage!=null){
      try{stage.removeView(liveMap);}catch(RuntimeException ignored){}
    }
    liveMap=null;
    if(stage!=null&&mapRecoveryPlaceholder==null){
      mapRecoveryPlaceholder=new android.widget.TextView(this);
      mapRecoveryPlaceholder.setText("HARTĂ OPRITĂ PENTRU RECUPERARE\nSetări EVO → Reîncearcă harta");
      mapRecoveryPlaceholder.setTextColor(0xfff1f4fb);
      mapRecoveryPlaceholder.setTextSize(20);
      mapRecoveryPlaceholder.setGravity(android.view.Gravity.CENTER);
      mapRecoveryPlaceholder.setBackgroundColor(0xff15202d);
      stage.addView(mapRecoveryPlaceholder,new android.widget.FrameLayout.LayoutParams(200,200));
      placeMap();
    }
  }
  void placeMap(){if(stage==null||launcherSettings==null||shortcutDock==null)return;boolean shown=page==0||page==2;if(liveMap!=null)liveMap.setVisibility(shown?View.VISIBLE:View.GONE);if(mapRecoveryPlaceholder!=null)mapRecoveryPlaceholder.setVisibility(shown?View.VISIBLE:View.GONE);shortcutDock.setVisibility(page==0?View.VISIBLE:View.GONE);launcherSettings.setVisibility(page==5?View.VISIBLE:View.GONE);int w=stage.getWidth(),h=stage.getHeight();if(w<=0||h<=0)return;float sx=w/1280f,sy=h/720f;if(shown){int x=page==0?20:158,y=page==0?78:169,mw=page==0?600:1052,mh=page==0?490:527;android.widget.FrameLayout.LayoutParams p=new android.widget.FrameLayout.LayoutParams(Math.max(1,Math.round(mw*sx)),Math.max(1,Math.round(mh*sy)));p.leftMargin=Math.round(x*sx);p.topMargin=Math.round(y*sy);if(liveMap!=null)liveMap.setLayoutParams(p);if(mapRecoveryPlaceholder!=null)mapRecoveryPlaceholder.setLayoutParams(p);}android.widget.FrameLayout.LayoutParams dock=new android.widget.FrameLayout.LayoutParams(Math.max(1,Math.round(600*sx)),Math.max(1,Math.round(121*sy)));dock.leftMargin=Math.round(20*sx);dock.topMargin=Math.round(576*sy);shortcutDock.setLayoutParams(dock);android.widget.FrameLayout.LayoutParams prefs=new android.widget.FrameLayout.LayoutParams(Math.max(1,Math.round(1115*sx)),Math.max(1,Math.round(620*sy)));prefs.leftMargin=Math.round(130*sx);prefs.topMargin=Math.round(78*sy);launcherSettings.setLayoutParams(prefs);}
  static void changed(){MainActivity a=active.get();if(a!=null)a.runOnUiThread(()->{a.refresh();a.view.invalidate();});}
  String labelForMedia(String pkg){
    if(pkg==null||pkg.isEmpty())return "Alege playerul";
    try{return getPackageManager().getApplicationLabel(getPackageManager().getApplicationInfo(pkg,0)).toString();}
    catch(Exception e){return pkg;}
  }
  void choosePlayer(){
    // Android 10 target 28 exposes installed LAUNCHER activities. A Vanced /
    // ReVanced installation might use a customized package name.
    Intent query=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
    List<android.content.pm.ResolveInfo> available=getPackageManager().queryIntentActivities(query,0);
    ArrayList<String> pkgs=new ArrayList<>(); HashSet<String> seen=new HashSet<>();
    for(android.content.pm.ResolveInfo info:available){
      if(info.activityInfo==null)continue;
      String pkg=info.activityInfo.packageName;
      if(pkg.equals(getPackageName())||!seen.add(pkg)||getPackageManager().getLaunchIntentForPackage(pkg)==null)continue;
      pkgs.add(pkg);
    }
    Collections.sort(pkgs,(a,b)->{
      String an=labelForMedia(a).toLowerCase(Locale.ROOT);
      String bn=labelForMedia(b).toLowerCase(Locale.ROOT);
      int ar=(an.contains("vanced")||an.contains("revanced")||an.contains("youtube")||
          an.contains("music")||an.contains("poweramp")||an.contains("spotify")||
          an.contains("player")||an.contains("vlc"))?0:1;
      int br=(bn.contains("vanced")||bn.contains("revanced")||bn.contains("youtube")||
          bn.contains("music")||bn.contains("poweramp")||bn.contains("spotify")||
          bn.contains("player")||bn.contains("vlc"))?0:1;
      return ar!=br?Integer.compare(ar,br):an.compareToIgnoreCase(bn);
    });
    if(pkgs.isEmpty()){
      new AlertDialog.Builder(this).setTitle("Player media").setMessage("Nu au fost găsite aplicații lansabile.")
        .setPositiveButton("OK",null).show();return;
    }
    String[] labels=new String[pkgs.size()];
    int selected=-1;
    for(int n=0;n<pkgs.size();n++){labels[n]=labelForMedia(pkgs.get(n));if(mediaPackage.equals(pkgs.get(n)))selected=n;}
    new AlertDialog.Builder(this)
      .setTitle("Alege playerul instalat — Vanced / ReVanced / altele")
      .setSingleChoiceItems(labels,selected,(dialog,chosen)->{
         mediaPackage=pkgs.get(chosen);
         mediaName=labelForMedia(mediaPackage);
         getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE).edit().putString("evo_media_package",mediaPackage).commit();
         dialog.dismiss();refresh();if(view!=null)view.invalidate();
         if(media==null)mediaSetup();
      }).setNeutralButton("Permisiune MediaSession",(d,w)->permissions())
      .setNegativeButton("Anulează",null).show();
  }
  void mediaSetup(){
    refresh();
    boolean notificationAccess=(Settings.Secure.getString(getContentResolver(),"enabled_notification_listeners")!=null && Settings.Secure.getString(getContentResolver(),"enabled_notification_listeners").contains(getPackageName()));
    // The selected app must actually publish a MediaSession. For modified
    // YouTube clients this is application-dependent and cannot be fabricated.
    new AlertDialog.Builder(this).setTitle(mediaName)
      .setMessage("Sursă media: "+(mediaPackage.isEmpty()?"NESELECTAT":mediaPackage)+
        "\nAcces la notificări: "+(notificationAccess?"ACORDAT":"NEACORDAT")+
        "\nMediaSession detectată: "+(media!=null?"DA":"NU")+
        "\n\nDacă Morphe nu publică MediaSession, poți apăsa Play în panou pentru o comandă media Android de încercare. Sistemul nu garantează direcționarea către Morphe. Un control sigur necesită MediaSession publicată de aplicație.")
      .setPositiveButton("Acces notificări",(d,w)->permissions())
      .setNeutralButton("Deschide playerul o dată",(d,w)->{
        if(!mediaPackage.isEmpty())app(mediaPackage);else choosePlayer();
      })
      .setNegativeButton("Închide",null).show();
  }
  void refresh(){
    MediaController next=null;
    try{
      MediaSessionManager sessions=(MediaSessionManager)getSystemService(MEDIA_SESSION_SERVICE);
      List<MediaController> active=sessions.getActiveSessions(new ComponentName(this,MediaAccessService.class));
      for(MediaController c:active)if(mediaPackage.equals(c.getPackageName())){next=c;break;}
    }catch(RuntimeException ignored){}
    if(media!=null&&next!=null&&media.getSessionToken().equals(next.getSessionToken()))return;
    if(media!=null)try{media.unregisterCallback(mediaCallback);}catch(Exception ignored){}
    media=next;
    if(media!=null)media.registerCallback(mediaCallback,handler);
    if(view!=null)view.invalidate();
  }
  void app(String pkg){
    try{
      Intent i=getPackageManager().getLaunchIntentForPackage(pkg);
      if(i!=null){startActivity(i);return;}
      android.widget.Toast.makeText(this,"Aplicația nu este instalată. Alege o aplicație disponibilă.",android.widget.Toast.LENGTH_LONG).show();
    }catch(Exception ignored){android.widget.Toast.makeText(this,"Nu pot porni aplicația.",android.widget.Toast.LENGTH_LONG).show();}
  }
  // An explicit shortcut in the Apps screen may open Maps, but tapping the embedded map never does.
  void maps(){app("com.google.android.apps.maps");}
  private void dispatchFallbackMediaKey(int id){
    // Modified clients may not publish a MediaSession. Android's media-button
    // dispatch is the ONLY generic best-effort fallback. It is NOT an app-specific
    // API, and cannot guarantee that Morphe will receive or honor the command.
    // Never hijack controls when another app has an active media session.
    if(mediaPackage.isEmpty()){choosePlayer();return;}
    try{
      MediaSessionManager manager=(MediaSessionManager)getSystemService(MEDIA_SESSION_SERVICE);
      List<MediaController> active=manager.getActiveSessions(new ComponentName(this,MediaAccessService.class));
      for(MediaController controller:active){
        if(!mediaPackage.equals(controller.getPackageName())){
          android.widget.Toast.makeText(this,
            "Un alt player are sesiune activă. Nu redirecționez comenzile către el.",
            android.widget.Toast.LENGTH_LONG).show();
          return;
        }
      }
      AudioManager audio=(AudioManager)getSystemService(AUDIO_SERVICE);
      if(audio==null){mediaSetup();return;}
      int key=id==0?android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS:
        id==2?android.view.KeyEvent.KEYCODE_MEDIA_NEXT:
        android.view.KeyEvent.KEYCODE_MEDIA_PLAY;
      long when=SystemClock.uptimeMillis();
      audio.dispatchMediaKeyEvent(new android.view.KeyEvent(when,when,android.view.KeyEvent.ACTION_DOWN,key,0));
      audio.dispatchMediaKeyEvent(new android.view.KeyEvent(when,when,android.view.KeyEvent.ACTION_UP,key,0));
      handler.postDelayed(()->{refresh();if(media==null)
        android.widget.Toast.makeText(this,
          "Comanda media Android a fost trimisă, dar "+mediaName+" nu oferă încă o sesiune controlabilă.",
          android.widget.Toast.LENGTH_LONG).show();},1300);
    }catch(RuntimeException denied){mediaSetup();}
  }
  void mediaAction(int id){
    refresh();
    if(media==null){dispatchFallbackMediaKey(id);return;}
    try{
      MediaController.TransportControls t=media.getTransportControls();
      if(id==0)t.skipToPrevious();
      else if(id==2)t.skipToNext();
      else if(media.getPlaybackState()!=null&&media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING)t.pause();
      else t.play();
    }catch(RuntimeException unavailable){mediaSetup();}
    if(view!=null)view.invalidate();
  }
  void chooseObdSource(){
    final String[] labels={"ELM327 Bluetooth direct — și pentru Torque neoficial",
      "Torque Pro oficial — API plugin"};
    int current=obd!=null&&obd.isDirect()?0:1;
    new AlertDialog.Builder(this).setTitle("Alege sursa celor patru ceasuri")
      .setSingleChoiceItems(labels,current,(dialog,which)->{
        dialog.dismiss();
        if(obd==null)return;
        obd.setMode(which==0);
        if(which==0&&obd.adapterAddress().isEmpty())selectElmAdapter();
        if(view!=null)view.invalidate();
      }).setNegativeButton("Anulează",null).show();
  }
  private void selectObdDevice(String mac,boolean ble){
    if(obd==null)return;
    try{
      getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE).edit()
        .putBoolean("elm327_ble_hint",ble).commit();
      obd.chooseDirectAdapter(mac);
      getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE).edit()
        .putBoolean("evo_skip_obd_at_start",false).commit();
      android.widget.Toast.makeText(this,
        (ble?"BLE GATT":"Bluetooth Classic")+" ales. ECU este interogat direct; fără Torque.",
        android.widget.Toast.LENGTH_LONG).show();
      if(view!=null)view.invalidate();
    }catch(RuntimeException error){
      android.widget.Toast.makeText(this,"ELM327: "+error.getClass().getSimpleName(),
        android.widget.Toast.LENGTH_LONG).show();
    }
  }
  void selectElmAdapter(){
    android.bluetooth.BluetoothAdapter adapter=android.bluetooth.BluetoothAdapter.getDefaultAdapter();
    if(adapter==null){
      new AlertDialog.Builder(this).setTitle("ELM327")
        .setMessage("Android nu oferă un adaptor Bluetooth.")
        .setPositiveButton("OK",null).show();return;
    }
    if(!adapter.isEnabled()){
      new AlertDialog.Builder(this).setTitle("Bluetooth oprit")
        .setMessage("Activează Bluetooth și apoi configurează ELM327.")
        .setPositiveButton("Setări Bluetooth",(d,w)->startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS)))
        .setNegativeButton("Închide",null).show();return;
    }
    ArrayList<android.bluetooth.BluetoothDevice> paired=new ArrayList<>();
    try{paired.addAll(adapter.getBondedDevices());}
    catch(RuntimeException e){
      android.widget.Toast.makeText(this,"Firmware Bluetooth: "+e.getMessage(),
        android.widget.Toast.LENGTH_LONG).show();
    }
    Collections.sort(paired,(a,b)->{
      String x=a.getName()==null?"":a.getName(),y=b.getName()==null?"":b.getName();
      return x.compareToIgnoreCase(y);
    });
    // BLE UART devices commonly do NOT appear in the Android bonded list.
    // Offer an explicit bounded BLE scan; never connect to arbitrary devices.
    String[] items=new String[paired.size()+3];
    for(int i=0;i<paired.size();i++){
      android.bluetooth.BluetoothDevice d=paired.get(i);
      String name=d.getName()==null?"Bluetooth":d.getName();
      items[i]=name+" • "+d.getAddress()+" (asociat)";
    }
    items[paired.size()]="Caută ELM327 Bluetooth Classic (OBDII, ELM327, V-LINK)";
    items[paired.size()+1]="Caută ELM327 Bluetooth BLE (GATT)";
    items[paired.size()+2]="Diagnostic modul Bluetooth al navigației";
    new AlertDialog.Builder(this).setTitle("Alege ELM327 • Classic / BLE")
      .setMessage("BLE și Bluetooth Classic sunt diferite. Majoritatea adaptoarelor ELM327 clasice trebuie asociate prin PIN 1234/0000. Dispozitive Android asociate: "+paired.size())
      .setItems(items,(dialog,which)->{
        if(which==paired.size())scanClassicAdapters();
        else if(which==paired.size()+1)scanBleAdapters();
        else if(which==paired.size()+2)showBluetoothDiagnosis();
        else selectObdDevice(paired.get(which).getAddress(),false);
      }).setNegativeButton("Închide",null).show();
  }
  void scanClassicAdapters(){
    // Explicit Classic search + Android pairing. An empty BLE scan must not
    // send the driver through more BLE retries for a Classic-only ELM327.
    new ClassicObdDiscovery(this,mac->selectObdDevice(mac,false)).begin();
  }
  void showBluetoothDiagnosis(){
    android.bluetooth.BluetoothAdapter bt=android.bluetooth.BluetoothAdapter.getDefaultAdapter();
    StringBuilder msg=new StringBuilder();
    if(bt==null){msg.append("Android BluetoothAdapter: ABSENT\\n");}
    else{
      msg.append("Adapter Android: ").append(bt.isEnabled()?"ON":"OFF").append("\\n");
      msg.append("LE advertising/scanning: ")
        .append(getPackageManager().hasSystemFeature("android.hardware.bluetooth_le")?"DECLARED":"NOT DECLARED")
        .append("\\n");
      int bondedCount=-1;
      try{bondedCount=bt.getBondedDevices().size();}
      catch(RuntimeException e){msg.append("getBondedDevices: ").append(e.getClass().getSimpleName()).append("\\n");}
      msg.append("Dispozitive asociate Android: ").append(bondedCount).append("\\n");
      if(bondedCount>0)try{
        for(android.bluetooth.BluetoothDevice device:bt.getBondedDevices()){
          String name=device.getName()==null?"necunoscut":device.getName();
          msg.append(" • ").append(name).append(" — tip ")
            .append(device.getType()==android.bluetooth.BluetoothDevice.DEVICE_TYPE_LE?"BLE":
                    device.getType()==android.bluetooth.BluetoothDevice.DEVICE_TYPE_DUAL?"DUAL":
                    device.getType()==android.bluetooth.BluetoothDevice.DEVICE_TYPE_CLASSIC?"CLASSIC":"UNKNOWN")
            .append("\\n");
        }
      }catch(RuntimeException ignored){}
    }
    if(obd!=null)msg.append("\\nSursă OBD: ")
      .append(obd.isDirect()?"ELM327 direct":"Torque AIDL")
      .append("\\n").append(obd.status()).append("\\n").append(obd.diagnostic());
    msg.append("\\n\\nDacă Torque/ELM funcționează pe telefon, dar Android din navigație nu vede dispozitivul Classic sau BLE, Bluetooth-ul head-unit poate fi limitat la apeluri (MCU). Nu se poate corecta din polling OBD.");
    new AlertDialog.Builder(this).setTitle("Audit Bluetooth navigație")
      .setMessage(msg.toString())
      .setPositiveButton("Caută Classic",(d,w)->scanClassicAdapters())
      .setNeutralButton("Caută BLE",(d,w)->scanBleAdapters())
      .setNegativeButton("Închide",null).show();
  }
  void scanBleAdapters(){
    if(checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)
       !=android.content.pm.PackageManager.PERMISSION_GRANTED){
      requestPermissions(new String[]{android.Manifest.permission.ACCESS_FINE_LOCATION},2407);
      android.widget.Toast.makeText(this,
        "Permite locația pentru scanarea BLE în Android 10, apoi repetă căutarea.",
        android.widget.Toast.LENGTH_LONG).show();
      return;
    }
    final android.bluetooth.BluetoothAdapter adapter=android.bluetooth.BluetoothAdapter.getDefaultAdapter();
    final android.bluetooth.le.BluetoothLeScanner scanner=adapter==null?null:adapter.getBluetoothLeScanner();
    if(scanner==null){
      new AlertDialog.Builder(this).setTitle("BLE indisponibil")
        .setMessage("Bluetooth Low Energy nu este disponibil pe această navigație sau locația Android este dezactivată.")
        .setPositiveButton("OK",null).show();return;
    }
    final java.util.LinkedHashMap<String,android.bluetooth.le.ScanResult> found=
      new java.util.LinkedHashMap<>();
    final android.app.ProgressDialog progress=new android.app.ProgressDialog(this);
    progress.setTitle("ELM327 BLE");progress.setMessage("Caut adaptoare BLE timp de 8 secunde...");
    progress.setCancelable(true);
    final boolean[] completed={false};
    final android.bluetooth.le.ScanCallback callback=new android.bluetooth.le.ScanCallback(){
      @Override public void onScanResult(int type,android.bluetooth.le.ScanResult result){
        if(result==null||result.getDevice()==null||completed[0])return;
        runOnUiThread(()->{
          if(!completed[0])found.put(result.getDevice().getAddress(),result);
        });
      }
      @Override public void onScanFailed(int error){
        runOnUiThread(()->{
          if(!completed[0])progress.setMessage("Scanare BLE: eroare "+error+
            ". Verifică GPS/locația Android.");
        });
      }
    };
    final Runnable finish=()->{
      if(completed[0])return;
      completed[0]=true;
      try{scanner.stopScan(callback);}catch(RuntimeException ignored){}
      progress.dismiss();
      if(isFinishing())return;
      if(found.isEmpty()){
        new AlertDialog.Builder(this).setTitle("BLE: niciun dispozitiv detectat")
          .setMessage("Scanarea BLE a returnat zero dispozitive. Asta NU înseamnă că ELM327 lipsește: cele mai multe adaptoare OBDII clasice folosesc Bluetooth Classic/SPP, nu BLE. Încearcă scanarea Classic ori vezi auditul modulului Bluetooth Android.")
          .setPositiveButton("Caută Classic",(d,w)->scanClassicAdapters())
          .setNeutralButton("Diagnostic BT",(d,w)->showBluetoothDiagnosis())
          .setNegativeButton("Închide",null).show();
        return;
      }
      ArrayList<android.bluetooth.le.ScanResult> choices=new ArrayList<>(found.values());
      String[] labels=new String[choices.size()];
      for(int i=0;i<choices.size();i++){
        android.bluetooth.le.ScanResult result=choices.get(i);
        String name=result.getScanRecord()==null?null:result.getScanRecord().getDeviceName();
        if(name==null||name.isEmpty())name=result.getDevice().getName();
        labels[i]=(name==null?"BLE necunoscut":name)+"  •  "+
          result.getDevice().getAddress()+"  ("+result.getRssi()+" dBm)";
      }
      new AlertDialog.Builder(this).setTitle("Alege adaptorul BLE / ELM327")
        .setItems(labels,(dialog,which)->selectObdDevice(
          choices.get(which).getDevice().getAddress(),true))
        .setNegativeButton("Anulează",null).show();
    };
    progress.setOnCancelListener(dialog->{handler.removeCallbacks(finish);finish.run();});
    try{
      android.bluetooth.le.ScanSettings settings=
        new android.bluetooth.le.ScanSettings.Builder()
          .setScanMode(android.bluetooth.le.ScanSettings.SCAN_MODE_LOW_LATENCY).build();
      scanner.startScan(null,settings,callback);
      progress.show();
      handler.postDelayed(finish,8000);
    }catch(RuntimeException error){
      try{scanner.stopScan(callback);}catch(RuntimeException ignored){}
      new AlertDialog.Builder(this).setTitle("BLE")
        .setMessage("Scanarea este indisponibilă: "+error.getMessage())
        .setPositiveButton("OK",null).show();
    }
  }
  void showObdStatus(){
    ObdReader.Reading r=obd==null?ObdReader.Reading.empty():obd.current();
    boolean direct=obd!=null&&obd.isDirect();
    String info=obd==null?"OBD NECONECTAT":obd.status();
    String source=direct?"ELM327 Bluetooth direct":"Torque Pro oficial";
    String adapter=obd==null?"":obd.adapterAddress();
    new AlertDialog.Builder(this).setTitle("OBD-II • STFT / LTFT / RPM / apă")
      .setMessage("Sursă: "+source+"\nStare: "+info+"\n"+(obd==null?"":obd.diagnostic())+
        (direct?"\nAdaptor selectat: "+(adapter.isEmpty()?"NU":adapter):"")+
        "\nSTFT: "+(Float.isFinite(r.stft)?r.stft+" %":"N/A")+
        "\nLTFT: "+(Float.isFinite(r.ltft)?r.ltft+" %":"N/A")+
        "\nRPM: "+(Float.isFinite(r.rpm)?r.rpm:"N/A")+
        "\nTemperatura: "+(Float.isFinite(r.coolantC)?r.coolantC+" °C":"N/A")+
        "\n\nPentru Torque neoficial, selectează ELM327 Bluetooth direct. Adaptorul trebuie asociat cu navigația. Închide conexiunea OBD din Torque înainte de folosirea citirii directe. Nu trimitem comenzi de modificare ECU.")
      .setPositiveButton("Alege ELM327",(d,w)->selectElmAdapter())
      .setNeutralButton("Schimbă sursa",(d,w)->chooseObdSource())
      .setNegativeButton("Închide",null).show();
  }
  void permissions(){try{startActivity(new Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"));}catch(Exception e){startActivity(new Intent(Settings.ACTION_SETTINGS));}}
  class Dashboard extends View{
   Paint p=new Paint(3);int white=0xfff1f4fb,red=0xffec263b,muted=0xff94a3b5,bg=0xff0a1019,card=0xc4161f2c;
   Dashboard(){super(MainActivity.this);}
   void r(Canvas c,float x,float y,float w,float h,int col,float rad){p.setStyle(Paint.Style.FILL);p.setColor(col);c.drawRoundRect(x,y,x+w,y+h,rad,rad,p);}
   void outline(Canvas c,float x,float y,float w,float h,int col){p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2);p.setColor(col);c.drawRoundRect(x,y,x+w,y+h,14,14,p);p.setStyle(Paint.Style.FILL);}
   void t(Canvas c,String s,float x,float y,int size,int color){p.setStyle(Paint.Style.FILL);p.setShader(null);p.setColor(color);p.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));p.setTextSize(size);c.drawText(s,x,y,p);} void centered(Canvas c,String s,float x,float y,int size,int color){p.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));p.setTextSize(size);t(c,s,x-p.measureText(s)/2f,y,size,color);}
   void l(Canvas c,float x,float y,float xx,float yy,int col,int w){p.setColor(col);p.setStrokeWidth(w);p.setStrokeCap(Paint.Cap.ROUND);c.drawLine(x,y,xx,yy,p);}
   void dot(Canvas c,float x,float y,float radius,int col){p.setColor(col);p.setStyle(Paint.Style.FILL);c.drawCircle(x,y,radius,p);}
   void nav(Canvas c){r(c,0,0,112,720,0xff101720,0);String[] letters={"⌂","♫","➤","▤","▦","⚙"},labels={"Acasă","Muzică","Navigație","Mașină","Aplicații","Setări"};for(int i=0;i<6;i++){int y=73+i*105;if(page==i){r(c,0,y,109,100,0xff321c28,0);r(c,0,y,5,100,red,0);}t(c,letters[i],39,y+42,32,page==i?red:white);t(c,labels[i],i==2?13:23,y+77,16,page==i?white:muted);}}
   void header(Canvas c){if(page==0){t(c,"◆",23,41,32,red);t(c,"K2401",72,40,27,white);t(c,"EVO",181,40,28,red);t(c,"LAUNCHER",260,40,26,white);t(c,"ANDROID 10",1015,38,15,muted);t(c,new SimpleDateFormat(launcherSettings!=null&&launcherSettings.use24HourClock()?"HH:mm":"hh:mm a",Locale.getDefault()).format(new Date()),1158,40,23,white);}else{t(c,"MITSUBISHI",140,39,19,white);t(c,"LANCER",295,39,19,white);t(c,"EVOLUTION",397,39,18,red);t(c,"K2401",1130,39,15,muted);t(c,new SimpleDateFormat(launcherSettings!=null&&launcherSettings.use24HourClock()?"HH:mm":"hh:mm a",Locale.getDefault()).format(new Date()),1180,39,22,white);}l(c,page==0?0:112,61,1280,61,0xff58212d,1);}
   void title(Canvas c,String name,String sub){t(c,name,149,121,32,white);t(c,sub,149,158,17,muted);}
   void map(Canvas c,int x,int y,int w,int h){
      r(c,x,y,w,h,0xff182332,16);outline(c,x,y,w,h,0xff384859);t(c,"Se încarcă harta online...",x+28,y+61,19,muted);
   }
   String musicText(boolean title){if(media==null||media.getMetadata()==null)return "";CharSequence s=media.getMetadata().getText(title?MediaMetadata.METADATA_KEY_TITLE:MediaMetadata.METADATA_KEY_ARTIST);return s==null?"":s.toString();}
   String shorten(String s){return s.length()>28?s.substring(0,27)+"…":s;}
   void music(Canvas c,int x,int y,int w,int h){
       r(c,x,y,w,h,0xd4171f2b,16);outline(c,x,y,w,h,0xff712638);dot(c,x+29,y+29,15,red);t(c,"▶",x+20,y+36,18,white);t(c,shorten(mediaName),x+55,y+36,22,white);t(c,"EVO MEDIA",x+w-153,y+37,18,red);
       r(c,x+18,y+70,167,h-131,0xff7f182d,10);Bitmap art=null;if(media!=null&&media.getMetadata()!=null){art=media.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);if(art==null)art=media.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ART);if(art==null)art=media.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_DISPLAY_ICON);}if(art!=null){p.setColor(white);p.setStyle(Paint.Style.FILL);c.drawBitmap(art,null,new Rect(x+20,y+72,x+183,y+h-63),p);}else{t(c,"YT",x+73,y+158,42,white);t(c,"MUSIC",x+51,y+194,22,white);}
       String title=musicText(true),artist=musicText(false);
       if(title.isEmpty()){title=mediaPackage.isEmpty()?"Selectează playerul":"Fără redare activă";artist=mediaPackage.isEmpty()?"Atinge panoul pentru a alege Vanced":"Permite MediaSession / pornește redarea";}
       t(c,shorten(title),x+205,y+126,27,white);t(c,shorten(artist),x+205,y+160,19,muted);
       r(c,x+205,y+186,w-225,5,0xff455065,3);long duration=media!=null&&media.getMetadata()!=null?media.getMetadata().getLong(MediaMetadata.METADATA_KEY_DURATION):0;long pos=media!=null&&media.getPlaybackState()!=null?media.getPlaybackState().getPosition():0;if(media!=null&&media.getPlaybackState()!=null&&media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING){long updated=media.getPlaybackState().getLastPositionUpdateTime();if(updated>0){long delta=Math.max(0,SystemClock.elapsedRealtime()-updated);pos+=(long)(delta*media.getPlaybackState().getPlaybackSpeed());}}if(duration>0&&pos>=0){float ratio=Math.max(0,Math.min(1,(float)pos/duration));r(c,x+205,y+186,(w-225)*ratio,5,red,3);}
       t(c,media!=null?"MediaSession activă • control în panou":"Atinge titlul pentru player / setări media",x+205,y+214,15,muted);
       t(c,"◀◀",x+247,y+h-36,27,white);dot(c,x+390,y+h-46,28,red);boolean musicPlaying=media!=null&&media.getPlaybackState()!=null&&media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;t(c,musicPlaying?"Ⅱ":"▶",x+376,y+h-34,27,white);t(c,"▶▶",x+493,y+h-36,27,white);
   }
   String formatObd(float value){return Float.isFinite(value)?String.format(Locale.US,"%.1f",value):"N/A";}
   void gauges(Canvas c,int x,int y,int w,int h){
       r(c,x,y,w,h,card,16);outline(c,x,y,w,h,0xff7e2638);
       t(c,"OBD-II • "+(obd!=null&&obd.isDirect()?"ELM327 DIRECT":"TORQUE OFICIAL"),x+20,y+32,20,white);
       ObdReader.Reading rd=obd==null?ObdReader.Reading.empty():obd.current();
       t(c,obd==null?"OBD NECONECTAT":obd.status(),x+w-205,y+30,13,rd.live?0xff36c888:muted);
       l(c,x+16,y+45,x+w-16,y+45,0xff394657,1);
       // Order explicitly approved: STFT B1, LTFT B1, RPM, coolant.
       String[] names={"STFT B1","LTFT B1","RPM","TEMP APĂ"};
       String[] units={"%","%","rpm","°C"};
       float[] vals={rd.stft,rd.ltft,rd.rpm,rd.coolantC};
       float[] minimum={-25f,-25f,0f,40f},maximum={25f,25f,8000f,120f};
       for(int i=0;i<4;i++){
         float cx=x+78+i*(w-156)/3f,cy=y+146,rad=57;
         p.setStyle(Paint.Style.FILL);p.setColor(0xff090e15);c.drawCircle(cx,cy,rad+8,p);
         p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(4);p.setColor(0xff465366);
         c.drawArc(cx-rad,cy-rad,cx+rad,cy+rad,135,270,false,p);
         for(int j=0;j<=10;j++){
           double a=Math.toRadians(135+27*j);float ca=(float)Math.cos(a),sa=(float)Math.sin(a);
           l(c,cx+ca*(rad-11),cy+sa*(rad-11),cx+ca*(rad-2),cy+sa*(rad-2),j>=8?red:muted,2);
         }
         p.setStyle(Paint.Style.FILL);
         // No needle at all when Torque has not supplied a fresh finite value.
         float val=vals[i];
         if(Float.isFinite(val)){
           float fraction=Math.max(0f,Math.min(1f,(val-minimum[i])/(maximum[i]-minimum[i])));
           double a=Math.toRadians(135+270*fraction);
           float tx=cx+(float)Math.cos(a)*(rad-15),ty=cy+(float)Math.sin(a)*(rad-15);
           l(c,cx,cy,tx,ty,red,4);dot(c,cx,cy,5,white);
         }else{dot(c,cx,cy,3,0xff536073);}
         String number=!Float.isFinite(val)?"N/A":i==2?String.format(Locale.US,"%.0f",val):i==3?String.format(Locale.US,"%.0f",val):String.format(Locale.US,"%+.1f",val);
         centered(c,number,cx,cy+89,27,white);
         centered(c,names[i],cx,cy+112,16,white);
         centered(c,units[i],cx,cy+132,14,muted);
       }
   }
   void row(Canvas c,int y,String name,String desc){r(c,150,y,1088,109,card,14);r(c,150,y,5,109,red,0);t(c,name,177,y+42,25,white);t(c,desc,177,y+80,17,muted);}
   protected void onDraw(Canvas original){original.save();original.scale(getWidth()/1280f,getHeight()/720f);if(launcherSettings!=null){launcherSettings.drawWallpaper(original);red=launcherSettings.accent();}else original.drawColor(bg);if(page!=0)nav(original);header(original);
      if(page==0){map(original,20,78,600,490);music(original,634,78,626,298);gauges(original,634,389,626,310);}
      if(page==1){title(original,"MUZICĂ","Player configurabil • control MediaSession în panou");music(original,158,185,1070,435);}
      if(page==2){title(original,"NAVIGAȚIE","Hartă OSM nativă / Google SDK • GPS și căutare în panou");map(original,158,169,1052,527);}
      if(page==3){title(original,"MAȘINĂ","Ceasuri OBD în stil EVO • modul live necesită adaptor ELM327");gauges(original,156,200,1069,335);row(original,560,obd!=null&&obd.current().live?"OBD-II conectat":"ELM327 Bluetooth",obd!=null&&obd.current().live?"Date live din ECU, numai citire, fără comenzi de modificare.":"Alege adaptorul ELM327 Bluetooth în setări; Torque neoficial nu are nevoie de plugin.");}
      if(page==4){title(original,"APLICAȚII","Lansează aplicații reale sau adaugă-le în bara de pinuri");String[] labels={"Google Maps","Alege player","OBD / ELM327","Alege aplicație","Setări Android","Bluetooth"};for(int i=0;i<6;i++){int x=158+(i%3)*360,y=210+(i/3)*181;r(original,x,y,324,150,card,14);t(original,labels[i],x+24,y+90,24,white);}}
      if(page==5){title(original,"SETĂRI","EVO Dark Red • fără animații sau servicii permanente");row(original,186,"Acces notificări","Permite controlul YouTube Music prin MediaSession.");row(original,316,"Google Maps","Hartă interactivă live (Maps SDK cu cheie, altfel OpenStreetMap).");row(original,446,"OBD / ELM327","Citire directă Bluetooth sau API Torque oficial — alege sursa din setări.");row(original,576,"Protecție","Nu modificăm MCU, boot, recovery sau CANBUS.");}
      original.restore();}
   public boolean onTouchEvent(MotionEvent e){if(e.getAction()!=MotionEvent.ACTION_UP)return true;float x=e.getX()*1280/getWidth(),y=e.getY()*720/getHeight();
       if(page!=0&&x<109&&y>=73){int idx=(int)((y-73)/105);if(idx>=0&&idx<6)page=idx;invalidate();placeMap();return true;}
       if(page==0){if(y<65&&x<65){page=4;invalidate();placeMap();}else if(y<65&&x>1210){page=5;invalidate();placeMap();}else if(x>=634&&y>=78&&y<386){if(y>294)mediaAction(x<995?0:x<1125?1:2);else choosePlayer();}else if(x>=634&&y>=389){showObdStatus();}}
       else if(page==1){if(y>=520&&y<=620&&x>=350&&x<=715){mediaAction(x<477?0:x<608?1:2);}else if(x>=158&&x<=1228&&y>=185&&y<520){choosePlayer();}}
       else if(page==2){/* Native map overlay handles touches; never switch Activities. */}else if(page==3){showObdStatus();}
       else if(page==4){int col=(int)((x-158)/360),r=(int)((y-210)/181),i=r*3+col;if(col>=0&&col<3&&r>=0&&r<2){if(i==0)maps();else if(i==1)choosePlayer();else if(i==2)showObdStatus();else if(i==3&&shortcutDock!=null)shortcutDock.openPicker();else if(i==4){try{startActivity(new Intent(Settings.ACTION_SETTINGS));}catch(Exception ignored){}}else if(i==5){try{startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS));}catch(Exception ignored){}}}}
       else if(page==5&&y>=186&&y<=300)permissions();invalidate();placeMap();return true;}
  }
}