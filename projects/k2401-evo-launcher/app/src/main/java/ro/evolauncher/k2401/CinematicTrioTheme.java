package ro.evolauncher.k2401;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.media.MediaMetadata;
import android.media.session.MediaController;
import android.media.session.PlaybackState;
import android.provider.Settings;
import java.io.IOException;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Three independent 4K-art-backed cinematic HUD variants.
 * No text, clock, demo sensor data or application logos in scene bitmaps;
 * all those elements are real, native Android Canvas components.
 *
 * 22 A1 = vertical holographic instrument pods
 * 23 02 = dual circular holographic gauges
 * 24 A3 = luxury glass showroom rectangular instruments
 *
 * The existing OBD engine, MediaSession controls and six persistent personal
 * app shortcuts are reused without changing their connection/startup logic.
 */
final class CinematicTrioTheme {
  static final int FIRST=22, LAST=24;
  private static final int BLUE=0xff42ddff, ICE=0xffc8f8ff, WHITE=0xfff5faff;
  private static final int DARK=0xff07101c, LT=0xff98b1c5;
  private final MainActivity host;
  private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  private final UltraCockpitTheme personalApps;
  private final Bitmap[] scenes=new Bitmap[3];

  CinematicTrioTheme(MainActivity h,UltraCockpitTheme apps){
    host=h;personalApps=apps;
    for(int i=0;i<3;i++){
      try(InputStream in=h.getAssets().open("skins/cinematic/scene_"+i+"_4k.webp")){
        BitmapFactory.Options o=new BitmapFactory.Options();
        // The original 3840x2160 artwork stays 4K on disk. Android decodes
        // one 1280x720 (or 1920x1080 on a high-DPI screen) copy to avoid OOM.
        o.inSampleSize=2;o.inPreferredConfig=Bitmap.Config.RGB_565;
        scenes[i]=BitmapFactory.decodeStream(in,null,o);
      }catch(IOException|RuntimeException ignored){scenes[i]=null;}
    }
  }
  void dispose(){
    for(int i=0;i<scenes.length;i++){
      if(scenes[i]!=null&&!scenes[i].isRecycled())scenes[i].recycle();
      scenes[i]=null;
    }
  }
  private void color(int c){p.setShader(null);p.setColor(c);p.setStrokeWidth(1);p.setStyle(Paint.Style.FILL);}
  private void panel(Canvas c,float x,float y,float w,float h,float radius,int fill,int line){
    color(fill);c.drawRoundRect(x,y,x+w,y+h,radius,radius,p);
    color(line);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2);
    c.drawRoundRect(x+1,y+1,x+w-1,y+h-1,radius,radius,p);
    p.setStyle(Paint.Style.FILL);
  }
  private void text(Canvas c,String s,float x,float y,float size,int col,boolean bold,boolean centre){
    color(col);p.setTextSize(size);p.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));
    p.setTextAlign(centre?Paint.Align.CENTER:Paint.Align.LEFT);c.drawText(s,x,y,p);
    p.setTextAlign(Paint.Align.LEFT);
  }
  private static String labelValue(float v,boolean signed){
    if(!Float.isFinite(v))return "N/A";
    return String.format(Locale.US,signed?"%+.1f":"%.1f",v);
  }
  private static String degrees(float v){
    return Float.isFinite(v)?String.format(Locale.US,"%.0f°C",v):"N/A";
  }
  private static float cap(float f){return Math.max(0f,Math.min(1f,f));}
  private void background(Canvas c,int id){
    int i=id-FIRST;
    color(DARK);c.drawColor(DARK);
    Bitmap im=scenes[i];
    if(im!=null&&!im.isRecycled()){
      color(Color.WHITE);p.setFilterBitmap(true);
      c.drawBitmap(im,null,new Rect(0,0,1280,720),p);
    }else{
      // Only a backup if an Android OEM decoder fails. Never draw fake data.
      color(0xff0a1b32);p.setShader(new LinearGradient(0,0,0,720,
        0xff0a1830,0xff030811,Shader.TileMode.CLAMP));c.drawRect(0,0,1280,720,p);p.setShader(null);
    }
    // Vary lighting without overprinting the imported photographic artwork.
    color(0x8d040b17);c.drawRect(0,0,1280,128,p);
    color(0x9d040a14);c.drawRect(0,594,1280,720,p);
    color(0xa0081324);c.drawRect(0,120,150,590,p);
    color(0xa0081324);c.drawRect(1125,120,1280,590,p);
  }
  private void bar(Canvas c,int id,int line){
    // Only ONE clock/date + one exterior temperature: always drawn over opaque
    // backing. No imprinted numbers or duplicated Wi-Fi/BT groups.
    panel(c,387,8,394,94,13,0xff081725,line);
    Date now=new Date();
    String date=new SimpleDateFormat("EEE, d MMM yyyy",new Locale("ro","RO")).format(now);
    text(c,new SimpleDateFormat("HH:mm",Locale.getDefault()).format(now),517,59,42,WHITE,true,true);
    text(c,date,517,82,14,ICE,false,true);
    ObdReader.Reading rd=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    text(c,"EXTERIOR",655,34,13,LT,false,false);
    text(c,degrees(rd.ambientC),653,70,25,BLUE,true,false);
    panel(c,1071,12,195,86,12,0xff081725,line);
    boolean bt=false,wifi=false;
    try{
      bt=Settings.Global.getInt(host.getContentResolver(),"bluetooth_on",0)!=0;
      wifi=Settings.Global.getInt(host.getContentResolver(),"wifi_on",0)!=0;
    }catch(RuntimeException ignored){}
    text(c,"BT",1097,42,16,bt?BLUE:LT,true,false);
    text(c,"Wi-Fi",1170,42,16,wifi?BLUE:LT,true,false);
    text(c,"EVO",1098,77,18,ICE,true,false);
    // Exact selected theme label, not an additional permanent clock.
    text(c,id==22?"A1":id==23?"02":"A3",1199,77,18,BLUE,true,false);
  }
  private void music(Canvas c,int line){
    panel(c,20,12,344,88,12,0xff081725,line);
    MediaController m=host.media;
    String artist=host.mediaName,song="Nicio redare";
    Bitmap cover=null;
    if(m!=null&&m.getMetadata()!=null){
      MediaMetadata meta=m.getMetadata();
      CharSequence t=meta.getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence a=meta.getText(MediaMetadata.METADATA_KEY_ARTIST);
      if(t!=null&&!t.toString().isEmpty())song=t.toString();
      if(a!=null&&!a.toString().isEmpty())artist=a.toString();
      cover=meta.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
      if(cover==null)cover=meta.getBitmap(MediaMetadata.METADATA_KEY_ART);
    }
    if(cover!=null&&!cover.isRecycled()){
      color(WHITE);c.drawBitmap(cover,null,new Rect(30,22,90,82),p);
    }else{
      panel(c,30,21,62,62,9,0xff102c4c,line);
      text(c,"♪",60,64,37,BLUE,true,true);
    }
    if(artist==null||artist.isEmpty())artist="Alege playerul";
    text(c,clip(artist,16),101,37,13,LT,false,false);
    text(c,clip(song,18),101,57,16,WHITE,true,false);
    boolean playing=m!=null&&m.getPlaybackState()!=null&&
      m.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,200,77,0,WHITE);
    MediaVectorIcons.draw(c,250,77,playing?3:1,BLUE);
    MediaVectorIcons.draw(c,302,77,2,WHITE);
  }
  private static String clip(String s,int limit){
    if(s==null)return "";
    return s.length()<=limit?s:s.substring(0,limit-1)+"…";
  }
  private void vertical(Canvas c,int x,int y,int w,int h,String key,String value,String unit,
                        float fraction,int edge,int fill){
    panel(c,x,y,w,h,18,fill,edge);
    text(c,key,x+w/2f,y+43,18,ICE,true,true);
    text(c,value,x+w/2f,y+96,38,WHITE,true,true);
    text(c,unit,x+w/2f,y+119,15,LT,false,true);
    color(0xff1a344a);c.drawRoundRect(x+w/2f-28,y+150,x+w/2f+28,y+h-25,6,6,p);
    if(Float.isFinite(fraction)){
      int bottom=y+h-27;
      int top=y+152;
      int filled=(int)((bottom-top)*cap(fraction));
      color(edge);
      c.drawRoundRect(x+w/2f-27,bottom-filled,x+w/2f+27,bottom,5,5,p);
    }
    for(int t=0;t<=6;t++){
      int yy=y+153+(h-180)*t/6;
      color(0xff5e8fa6);c.drawRect(x+w/2f+35,yy,x+w/2f+46,yy+2,p);
    }
  }
  private void boxGauge(Canvas c,int x,int y,int w,int h,String label,String value,
                        String unit,int edge){
    panel(c,x,y,w,h,11,0xf6071929,edge);
    text(c,label,x+15,y+27,15,ICE,true,false);
    text(c,value,x+15,y+65,32,WHITE,true,false);
    text(c,unit,x+w-29,y+65,15,LT,false,false);
  }
  private void circle(Canvas c,float cx,float cy,float r,String key,String value,
                      String unit,float fraction,int edge){
    color(0xf6081626);c.drawCircle(cx,cy,r-12,p);
    color(0xff294259);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(15);
    c.drawArc(cx-r,cy-r,cx+r,cy+r,132,276,false,p);
    if(Float.isFinite(fraction)){
      color(edge);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(16);
      c.drawArc(cx-r,cy-r,cx+r,cy+r,132,276*cap(fraction),false,p);
    }
    // Always render a THIN neon ring, never a filled pie/disk.
    color(0xff5f819e);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.5f);
    c.drawCircle(cx,cy,r-19,p);p.setStyle(Paint.Style.FILL);
    for(int k=0;k<=12;k++){
      double angle=Math.toRadians(132.0+276.0*k/12);
      float xa=cx+(r-25)*(float)Math.cos(angle),ya=cy+(r-25)*(float)Math.sin(angle);
      float xb=cx+(r-11)*(float)Math.cos(angle),yb=cy+(r-11)*(float)Math.sin(angle);
      color(0xff9acde7);p.setStrokeWidth(2);c.drawLine(xa,ya,xb,yb,p);
    }
    text(c,key,cx,cy-46,19,ICE,true,true);
    text(c,value,cx,cy+18,53,WHITE,true,true);
    text(c,unit,cx,cy+52,17,LT,false,true);
  }
  void draw(Canvas c,int id){
    if(id<FIRST||id>LAST)return;
    int line=id==24?0xff78d7fa:0xff20bafc;
    background(c,id);
    if(id==22){
      // The approved A1 tall holographic readouts flanking the front-view car.
      ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
      vertical(c,25,174,156,400,"RPM",
        Float.isFinite(r.rpm)?String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A",
        "x1000 rpm",r.rpm/8000f,line,0xe5092035);
      vertical(c,1100,174,155,400,"TEMP APĂ",degrees(r.coolantC),
        "",(r.coolantC-40)/90f,0xffc65fff,0xe5092035);
      boxGauge(c,220,479,161,87,"STFT",labelValue(r.stft,true),"%",line);
      boxGauge(c,902,479,162,87,"LTFT",labelValue(r.ltft,true),"%",line);
    }else if(id==23){
      // 02: two circular blue holographic main gauges, small fuel trims
      // below the actual vehicle photo, NOT the same geometry as A1.
      ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
      circle(c,202,344,145,"RPM",Float.isFinite(r.rpm)?
        String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A","x1000 rpm",r.rpm/8000f,line);
      circle(c,1078,344,145,"TEMP APĂ",degrees(r.coolantC),"",
        (r.coolantC-40f)/90f,0xff54dcff);
      boxGauge(c,430,481,179,87,"STFT",labelValue(r.stft,true),"%",line);
      boxGauge(c,675,481,179,87,"LTFT",labelValue(r.ltft,true),"%",line);
    }else{
      // A3: glass showroom, compact rectangular instrument cards on sides.
      ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
      boxGauge(c,25,230,210,98,"RPM",Float.isFinite(r.rpm)?
        String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A","k",line);
      boxGauge(c,25,349,210,98,"STFT",labelValue(r.stft,true),"%",line);
      boxGauge(c,1045,230,210,98,"TEMP APĂ",degrees(r.coolantC),"",line);
      boxGauge(c,1045,349,210,98,"LTFT",labelValue(r.ltft,true),"%",line);
    }
    music(c,line);
    bar(c,id,line);
    // Exactly six live application shortcuts. All are click/hold-driven and
    // persisted under the original same app's SharedPreferences.
    personalApps.drawUserSlots(c);
  }
  boolean touch(float x,float y){
    if(y<=110&&x>=20&&x<=365){
      if(x<178)host.choosePlayer();
      else host.mediaAction(x<229?0:x<278?1:2);
      return true;
    }
    if(y<=115&&x>=387&&x<=781){host.showSkinPicker();return true;}
    if(y>=160&&y<579&&((x<380)||(x>900))){host.showObdStatus();return true;}
    if(y>=160&&y<579){host.showObdStatus();return true;}
    return false;
  }
}
