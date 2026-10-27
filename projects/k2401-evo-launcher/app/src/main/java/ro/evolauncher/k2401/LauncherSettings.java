package ro.evolauncher.k2401;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;
import java.io.InputStream;
import java.util.Locale;

/** Working in-app launcher settings. All values persist between reboots.
 * Wallpaper images are read through SAF grants and decoded within a memory bound.
 * Never changes global device wallpaper or system MCU/ROM settings.
 */
final class LauncherSettings extends ScrollView {
  static final int PICK_WALLPAPER=2406;
  private static final int WHITE=0xffedf3fb, MUTED=0xffa8b6c5;
  private final Activity host;
  private final Runnable changed;
  private final SharedPreferences store;
  private final LinearLayout body;
  private Bitmap photo;
  private String mode;
  private int accent, dim;
  private boolean clock24;

  LauncherSettings(Activity activity, Runnable onChange){
    super(activity);
    host=activity;
    changed=onChange;
    store=activity.getSharedPreferences("evo_launcher_prefs",Context.MODE_PRIVATE);
    mode=store.getString("wallpaper_preset","carbon");
    accent=store.getInt("accent",0xffec263b);
    dim=store.getInt("wallpaper_dim",40);
    clock24=store.getBoolean("clock_24h",true);
    setFillViewport(true);
    setBackgroundColor(0xff101722);
    setVerticalScrollBarEnabled(true);
    body=new LinearLayout(activity);
    body.setOrientation(LinearLayout.VERTICAL);
    body.setPadding(dp(26),dp(16),dp(26),dp(36));
    addView(body,new LayoutParams(-1,-2));
    readPhoto();
    renderControls();
  }
  private int dp(float v){return (int)(v*host.getResources().getDisplayMetrics().density+0.5f);}
  private void heading(String s){
    TextView v=new TextView(host);
    v.setText(s);v.setTextColor(WHITE);v.setTextSize(22);
    v.setPadding(0,dp(8),0,dp(8));body.addView(v,new LinearLayout.LayoutParams(-1,-2));
  }
  private void sub(String s){
    TextView v=new TextView(host);
    v.setText(s);v.setTextColor(MUTED);v.setTextSize(13);
    v.setPadding(0,dp(1),0,dp(8));body.addView(v);
  }
  private Button button(LinearLayout row,String caption,Runnable command){
    Button b=new Button(host);b.setText(caption);b.setTextSize(13);b.setAllCaps(false);
    b.setTextColor(WHITE);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xff394357));
    LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(50),1f);
    p.setMargins(dp(3),0,dp(3),dp(9));row.addView(b,p);
    b.setOnClickListener(v->command.run());return b;
  }
  private LinearLayout row(){
    LinearLayout r=new LinearLayout(host);r.setOrientation(LinearLayout.HORIZONTAL);
    body.addView(r,new LinearLayout.LayoutParams(-1,-2));return r;
  }
  private void preset(String next){
    mode=next;
    store.edit().putString("wallpaper_preset",next).commit();
    if(!"custom".equals(next)){if(photo!=null){photo.recycle();photo=null;}}
    changed.run();
    renderControls();
  }
  private void setAccent(int c){
    accent=c;store.edit().putInt("accent",c).commit();changed.run();renderControls();
  }
  private void renderControls(){
    body.removeAllViews();
    heading("PERSONALIZARE • EVO LAUNCHER");
    sub("Fundalul, culorile, ceasul si luminozitatea se salveaza automat, inclusiv dupa repornire.");
    heading("WALLPAPER");
    LinearLayout first=row();
    button(first,"EVO Carbon",()->preset("carbon"));
    button(first,"Graphite",()->preset("graphite"));
    button(first,"Midnight",()->preset("midnight"));
    LinearLayout second=row();
    button(second,"Alege fotografie",()->pickImage());
    button(second,"Revino la implicit",()->preset("carbon"));
    sub("Fundal activ: "+("custom".equals(mode)?"Fotografie":mode.toUpperCase(Locale.ROOT))+
        ". Imaginea este afisata doar in launcher, nu modifica fundalul Android.");
    heading("INTENSITATE FUNDAL");
    SeekBar seek=new SeekBar(host);seek.setMax(80);seek.setProgress(dim);
    body.addView(seek,new LinearLayout.LayoutParams(-1,dp(42)));
    seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
      @Override public void onProgressChanged(SeekBar s,int n,boolean fromUser){
        if(fromUser){dim=n;store.edit().putInt("wallpaper_dim",n).commit();changed.run();}
      }
      @Override public void onStartTrackingTouch(SeekBar s){}
      @Override public void onStopTrackingTouch(SeekBar s){}
    });
    heading("CULOARE ACCENT");
    LinearLayout accents=row();
    button(accents,"Rosu EVO",()->setAccent(0xffec263b));
    button(accents,"Albastru",()->setAccent(0xff248ce6));
    button(accents,"Chihlimbar",()->setAccent(0xffffaa28));
    heading("CEAS SI PREFERINTE");
    Switch clock=new Switch(host);
    clock.setText("Ceas 24 de ore");clock.setTextColor(WHITE);clock.setTextSize(16);
    clock.setPadding(dp(6),dp(6),dp(6),dp(6));clock.setChecked(clock24);
    body.addView(clock,new LinearLayout.LayoutParams(-1,dp(55)));
    clock.setOnCheckedChangeListener((b,v)->{clock24=v;store.edit().putBoolean("clock_24h",v).commit();changed.run();});
    heading("PLAYER VIDEO / MUSIC");
    sub("Alege orice player instalat, inclusiv YouTube Vanced/ReVanced. EVO nu deschide automat alte ferestre.");
    LinearLayout mediaRow=row();
    button(mediaRow,"Alege playerul",()->((MainActivity)host).choosePlayer());
    button(mediaRow,"Stare player",()->((MainActivity)host).mediaSetup());
    heading("OBD-II / ELM327 DIRECT");
    sub("Torque neoficial nu are API-ul Torque Pro. EVO poate citi singur adaptorul Bluetooth Classic deja asociat, fara date simulate.");
    LinearLayout obdRow=row();
    button(obdRow,"Alege ELM327 Bluetooth",()->((MainActivity)host).selectElmAdapter());
    button(obdRow,"Sursa ceasurilor",()->((MainActivity)host).chooseObdSource());
    LinearLayout obdState=row();
    button(obdState,"Stare ECU / PID",()->((MainActivity)host).showObdStatus());
    heading("CONEXIUNI SI APLICATII");
    LinearLayout connections=row();
    button(connections,"Acces MediaSession",()->((MainActivity)host).permissions());
    button(connections,"Bluetooth / Torque",()->launchSettings(Settings.ACTION_BLUETOOTH_SETTINGS));
    button(connections,"GPS / Locatie",()->launchSettings(Settings.ACTION_LOCATION_SOURCE_SETTINGS));
    LinearLayout actions=row();
    button(actions,"Setari Android",()->launchSettings(Settings.ACTION_SETTINGS));
    button(actions,"Stare OBD / ECU",()->((MainActivity)host).showObdStatus());
    button(actions,"Alege player",()->((MainActivity)host).choosePlayer());
    sub("OBD: ELM327 direct citeste PID 0106/0107/010C/0105 fara Torque oficial; inchide conexiunea Torque neoficial cand folosesti EVO. Playerul necesita MediaSession activa. Hartile sunt in Home.");
    sub("NU modifica MCU, CANBUS, ROM, recovery sau launcherul implicit fara acordul utilizatorului.");
  }
  private void launchSettings(String action){
    try{host.startActivity(new Intent(action));}
    catch(Exception ex){Toast.makeText(host,"Setarea nu este disponibila pe acest dispozitiv",Toast.LENGTH_LONG).show();}
  }
  private void pickImage(){
    Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);
    i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("image/*");
    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
    try{host.startActivityForResult(i,PICK_WALLPAPER);}
    catch(Exception ex){Toast.makeText(host,"Nu exista un selector de imagini. Poti folosi fundalurile incluse.",Toast.LENGTH_LONG).show();}
  }
  void onPicked(int requestCode,int resultCode,Intent intent){
    if(requestCode!=PICK_WALLPAPER||resultCode!=Activity.RESULT_OK||intent==null||intent.getData()==null)return;
    Uri uri=intent.getData();
    try{
      host.getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);
      Bitmap newBitmap=decode(uri);
      if(newBitmap==null)throw new IllegalArgumentException("Imagine invalida");
      if(photo!=null)photo.recycle();
      photo=newBitmap;mode="custom";
      store.edit().putString("wallpaper_uri",uri.toString()).putString("wallpaper_preset","custom").commit();
      changed.run();renderControls();
    }catch(Exception ex){Toast.makeText(host,"Fotografia nu poate fi citita; alege alta imagine.",Toast.LENGTH_LONG).show();}
  }
  private Bitmap decode(Uri uri) throws Exception {
    BitmapFactory.Options opts=new BitmapFactory.Options();opts.inJustDecodeBounds=true;
    try(InputStream s=host.getContentResolver().openInputStream(uri)){if(s==null)return null;BitmapFactory.decodeStream(s,null,opts);}
    if(opts.outWidth<1||opts.outHeight<1)return null;
    int sample=1;
    while(opts.outWidth/sample>1920||opts.outHeight/sample>1080)sample*=2;
    opts.inJustDecodeBounds=false;opts.inSampleSize=sample;opts.inPreferredConfig=Bitmap.Config.RGB_565;
    try(InputStream s=host.getContentResolver().openInputStream(uri)){return s==null?null:BitmapFactory.decodeStream(s,null,opts);}
  }
  private void readPhoto(){
    if(!"custom".equals(mode))return;
    String value=store.getString("wallpaper_uri",null);
    if(value==null){mode="carbon";return;}
    try{photo=decode(Uri.parse(value));if(photo==null)mode="carbon";}
    catch(Exception ex){mode="carbon";}
  }
  int accent(){return accent;}
  boolean use24HourClock(){return clock24;}
  /** Called in scaled 1280x720 canvas coordinate space, before content cards. */
  void drawWallpaper(Canvas c){
    Paint p=new Paint(3);
    if("custom".equals(mode)&&photo!=null&&!photo.isRecycled()){
      float factor=Math.max(1280f/photo.getWidth(),720f/photo.getHeight());
      int dw=(int)(photo.getWidth()*factor),dh=(int)(photo.getHeight()*factor);
      Rect src=new Rect(0,0,photo.getWidth(),photo.getHeight());
      Rect dest=new Rect((1280-dw)/2,(720-dh)/2,(1280+dw)/2,(720+dh)/2);
      c.drawBitmap(photo,src,dest,p);
    }else{
      int top="graphite".equals(mode)?0xff364354:"midnight".equals(mode)?0xff071129:0xff17202a;
      int bottom="graphite".equals(mode)?0xff101720:"midnight".equals(mode)?0xff08090f:0xff070c13;
      p.setShader(new LinearGradient(0,0,1280,720,top,bottom,Shader.TileMode.CLAMP));
      c.drawRect(0,0,1280,720,p);p.setShader(null);
      if(!"midnight".equals(mode)){
        p.setColor("graphite".equals(mode)?0x187da0b4:0x123f5365);
        p.setStrokeWidth(2);
        for(int x=-720;x<1800;x+=20)c.drawLine(x,0,x+720,720,p);
      }
      p.setColor(accent);p.setAlpha(28);c.drawCircle(1130,620,420,p);
    }
    p.setColor(android.graphics.Color.argb(Math.min(220,dim*255/100),0,0,0));
    c.drawRect(0,0,1280,720,p);
  }
  void dispose(){if(photo!=null){photo.recycle();photo=null;}}
}
