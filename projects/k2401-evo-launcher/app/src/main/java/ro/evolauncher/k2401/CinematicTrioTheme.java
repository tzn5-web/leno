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
    // APPROVED reference is a visual screenshot and contains sample player
    // words/app icons. Full opacity is mandatory: no phantom second clock,
    // duplicated app, fake ECU data or album covers can show through.
    // Original vehicle/mountain hologram stays fully visible between bars.
    color(0xff040d1b);c.drawRect(0,0,1280,146,p);
    color(0xff040d1b);c.drawRect(0,554,1280,720,p);
    color(0x65061223);c.drawRect(0,146,22,554,p);
    color(0x65061223);c.drawRect(1258,146,1280,554,p);
  }
  private void bar(Canvas c,int id,int line){
    // Only ONE clock/date + one exterior temperature: always drawn over opaque
    // backing. No imprinted numbers or duplicated Wi-Fi/BT groups.
    // Player sits at top-centre, the SINGLE clock at top-right.
    // Separate fully opaque cards prevent any baked clock/album leakage.
    panel(c,767,8,276,94,13,0xff081725,line);
    Date now=new Date();
    String date=new SimpleDateFormat("EEE, d MMM yyyy",new Locale("ro","RO")).format(now);
    text(c,new SimpleDateFormat("HH:mm",Locale.getDefault()).format(now),854,60,39,WHITE,true,true);
    text(c,date,854,84,13,ICE,false,true);
    ObdReader.Reading rd=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    text(c,"EXT",954,36,13,LT,false,false);
    text(c,degrees(rd.ambientC),951,70,23,BLUE,true,false);
    panel(c,1053,12,213,86,12,0xff081725,line);
    boolean bt=false,wifi=false;
    try{
      bt=Settings.Global.getInt(host.getContentResolver(),"bluetooth_on",0)!=0;
      wifi=Settings.Global.getInt(host.getContentResolver(),"wifi_on",0)!=0;
    }catch(RuntimeException ignored){}
    text(c,"BT",1078,42,16,bt?BLUE:LT,true,false);
    text(c,"Wi-Fi",1151,42,16,wifi?BLUE:LT,true,false);
    text(c,"EVO",1080,77,18,ICE,true,false);
    // Label is descriptive only, never a duplicate clock or status icon.
    text(c,id==22?"A1":id==23?"02":"A3",1191,77,18,BLUE,true,false);
  }
  private void music(Canvas c,int line){
    panel(c,261,12,484,88,12,0xff081725,line);
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
      color(WHITE);c.drawBitmap(cover,null,new Rect(272,22,333,82),p);
    }else{
      panel(c,272,21,62,62,9,0xff102c4c,line);
      text(c,"♪",302,64,37,BLUE,true,true);
    }
    if(artist==null||artist.isEmpty())artist="Alege playerul";
    text(c,clip(artist,21),346,39,13,LT,false,false);
    text(c,clip(song,24),346,64,17,WHITE,true,false);
    boolean playing=m!=null&&m.getPlaybackState()!=null&&
      m.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,616,57,0,WHITE);
    MediaVectorIcons.draw(c,670,57,playing?3:1,BLUE);
    MediaVectorIcons.draw(c,724,57,2,WHITE);
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
    // Right-aligned unit stays INSIDE the card, even for "x1000 rpm".
    color(LT);p.setTextSize(13);p.setTypeface(Typeface.DEFAULT);
    p.setTextAlign(Paint.Align.RIGHT);
    c.drawText(unit,x+w-12,y+65,p);
    p.setTextAlign(Paint.Align.LEFT);
  }
  private void circle(Canvas c,float cx,float cy,float r,String key,String value,
                      String unit,float fraction,int edge){
    color(0xff081626);c.drawCircle(cx,cy,r-12,p); // opaque: no old sample-gauge ghosts
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
      // Four tall, nonoverlapping holographic meters like approved A1:
      // RPM / STFT / LTFT / TEMP APĂ. NO VOLT/BOOST placeholders.
      vertical(c,25,159,153,387,"RPM",
        Float.isFinite(r.rpm)?String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A",
        "x1000 rpm",r.rpm/8000f,line,0xff071b2f);
      vertical(c,217,159,149,387,"STFT",labelValue(r.stft,true),
        "%",(r.stft+25f)/50f,line,0xff071b2f);
      vertical(c,917,159,149,387,"LTFT",labelValue(r.ltft,true),
        "%",(r.ltft+25f)/50f,0xff55ceff,0xff071b2f);
      vertical(c,1105,159,153,387,"TEMP APĂ",degrees(r.coolantC),
        "",(r.coolantC-40)/90f,0xffa85cff,0xff071b2f);
    }else if(id==23){
      // 02: two circular blue holographic main gauges, small fuel trims
      // below the actual vehicle photo, NOT the same geometry as A1.
      ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
      // Approved 02 geometry: 2 LARGE + 2 SMALL concentric circles.
      // The four native gauges never cover the central holographic vehicle.
      circle(c,160,352,126,"RPM",Float.isFinite(r.rpm)?
        String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A","x1000 rpm",r.rpm/8000f,line);
      circle(c,371,382,78,"STFT",labelValue(r.stft,true),
        "%",(r.stft+25f)/50f,0xff47d0ff);
      circle(c,909,382,78,"LTFT",labelValue(r.ltft,true),
        "%",(r.ltft+25f)/50f,0xff45d5ff);
      circle(c,1120,352,126,"TEMP APĂ",degrees(r.coolantC),"",
        (r.coolantC-40f)/90f,0xff54dcff);
    }else{
      // A3: glass showroom, compact rectangular instrument cards on sides.
      ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
      boxGauge(c,25,230,210,98,"RPM",Float.isFinite(r.rpm)?
        String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A","x1000 rpm",line);
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
    if(y<=110&&x>=261&&x<=747){
      if(x<593)host.choosePlayer();
      else host.mediaAction(x<642?0:x<697?1:2);
      return true;
    }
    if(y<=115&&x>=767&&x<=1044){host.showSkinPicker();return true;}
    if(y>=160&&y<579&&((x<380)||(x>900))){host.showObdStatus();return true;}
    if(y>=160&&y<579){host.showObdStatus();return true;}
    return false;
  }
}
