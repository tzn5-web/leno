package ro.evolauncher.k2401;
import android.app.*;import android.content.*;import android.graphics.*;import android.media.*;import android.media.session.*;import android.net.*;import android.os.*;import android.provider.*;import android.view.*;import java.lang.ref.*;import java.text.*;import java.util.*;
public final class MainActivity extends Activity {
  static WeakReference<MainActivity> active=new WeakReference<>(null);
  Handler handler=new Handler(); MediaController media; Dashboard view; ObdReader obd; LiveMapPanel liveMap; android.widget.FrameLayout stage; int page=0; boolean emu;
  final MediaController.Callback mediaCallback=new MediaController.Callback(){@Override public void onPlaybackStateChanged(PlaybackState s){if(view!=null)view.invalidate();}@Override public void onMetadataChanged(MediaMetadata m){if(view!=null)view.invalidate();}@Override public void onSessionDestroyed(){refresh();if(view!=null)view.invalidate();}};
  final Runnable update=new Runnable(){public void run(){if(view!=null)view.invalidate();handler.postDelayed(this,1000);}};
  public void onCreate(Bundle state){super.onCreate(state);getWindow().getDecorView().setSystemUiVisibility(5894|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);emu=Build.FINGERPRINT.contains("generic")||Build.PRODUCT.contains("sdk");view=new Dashboard();obd=new ObdReader(this,()->runOnUiThread(()->{if(view!=null)view.invalidate();}));stage=new android.widget.FrameLayout(this);stage.addView(view,new android.widget.FrameLayout.LayoutParams(-1,-1));liveMap=new LiveMapPanel(this);stage.addView(liveMap,new android.widget.FrameLayout.LayoutParams(200,200));stage.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or2,ob)->placeMap());setContentView(stage);active=new WeakReference<>(this);placeMap();}
  protected void onStart(){super.onStart();if(liveMap!=null)liveMap.onHostStart();}
  protected void onResume(){super.onResume();if(liveMap!=null)liveMap.onHostResume();refresh();handler.removeCallbacks(update);handler.post(update);startObd();if(!emu&&checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)!=android.content.pm.PackageManager.PERMISSION_GRANTED&&checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)!=android.content.pm.PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{android.Manifest.permission.ACCESS_FINE_LOCATION,android.Manifest.permission.ACCESS_COARSE_LOCATION},2402);}}
  protected void onPause(){handler.removeCallbacks(update);if(obd!=null)obd.stop();if(liveMap!=null)liveMap.onHostPause();super.onPause();}
  protected void onStop(){if(liveMap!=null)liveMap.onHostStop();super.onStop();}
  protected void onDestroy(){if(media!=null){try{media.unregisterCallback(mediaCallback);}catch(Exception ignored){}}if(obd!=null)obd.close();if(liveMap!=null)liveMap.onHostDestroy();active.clear();super.onDestroy();}
  void startObd(){if(!emu)obd.start();}
  @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grantResults){super.onRequestPermissionsResult(code,permissions,grantResults);if(code==2402&&liveMap!=null){liveMap.onHostPause();liveMap.onHostStart();}if(code==2401&&obd!=null){for(int result:grantResults)if(result!=android.content.pm.PackageManager.PERMISSION_GRANTED)return;if(grantResults.length>0)obd.start();}}
  public void onBackPressed(){page=0;view.invalidate();placeMap();}
  void placeMap(){if(stage==null||liveMap==null)return;boolean shown=page==0||page==2;liveMap.setVisibility(shown?View.VISIBLE:View.GONE);if(!shown)return;int w=stage.getWidth(),h=stage.getHeight();if(w<=0||h<=0)return;float sx=w/1280f,sy=h/720f;int x=page==0?124:158,y=page==0?78:169,mw=page==0?522:1052,mh=page==0?622:527;android.widget.FrameLayout.LayoutParams p=new android.widget.FrameLayout.LayoutParams(Math.max(1,Math.round(mw*sx)),Math.max(1,Math.round(mh*sy)));p.leftMargin=Math.round(x*sx);p.topMargin=Math.round(y*sy);liveMap.setLayoutParams(p);}
  static void changed(){MainActivity a=active.get();if(a!=null)a.runOnUiThread(()->{a.refresh();a.view.invalidate();});}
  void refresh(){MediaController next=null;try{MediaSessionManager m=(MediaSessionManager)getSystemService(MEDIA_SESSION_SERVICE);List<MediaController> all=m.getActiveSessions(new ComponentName(this,MediaAccessService.class));for(MediaController c:all)if("com.google.android.apps.youtube.music".equals(c.getPackageName())){next=c;break;}}catch(Exception ignored){}if(media!=null&&next!=null&&media.getSessionToken().equals(next.getSessionToken()))return;if(media!=null){try{media.unregisterCallback(mediaCallback);}catch(Exception ignored){}}media=next;if(media!=null)media.registerCallback(mediaCallback,handler);}
  void app(String pkg){try{Intent i=getPackageManager().getLaunchIntentForPackage(pkg);if(i!=null){startActivity(i);return;}startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("market://details?id="+pkg)));}catch(Exception ignored){}}
  void maps(){try{Intent i=getPackageManager().getLaunchIntentForPackage("com.google.android.apps.maps");if(i!=null)startActivity(i);else startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("geo:0,0?q=destinatie")));}catch(Exception ignored){}}
  void mediaAction(int id){refresh();if(media==null){app("com.google.android.apps.youtube.music");return;}try{MediaController.TransportControls t=media.getTransportControls();if(id==0)t.skipToPrevious();else if(id==2)t.skipToNext();else if(media.getPlaybackState()!=null&&media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING)t.pause();else t.play();}catch(Exception ignored){}view.invalidate();}
  void permissions(){try{startActivity(new Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"));}catch(Exception e){startActivity(new Intent(Settings.ACTION_SETTINGS));}}
  class Dashboard extends View{
   Paint p=new Paint(3);int white=0xfff1f4fb,red=0xffec263b,muted=0xff94a3b5,bg=0xff0a1019,card=0xff161f2c;
   Dashboard(){super(MainActivity.this);}
   void r(Canvas c,float x,float y,float w,float h,int col,float rad){p.setStyle(Paint.Style.FILL);p.setColor(col);c.drawRoundRect(x,y,x+w,y+h,rad,rad,p);}
   void outline(Canvas c,float x,float y,float w,float h,int col){p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2);p.setColor(col);c.drawRoundRect(x,y,x+w,y+h,14,14,p);p.setStyle(Paint.Style.FILL);}
   void t(Canvas c,String s,float x,float y,int size,int color){p.setStyle(Paint.Style.FILL);p.setShader(null);p.setColor(color);p.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));p.setTextSize(size);c.drawText(s,x,y,p);}
   void l(Canvas c,float x,float y,float xx,float yy,int col,int w){p.setColor(col);p.setStrokeWidth(w);p.setStrokeCap(Paint.Cap.ROUND);c.drawLine(x,y,xx,yy,p);}
   void dot(Canvas c,float x,float y,float radius,int col){p.setColor(col);p.setStyle(Paint.Style.FILL);c.drawCircle(x,y,radius,p);}
   void nav(Canvas c){r(c,0,0,112,720,0xff101720,0);String[] letters={"⌂","♫","➤","▤","▦","⚙"},labels={"Acasă","Muzică","Navigație","Mașină","Aplicații","Setări"};for(int i=0;i<6;i++){int y=73+i*105;if(page==i){r(c,0,y,109,100,0xff321c28,0);r(c,0,y,5,100,red,0);}t(c,letters[i],39,y+42,32,page==i?red:white);t(c,labels[i],i==2?13:23,y+77,16,page==i?white:muted);}}
   void header(Canvas c){t(c,"MITSUBISHI",140,39,19,white);t(c,"LANCER",295,39,19,white);t(c,"EVOLUTION",397,39,18,red);t(c,"K2401",1130,39,15,muted);t(c,new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date()),1200,39,24,white);l(c,112,61,1280,61,0xff253244,1);}
   void title(Canvas c,String name,String sub){t(c,name,149,121,32,white);t(c,sub,149,158,17,muted);}
   void map(Canvas c,int x,int y,int w,int h){
      r(c,x,y,w,h,0xff182332,16);outline(c,x,y,w,h,0xff384859);t(c,"Se încarcă harta online...",x+28,y+61,19,muted);
   }
   String musicText(boolean title){if(media==null||media.getMetadata()==null)return "";CharSequence s=media.getMetadata().getText(title?MediaMetadata.METADATA_KEY_TITLE:MediaMetadata.METADATA_KEY_ARTIST);return s==null?"":s.toString();}
   String shorten(String s){return s.length()>28?s.substring(0,27)+"…":s;}
   void music(Canvas c,int x,int y,int w,int h){
       r(c,x,y,w,h,0xff171f2b,16);outline(c,x,y,w,h,0xff712638);dot(c,x+29,y+29,15,red);t(c,"▶",x+20,y+36,18,white);t(c,"YouTube Music",x+55,y+36,22,white);t(c,"EVO MEDIA",x+w-153,y+37,18,red);
       r(c,x+18,y+70,167,h-131,0xff7f182d,10);Bitmap art=null;if(media!=null&&media.getMetadata()!=null){art=media.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);if(art==null)art=media.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ART);if(art==null)art=media.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_DISPLAY_ICON);}if(art!=null){p.setColor(white);p.setStyle(Paint.Style.FILL);c.drawBitmap(art,null,new Rect(x+20,y+72,x+183,y+h-63),p);}else{t(c,"YT",x+73,y+158,42,white);t(c,"MUSIC",x+51,y+194,22,white);}
       String title=musicText(true),artist=musicText(false);
       if(title.isEmpty()){title="Fără redare activă";artist="Pornește YouTube Music";}
       t(c,shorten(title),x+205,y+126,27,white);t(c,shorten(artist),x+205,y+160,19,muted);
       r(c,x+205,y+186,w-225,5,0xff455065,3);long duration=media!=null&&media.getMetadata()!=null?media.getMetadata().getLong(MediaMetadata.METADATA_KEY_DURATION):0;long pos=media!=null&&media.getPlaybackState()!=null?media.getPlaybackState().getPosition():0;if(media!=null&&media.getPlaybackState()!=null&&media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING){long updated=media.getPlaybackState().getLastPositionUpdateTime();if(updated>0){long delta=Math.max(0,SystemClock.elapsedRealtime()-updated);pos+=(long)(delta*media.getPlaybackState().getPlaybackSpeed());}}if(duration>0&&pos>=0){float ratio=Math.max(0,Math.min(1,(float)pos/duration));r(c,x+205,y+186,(w-225)*ratio,5,red,3);}
       t(c,media!=null?"Sesiune media activă":"MediaSession • conectează aplicația",x+205,y+214,15,muted);
       t(c,"◀◀",x+247,y+h-36,27,white);dot(c,x+390,y+h-46,28,red);t(c,"Ⅱ",x+376,y+h-34,27,white);t(c,"▶▶",x+493,y+h-36,27,white);
   }
   String formatObd(float value){return Float.isFinite(value)?String.format(Locale.US,"%.1f",value):"N/A";}
   void gauges(Canvas c,int x,int y,int w,int h){
       r(c,x,y,w,h,card,16);outline(c,x,y,w,h,0xff7e2638);t(c,"TORQUE   •   DATE MOTOR",x+23,y+34,22,white);t(c,emu?"DATE INDISPONIBILE":obd.status(),x+w-239,y+33,15,0xffffb875);
       l(c,x+20,y+48,x+w-20,y+48,0xff394657,1);
       String[] name={"RPM","STFT B1","LTFT B1","TEMP. APĂ"},unit={"rpm","%","%","°C"};
       ObdReader.Reading reading=obd==null?ObdReader.Reading.empty():obd.current();
       String[] value=emu?new String[]{"N/A","N/A","N/A","N/A"}:new String[]{formatObd(reading.rpm),formatObd(reading.stft),formatObd(reading.ltft),Float.isFinite(reading.coolantC)?""+Math.round(reading.coolantC):"N/A"};
       for(int i=0;i<4;i++){float cx=x+78+i*(w-160)/3f,cy=y+166;
           p.setColor(0xff435063);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(9);c.drawArc(cx-59,cy-59,cx+59,cy+59,132,276,false,p);
           float val=i==0?reading.rpm:i==1?reading.stft:i==2?reading.ltft:reading.coolantC;if(!emu&&Float.isFinite(val)){float progress=i==0?val/8000f:i==3?(val+30)/170f:(val+100)/200f;progress=Math.max(0,Math.min(1,progress));p.setColor(red);c.drawArc(cx-59,cy-59,cx+59,cy+59,132,276*progress,false,p);}p.setStyle(Paint.Style.FILL);
           t(c,value[i],cx-30,cy+15,35,white);t(c,unit[i],cx-10,cy+39,16,muted);t(c,name[i],cx-58,cy+91,15,white);
       }
   }
   void row(Canvas c,int y,String name,String desc){r(c,150,y,1088,109,card,14);r(c,150,y,5,109,red,0);t(c,name,177,y+42,25,white);t(c,desc,177,y+80,17,muted);}
   protected void onDraw(Canvas original){original.save();original.scale(getWidth()/1280f,getHeight()/720f);original.drawColor(bg);nav(original);header(original);
      if(page==0){map(original,124,78,522,622);music(original,659,78,600,298);gauges(original,659,389,600,310);}
      if(page==1){title(original,"MUZICĂ","YouTube Music / control prin sesiunea Android");music(original,158,185,1070,435);}
      if(page==2){title(original,"NAVIGAȚIE","Apasă harta pentru a porni Google Maps");map(original,158,169,1052,527);}
      if(page==3){title(original,"MAȘINĂ","Ceasuri OBD în stil EVO • modul live necesită adaptor ELM327");gauges(original,156,200,1069,335);row(original,560,obd!=null&&obd.current().live?"OBD-II conectat":"ELM327 Bluetooth",obd!=null&&obd.current().live?"Date live din ECU, numai citire, fără comenzi de modificare.":"Deschide Torque Pro și conectează ECU, apoi revino în launcher.");}
      if(page==4){title(original,"APLICAȚII","Deschide direct aplicațiile Android instalate");String[] labels={"Google Maps","YouTube Music","Torque","Radio OEM","Android Settings","Bluetooth"};for(int i=0;i<6;i++){int x=158+(i%3)*360,y=210+(i/3)*181;r(original,x,y,324,150,card,14);t(original,labels[i],x+24,y+90,24,white);}}
      if(page==5){title(original,"SETĂRI","EVO Dark Red • fără animații sau servicii permanente");row(original,186,"Acces notificări","Permite controlul YouTube Music prin MediaSession.");row(original,316,"Google Maps","Hartă interactivă live (Maps SDK cu cheie, altfel OpenStreetMap).");row(original,446,"Torque / OBD","Torque Pro gestionează ELM327; launcherul citește datele prin IPC.");row(original,576,"Protecție","Nu modificăm MCU, boot, recovery sau CANBUS.");}
      original.restore();}
   public boolean onTouchEvent(MotionEvent e){if(e.getAction()!=MotionEvent.ACTION_UP)return true;float x=e.getX()*1280/getWidth(),y=e.getY()*720/getHeight();
       if(x<109&&y>=73){int idx=(int)((y-73)/105);if(idx>=0&&idx<6)page=idx;invalidate();placeMap();return true;}
       if(page==0){if(x>=124&&x<=646)maps();else if(x>=659&&y<386){if(y>294)mediaAction(x<1000?0:x<1130?1:2);else app("com.google.android.apps.youtube.music");}else if(x>=659&&y>=389){page=3;invalidate();}}
       else if(page==1){if(y>=520&&y<=620&&x>=350&&x<=715){mediaAction(x<477?0:x<608?1:2);}else if(x>=158&&x<=1228&&y>=185&&y<520){app("com.google.android.apps.youtube.music");}}
       else if(page==2)maps();else if(page==3&&obd!=null&&!obd.current().live){try{startActivity(getPackageManager().getLaunchIntentForPackage("org.prowl.torque"));}catch(Exception ignored){}}
       else if(page==4){int col=(int)((x-158)/360),r=(int)((y-210)/181),i=r*3+col;if(col>=0&&col<3&&r>=0&&r<2){if(i==0)maps();else if(i==1)app("com.google.android.apps.youtube.music");else if(i==2)app("org.prowl.torque");else startActivity(new Intent(Settings.ACTION_SETTINGS));}}
       else if(page==5&&y>=186&&y<=300)permissions();invalidate();placeMap();return true;}
  }
}