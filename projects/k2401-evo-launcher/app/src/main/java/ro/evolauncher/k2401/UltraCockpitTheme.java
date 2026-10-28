package ro.evolauncher.k2401;

import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.media.MediaMetadata;
import android.media.session.MediaController;
import android.media.session.PlaybackState;
import android.os.Handler;
import android.os.Looper;
import android.view.HapticFeedbackConstants;

import java.io.IOException;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;

/**
 * Opt-in 22nd skin: vector-drawn, resolution-independent cockpit.
 * Visual-only: existing OBD, MediaSession and launcher actions own ALL data.
 * Six persistent user-selected applications are drawn UNDER STFT/LTFT.
 * Tap launches, press-and-hold 550 ms changes any slot.
 */
final class UltraCockpitTheme {
  private static final int WHITE=0xffecf7ff, CYAN=0xff27d5ff, RED=0xffff315c;
  private static final int BG=0xff050b16;
  private static final int SLOT_COUNT=6;
  private static final int SLOT_X=427,SLOT_Y=609,SLOT_W=67,SLOT_H=71,SLOT_GAP=7;
  private final MainActivity host;
  private final SharedPreferences prefs;
  private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  private final String[] slots=new String[SLOT_COUNT];
  private final Drawable[] icons=new Drawable[SLOT_COUNT];
  private Bitmap approvedWallpaper;
  private final Handler ui=new Handler(Looper.getMainLooper());
  private int down=-1;
  private float downX,downY;
  private boolean longPressed;
  private Runnable longPressJob;

  UltraCockpitTheme(MainActivity host){
    this.host=host;
    prefs=host.getSharedPreferences("evo_launcher_prefs",0);
    for(int i=0;i<SLOT_COUNT;i++)slots[i]=prefs.getString("ultra_app_slot_"+i,"");
    try(InputStream image=host.getAssets().open("skins/approved/ultra-neon-2560x1440.webp")){
      BitmapFactory.Options options=new BitmapFactory.Options();
      options.inPreferredConfig=Bitmap.Config.ARGB_8888;
      options.inSampleSize=2; // 2560x1440 archived, 1280x720 display RAM
      approvedWallpaper=BitmapFactory.decodeStream(image,null,options);
    }catch(IOException|RuntimeException ignored){approvedWallpaper=null;}
  }
  private void color(int value){p.setColor(value);p.setStyle(Paint.Style.FILL);p.setShader(null);p.setStrokeWidth(1);}
  private void rect(Canvas c,float x,float y,float w,float h,float r,int col){
    color(col);c.drawRoundRect(x,y,x+w,y+h,r,r,p);
  }
  private void line(Canvas c,float x,float y,float xx,float yy,int col,float width){
    color(col);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(width);
    p.setStrokeCap(Paint.Cap.ROUND);c.drawLine(x,y,xx,yy,p);p.setStyle(Paint.Style.FILL);
  }
  private void stroke(Canvas c,float x,float y,float w,float h,float r,int col,float width){
    color(col);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(width);
    c.drawRoundRect(x,y,x+w,y+h,r,r,p);p.setStyle(Paint.Style.FILL);
  }
  private void label(Canvas c,String s,float x,float y,float size,int col,boolean bold){
    color(col);p.setTextAlign(Paint.Align.LEFT);
    p.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));
    p.setTextSize(size);c.drawText(s,x,y,p);
  }
  private void center(Canvas c,String s,float x,float y,float size,int col,boolean bold){
    color(col);p.setTextAlign(Paint.Align.CENTER);
    p.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));
    p.setTextSize(size);c.drawText(s,x,y,p);p.setTextAlign(Paint.Align.LEFT);
  }
  private static String trimmed(String s,int cap){
    if(s==null||s.isEmpty())return "";
    return s.length()<=cap?s:s.substring(0,cap-1)+"…";
  }
  private static String reading(float v,int decimals){
    if(!Float.isFinite(v))return "N/A";
    return String.format(Locale.US,decimals==0?"%.0f":decimals==1?"%+.1f":"%.2f",v);
  }
  private static float ratio(float value,float min,float max){
    return Math.max(0f,Math.min(1f,(value-min)/(max-min)));
  }
  private void neon(Canvas c,float x,float y,float radius,float from,float to,
                    float current,int colour){
    // Static full perimeter decoration is not a live sensor measurement.
    color(0xff29445b);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(radius>100?6f:4f);
    c.drawArc(x-radius,y-radius,x+radius,y+radius,133,273,false,p);
    if(Float.isFinite(current)){
      color(colour);p.setStyle(Paint.Style.STROKE);p.setStrokeCap(Paint.Cap.ROUND);
      p.setStrokeWidth(radius>100?9f:6f);
      c.drawArc(x-radius,y-radius,x+radius,y+radius,133,273*ratio(current,from,to),false,p);
    }
    p.setStyle(Paint.Style.FILL);
  }
  private void gauge(Canvas c,float cx,float cy,float radius,String heading,String value,
                     String unit,float current,float minimum,float maximum,int mainColour,
                     boolean large){
    // Opaque dynamic centre hides static artwork, preventing sample numbers.
    if(approvedWallpaper!=null){
      color(0xff06101c);c.drawCircle(cx,cy,radius*(large?.66f:.67f),p);
      // Art's original outer chrome/neon ring is decoration only.
      // A separate INNER arc displays actual ECU progress.
      neon(c,cx,cy,radius-(large?29f:16f),minimum,maximum,current,mainColour);
      center(c,heading,cx,cy-(large?54:23),large?19:16,0xff90d8f4,true);
      center(c,value,cx,cy+(large?13:18),large?54:36,WHITE,true);
      center(c,unit,cx,cy+(large?46:39),large?19:14,0xffc0d7e6,false);
      if(!Float.isFinite(current))
        center(c,"ECU N/A",cx,cy+radius*.55f,12,0xff93a7ba,false);
      return;
    }
    color(0xf807101d);c.drawCircle(cx,cy,radius-20,p);
    color(0xff0c2237);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2);
    c.drawCircle(cx,cy,radius-19,p);p.setStyle(Paint.Style.FILL);
    neon(c,cx,cy,radius,minimum,maximum,current,mainColour);
    for(int i=0;i<=12;i++){
      float angle=(float)Math.toRadians(133+273*i/12f);
      float ax=cx+(radius-14)*(float)Math.cos(angle);
      float ay=cy+(radius-14)*(float)Math.sin(angle);
      float bx=cx+(radius-5)*(float)Math.cos(angle);
      float by=cy+(radius-5)*(float)Math.sin(angle);
      line(c,ax,ay,bx,by,0xff8badc5,large?2.2f:1.2f);
    }
    center(c,heading,cx,cy-(large?54:23),large?19:16,0xff90d8f4,true);
    center(c,value,cx,cy+(large?13:18),large?54:36,WHITE,true);
    center(c,unit,cx,cy+(large?46:39),large?19:14,0xffc0d7e6,false);
    if(!Float.isFinite(current))
      center(c,"ECU N/A",cx,cy+radius*.65f,12,0xff93a7ba,false);
  }
  private void drawBackdrop(Canvas c){
    // The EXACT user-approved screenshot is embedded in the signed APK.
    // The printed sample data on it is covered below by native live widgets.
    if(approvedWallpaper!=null&&!approvedWallpaper.isRecycled()){
      color(Color.WHITE);p.setFilterBitmap(true);
      c.drawBitmap(approvedWallpaper,null,new Rect(0,0,1280,720),p);
      return;
    }
    color(BG);c.drawColor(BG);
    color(WHITE);
    p.setShader(new LinearGradient(0,170,1280,700,0xff15223d,0xff040a14,
      Shader.TileMode.CLAMP));
    c.drawRect(85,150,1280,720,p);p.setShader(null);
    // A perspective, wet road behind the four vector gauges.
    Path road=new Path();road.moveTo(710,302);road.lineTo(950,720);
    road.lineTo(377,720);road.close();
    color(0xff0e1930);c.drawPath(road,p);
    for(int i=0;i<8;i++){
      float y=340+i*i*5.1f;float half=6+i*i*4.8f;
      line(c,706-half,y,706-half-8,y+9,0xff123960,1.5f+i*.15f);
      line(c,706+half,y,706+half+8,y+9,0xff681e4c,1.5f+i*.15f);
    }
    // Night skyline and a tiny Mitsubishi-style car silhouette; illustrative, not ECU data.
    for(int i=0;i<25;i++){
      int x=468+i*17;
      int h=22+(i*31%59);
      rect(c,x,332-h,12,h,1,0xff0a1727);
    }
    color(0xff121c2c);c.drawRoundRect(660,356,761,391,15,15,p);
    stroke(c,652,367,116,23,12,0xff335c83,1.5f);
    line(c,654,381,674,383,RED,5);line(c,752,383,769,381,RED,5);
    line(c,657,384,772,384,0xff1a2239,2);
    // HUD corner filaments; all scalable Canvas paths (no pixelated labels).
    line(c,93,162,296,162,CYAN,2.0f);line(c,93,162,93,194,CYAN,2);
    line(c,1267,162,1060,162,RED,2);line(c,1267,162,1267,194,RED,2);
    line(c,93,693,312,693,RED,1.5f);line(c,1267,693,1045,693,CYAN,1.5f);
  }
  private void drawRail(Canvas c){
    rect(c,0,0,87,720,0,0xf9060e1c);
    final int[] ys={73,171,269,367,465,563,661};
    for(int i=0;i<7;i++){
      final int a=i==0?RED:0xffd9edff;
      if(i==0)rect(c,5,23,77,93,8,0xff261c32);
      // Same native vector navigation graphics as other K2401 skins.
      NavVectorIcons.draw(c,Math.min(5,i),44,ys[i],a);
      if(i==0)line(c,86,32,86,118,RED,3);
    }
  }
  private void drawMusic(Canvas c){
    rect(c,113,12,1152,128,17,0xf407111e);
    stroke(c,113,12,1152,128,17,0xff235887,2);
    MediaController m=host.media;
    String song="",artist="";
    Bitmap cover=null;
    if(m!=null&&m.getMetadata()!=null){
      MediaMetadata md=m.getMetadata();
      CharSequence title=md.getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence who=md.getText(MediaMetadata.METADATA_KEY_ARTIST);
      song=title==null?"":title.toString();
      artist=who==null?"":who.toString();
      cover=md.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
      if(cover==null)cover=md.getBitmap(MediaMetadata.METADATA_KEY_ART);
    }
    rect(c,270,23,73,75,7,0xff113452);
    if(cover!=null){
      color(WHITE);p.setFilterBitmap(true);
      c.drawBitmap(cover,null,new Rect(272,25,341,96),p);
    }else center(c,"♪",305,74,37,CYAN,true);
    if(song.isEmpty())song="Fără redare activă";
    if(artist.isEmpty())artist=host.mediaName;
    label(c,trimmed(artist,27),356,56,17,0xffc3d8e8,false);
    label(c,trimmed(song,28),356,82,21,WHITE,true);
    line(c,359,107,714,107,0xff33485b,3);
    if(m!=null&&m.getPlaybackState()!=null&&m.getMetadata()!=null){
      long dur=m.getMetadata().getLong(MediaMetadata.METADATA_KEY_DURATION);
      long pos=m.getPlaybackState().getPosition();
      if(dur>0&&pos>=0)line(c,359,107,359+355*ratio(pos,0,dur),107,CYAN,4);
    }
    boolean playing=m!=null&&m.getPlaybackState()!=null&&
      m.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,785,76,0,WHITE);
    rect(c,827,30,75,75,37,0xff0f375b);
    stroke(c,827,30,75,75,37,CYAN,2);
    MediaVectorIcons.draw(c,865,69,playing?3:1,WHITE);
    MediaVectorIcons.draw(c,950,76,2,WHITE);
    // Single system indicators cluster, top-right only.
    label(c,"BT  ·  Wi-Fi",1052,49,15,0xffc3d8e8,false);
    label(c,new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date()),
      1161,83,27,WHITE,true);
  }
  private void drawTime(Canvas c){
    rect(c,454,164,399,112,14,0xe50a1629);
    stroke(c,454,164,399,112,14,0xff236498,1.4f);
    String hh=new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date());
    String dt=new SimpleDateFormat("EEE, d MMM yyyy",new Locale("ro","RO")).format(new Date());
    center(c,hh,654,221,53,WHITE,true);
    label(c,trimmed(dt,28),477,257,15,0xffc7d9e9,false);
    // Ambient temperature PID 0x0146 not yet present in existing verified
    // OBD reader. Never display a fake car temperature or a weather API value.
    label(c,"EXT: ECU N/A",711,255,15,CYAN,false);
  }
  private void drawSlots(Canvas c){
    for(int i=0;i<SLOT_COUNT;i++){
      int x=SLOT_X+i*(SLOT_W+SLOT_GAP),y=SLOT_Y;
      rect(c,x,y,SLOT_W,SLOT_H,12,0xed0c1931);
      stroke(c,x,y,SLOT_W,SLOT_H,12,i%2==0?CYAN:RED,1.7f);
      String pkg=slots[i];
      if(pkg==null||pkg.isEmpty()){
        center(c,"+",x+SLOT_W/2f,y+46,36,WHITE,true);
        continue;
      }
      if(icons[i]==null){
        try{icons[i]=host.getPackageManager().getApplicationIcon(pkg);}
        catch(PackageManager.NameNotFoundException ex){slots[i]="";center(c,"+",x+SLOT_W/2f,y+46,36,WHITE,true);continue;}
      }
      Drawable icon=icons[i];
      icon.setBounds(x+17,y+8,x+SLOT_W-17,y+41);
      icon.draw(c);
      String appName=pkg;
      try{appName=String.valueOf(host.getPackageManager().getApplicationLabel(
        host.getPackageManager().getApplicationInfo(pkg,0)));}
      catch(PackageManager.NameNotFoundException ignored){}
      center(c,trimmed(appName,9),x+SLOT_W/2f,y+61,9,0xffd0e5f5,true);
    }
  }
  void draw(Canvas c){
    drawBackdrop(c);drawRail(c);drawMusic(c);drawTime(c);
    ObdReader.Reading rd=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    String rpm=Float.isFinite(rd.rpm)?
      String.format(Locale.US,"%.1f",rd.rpm/1000f):"N/A";
    gauge(c,282,380,165,"RPM",rpm,"x1000 rpm",
      rd.rpm,0,8000,RED,true);
    gauge(c,1047,380,164,"TEMP APĂ",reading(rd.coolantC,0),"°C",
      rd.coolantC,40,130,CYAN,true);
    gauge(c,551,492,79,"STFT",reading(rd.stft,1),"%",rd.stft,-25,25,CYAN,false);
    gauge(c,773,492,79,"LTFT",reading(rd.ltft,1),"%",rd.ltft,-25,25,RED,false);
    drawSlots(c);
  }
  private int slotAt(float x,float y){
    if(y<SLOT_Y||y>SLOT_Y+SLOT_H)return -1;
    for(int i=0;i<SLOT_COUNT;i++){
      int xx=SLOT_X+i*(SLOT_W+SLOT_GAP);
      if(x>=xx&&x<=xx+SLOT_W)return i;
    }
    return -1;
  }
  void down(float x,float y){
    cancel();
    down=slotAt(x,y);downX=x;downY=y;longPressed=false;
    if(down>=0){
      final int slot=down;
      longPressJob=()->{
        if(down==slot&&!longPressed){
          longPressed=true;
          down=-1;
          if(host.view!=null)host.view.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
          choose(slot);
        }
      };
      ui.postDelayed(longPressJob,550);
    }
  }
  void move(float x,float y){
    if(down>=0&&(Math.abs(x-downX)>18||Math.abs(y-downY)>18||
                 slotAt(x,y)!=down))cancel();
  }
  void cancel(){
    if(longPressJob!=null)ui.removeCallbacks(longPressJob);
    longPressJob=null;
    down=-1;
  }
  boolean up(float x,float y){
    int slot=down;
    boolean wasLong=longPressed;
    cancel();
    longPressed=false;
    if(wasLong)return true;
    if(slot>=0&&slotAt(x,y)==slot){
      openSlot(slot);return true;
    }
    return touch(x,y);
  }
  private void openSlot(int index){
    String pkg=slots[index];
    if(pkg==null||pkg.isEmpty()){choose(index);return;}
    Intent launch=host.getPackageManager().getLaunchIntentForPackage(pkg);
    if(launch==null){choose(index);return;}
    try{host.startActivity(launch);}
    catch(RuntimeException e){choose(index);}
  }
  private void choose(int index){
    PackageManager pm=host.getPackageManager();
    List<ResolveInfo> candidates=pm.queryIntentActivities(new Intent(Intent.ACTION_MAIN)
      .addCategory(Intent.CATEGORY_LAUNCHER),0);
    ArrayList<String> packages=new ArrayList<>();
    ArrayList<String> names=new ArrayList<>();
    HashSet<String> seen=new HashSet<>();
    for(ResolveInfo r:candidates){
      if(r.activityInfo==null)continue;
      String packageName=r.activityInfo.packageName;
      if(packageName.equals(host.getPackageName())||!seen.add(packageName)||
         pm.getLaunchIntentForPackage(packageName)==null)continue;
      packages.add(packageName);
      names.add(String.valueOf(r.loadLabel(pm)));
    }
    ArrayList<Integer> order=new ArrayList<>();
    for(int i=0;i<packages.size();i++)order.add(i);
    Collections.sort(order,(a,b)->names.get(a).compareToIgnoreCase(names.get(b)));
    final ArrayList<String> sortedPackages=new ArrayList<>();
    final ArrayList<String> sortedNames=new ArrayList<>();
    for(int id:order){sortedPackages.add(packages.get(id));sortedNames.add(names.get(id));}
    sortedNames.add(0,"+ Golește acest slot");
    new AlertDialog.Builder(host)
      .setTitle("Aplicația "+(index+1)+" • ține apăsat pentru schimbare")
      .setItems(sortedNames.toArray(new String[0]),(dialog,choice)->{
        String pkg=choice==0?"":sortedPackages.get(choice-1);
        slots[index]=pkg;
        icons[index]=null;
        prefs.edit().putString("ultra_app_slot_"+index,pkg).apply();
        if(host.view!=null)host.view.invalidate();
      }).setNegativeButton("Anulează",null).show();
  }
  boolean touch(float x,float y){
    int slot=slotAt(x,y);
    if(slot>=0){openSlot(slot);return true;}
    if(x<=87){
      int idx=Math.round((y-73f)/98f);
      if(idx>=0&&idx<7&&Math.abs(y-(73+idx*98))<45){
        if(idx==1||idx==6){host.showInstalledApps();return true;}
        int[] pages={0,4,2,1,3,5,4};
        host.page=pages[idx];
        if(host.view!=null)host.view.invalidate();
        host.placeMap();return true;
      }
    }
    if(y<145&&x>=730&&x<=1005){
      host.mediaAction(x<819?0:x<919?1:2);return true;
    }
    if(y<145&&x>=113&&x<730){host.choosePlayer();return true;}
    if(y<276&&x>=454&&x<=853){host.showSkinPicker();return true;}
    if(y>=285&&x>=100&&x<1250){host.showObdStatus();return true;}
    return false;
  }
  void release(){cancel();
    if(approvedWallpaper!=null&&!approvedWallpaper.isRecycled())approvedWallpaper.recycle();
    approvedWallpaper=null;
  }
}
