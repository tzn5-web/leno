package ro.evolauncher.k2401;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Shader;
import android.media.MediaMetadata;
import android.media.session.MediaController;
import android.media.session.PlaybackState;
import android.provider.Settings;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Approved RACE HUD FINAL: flowing carbon/white/silver/red angular-wing UI.
 * Draws every OBD reading, timestamp, media label and installed app icon LIVE;
 * NONE is baked into wallpaper. Vectors scale from 1280x720 to any display.
 * Center x=429..851, y=196..492 is reserved for LiveMapPanel, an actual
 * Google Maps SDK MapView (when a valid key/Play Services exist), or native
 * OSM map as a fallback. It is NOT a pretend Google Maps screenshot.
 */
final class RaceHudFinalTheme {
  static final int ID=25;
  static final int MAP_X=432,MAP_Y=196,MAP_W=416,MAP_H=291;
  private static final int WHITE=0xfff5f7fc, SILVER=0xffa9b5c3,
      RED=0xffea2845, LIT=0xfff85d64, DARK=0xff06090f;
  private final MainActivity host;
  private final UltraCockpitTheme slots;
  private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  RaceHudFinalTheme(MainActivity activity,UltraCockpitTheme userSlots){
    host=activity;slots=userSlots;
  }
  private void fill(int color){p.setShader(null);p.setColor(color);
    p.setStyle(Paint.Style.FILL);p.setStrokeWidth(1);}
  private void segment(Canvas c,float x1,float y1,float x2,float y2,int col,float width){
    fill(col);p.setStrokeWidth(width);c.drawLine(x1,y1,x2,y2,p);
  }
  private void label(Canvas c,String str,float x,float y,int sz,int col,boolean bold,boolean center){
    fill(col);p.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));
    p.setTextSize(sz);p.setTextAlign(center?Paint.Align.CENTER:Paint.Align.LEFT);
    c.drawText(str,x,y,p);p.setTextAlign(Paint.Align.LEFT);
  }
  private void plate(Canvas c,float x,float y,float w,float h,int edge,int background){
    Path path=new Path();
    path.moveTo(x+13,y);path.lineTo(x+w-16,y);path.lineTo(x+w,y+15);
    path.lineTo(x+w,y+h-11);path.lineTo(x+w-14,y+h);
    path.lineTo(x+12,y+h);path.lineTo(x,y+h-12);path.lineTo(x,y+12);
    path.close();fill(background);c.drawPath(path,p);
    fill(edge);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.7f);
    c.drawPath(path,p);p.setStyle(Paint.Style.FILL);
  }
  private void wings(Canvas c){
    c.drawColor(DARK);
    fill(WHITE);
    p.setShader(new LinearGradient(0,0,1280,720,
      new int[]{0xff060a12,0xff111822,0xff06070b},
      new float[]{0f,.45f,1f},Shader.TileMode.CLAMP));
    c.drawRect(0,0,1280,720,p);p.setShader(null);
    for(int side=0;side<2;side++){
      c.save();
      if(side==1){c.translate(1280,0);c.scale(-1,1);}
      // Sculptural angular wings echo the approved red/white original concept.
      for(int j=0;j<4;j++){
        float y=117+j*28;
        segment(c,0,y,34+j*8,y+13,SILVER,2);
        segment(c,34+j*8,y+13,142+j*11,y+13,RED,1.7f);
      }
      segment(c,0,168,45,203,SILVER,7);
      segment(c,45,203,105,203,RED,4);
      segment(c,0,548,68,516,SILVER,3);
      segment(c,68,516,131,516,RED,3);
      segment(c,0,601,143,571,WHITE,3);
      segment(c,143,571,303,571,RED,2);
      c.restore();
    }
    // A thin bright metallic/white upper arc, never duplicated status widgets.
    segment(c,0,99,1280,99,0xff7e8794,1.3f);
    segment(c,15,106,208,106,WHITE,2);
    segment(c,1075,106,1265,106,WHITE,2);
    segment(c,390,109,890,109,RED,1);
  }
  private String number(float value,int decimal,boolean sign){
    if(!Float.isFinite(value))return "N/A";
    return String.format(Locale.US,sign?(decimal==0?"%+.0f":"%+.1f"):
      (decimal==0?"%.0f":"%.1f"),value);
  }
  private void arc(Canvas c,float cx,float cy,float radius,float value,
      float min,float max,int edge){
    fill(0xff111923);c.drawCircle(cx,cy,radius-10,p);
    fill(0xffe8edf5);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(4);
    c.drawArc(cx-radius,cy-radius,cx+radius,cy+radius,133,273,false,p);
    fill(0xff394452);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(18);
    c.drawArc(cx-radius+9,cy-radius+9,cx+radius-9,cy+radius-9,134,270,false,p);
    if(Float.isFinite(value)){
      float frac=Math.max(0,Math.min(1,(value-min)/(max-min)));
      fill(edge);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(18);
      c.drawArc(cx-radius+9,cy-radius+9,cx+radius-9,cy+radius-9,
        134,270*frac,false,p);
    }
    p.setStyle(Paint.Style.FILL);
    for(int t=0;t<=12;t++){
      double a=Math.toRadians(134+t*270/12.);
      float r1=radius-4,r2=radius-20;
      segment(c,cx+(float)Math.cos(a)*r1,cy+(float)Math.sin(a)*r1,
        cx+(float)Math.cos(a)*r2,cy+(float)Math.sin(a)*r2,
        t>=9?RED:WHITE,t%3==0?2.4f:1);
    }
  }
  private void gauge(Canvas c,int cx,int cy,String title,String value,String units,
      float sensor,float min,float max){
    arc(c,cx,cy,155,sensor,min,max,RED);
    label(c,title,cx,cy-57,21,WHITE,true,true);
    label(c,value,cx,cy+22,52,WHITE,true,true);
    label(c,units,cx,cy+51,15,SILVER,false,true);
  }
  private void trim(Canvas c,int x,String title,float value){
    plate(c,x,516,215,76,0xffb0becb,0xee080e18);
    label(c,title,x+22,539,16,SILVER,true,false);
    label(c,number(value,1,true)+(Float.isFinite(value)?"%":""),x+114,552,28,WHITE,true,true);
    fill(0xff37414e);c.drawRoundRect(x+20,567,x+196,576,4,4,p);
    if(Float.isFinite(value)){
      float frac=Math.max(0,Math.min(1,(value+25f)/50f));
      fill(RED);c.drawRoundRect(x+20,567,x+20+176*frac,576,4,4,p);
    }
  }
  private static String shorten(String s,int max){
    if(s==null)return "";
    return s.length()<=max?s.substring(0,max-1)+"…";
  }
  private void top(Canvas c){
    plate(c,9,8,193,85,SILVER,0xff070b11);
    Date now=new Date();
    label(c,new SimpleDateFormat("HH:mm",Locale.getDefault()).format(now),
      22,45,30,WHITE,true,false);
    label(c,new SimpleDateFormat("EEE, d MMM yyyy",new Locale("ro","RO")).format(now),
      23,64,12,SILVER,false,false);
    ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    label(c,"EXT "+(Float.isFinite(r.ambientC)?
      String.format(Locale.US,"%.0f°C",r.ambientC):"N/A"),23,83,14,WHITE,true,false);
    final String[] actions={"SETUP","APPS","NAVI","MUZICĂ"};
    final int[] icons={5,4,2,1};
    final int[] xs={212,292,990,1070};
    for(int i=0;i<4;i++){
      plate(c,xs[i],11,73,77,SILVER,0xff0a1018);
      NavVectorIcons.draw(c,icons[i],xs[i]+36,37,RED);
      label(c,actions[i],xs[i]+36,71,i==3?11:12,WHITE,true,true);
    }
    plate(c,375,8,605,85,0xfff1f4fa,0xff090f18);
    MediaController media=host.media;
    String artist=host.mediaName,song="Nicio redare";
    android.graphics.Bitmap album=null;
    if(media!=null&&media.getMetadata()!=null){
      MediaMetadata m=media.getMetadata();
      CharSequence a=m.getText(MediaMetadata.METADATA_KEY_ARTIST);
      CharSequence t=m.getText(MediaMetadata.METADATA_KEY_TITLE);
      if(a!=null)artist=a.toString();
      if(t!=null)song=t.toString();
      album=m.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
      if(album==null)album=m.getBitmap(MediaMetadata.METADATA_KEY_ART);
    }
    if(album!=null&&!album.isRecycled()){fill(WHITE);c.drawBitmap(album,null,new Rect(387,20,444,79),p);}
    else{plate(c,386,17,59,63,RED,0xff141e2c);label(c,"♪",416,60,37,WHITE,true,true);}
    label(c,shorten(artist,24),458,36,14,SILVER,false,false);
    label(c,shorten(song,24),458,58,18,WHITE,true,false);
    boolean playing=media!=null&&media.getPlaybackState()!=null&&
      media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,798,54,0,WHITE);
    MediaVectorIcons.draw(c,863,54,playing?3:1,WHITE);
    MediaVectorIcons.draw(c,932,54,2,WHITE);
    segment(c,459,75,737,75,0xff667381,3);
    // One real system-status group; no duplicate Wi-Fi/BT placeholders.
    plate(c,1154,11,115,77,SILVER,0xff0a1018);
    boolean bt=false,wifi=false;
    try{
      bt=Settings.Global.getInt(host.getContentResolver(),"bluetooth_on",0)!=0;
      wifi=Settings.Global.getInt(host.getContentResolver(),"wifi_on",0)!=0;
    }catch(RuntimeException ignored){}
    label(c,"BT",1168,40,18,bt?WHITE:0xff606a78,true,false);
    label(c,"Wi-Fi",1204,40,16,wifi?WHITE:0xff606a78,true,false);
    label(c,"FINAL",1183,69,13,RED,true,false);
  }
  void draw(Canvas c){
    wings(c);
    // This unobstructed rectangle is occupied by the ACTUAL interactive map.
    plate(c,423,187,434,310,WHITE,0xff0d1118);
    fill(0xff111a23);c.drawRect(MAP_X,MAP_Y,MAP_X+MAP_W,MAP_Y+MAP_H,p);
    ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    gauge(c,208,347,"RPM",
      Float.isFinite(r.rpm)?number(r.rpm/1000f,1,false):"N/A",
      "x1000 rpm",r.rpm,0,8000);
    gauge(c,1072,347,"TEMP APĂ",number(r.coolantC,0,false),
      "°C",r.coolantC,40,130);
    trim(c,423,"STFT",r.stft);
    trim(c,642,"LTFT",r.ltft);
    top(c);
    slots.drawUserSlots(c);
  }
  boolean touch(float x,float y){
    if(y>=11&&y<=88){
      if(x>=212&&x<285){host.page=5;}
      else if(x>=292&&x<365){host.showInstalledApps();return true;}
      else if(x>=990&&x<1063){host.page=2;}
      else if(x>=1070&&x<1143){host.page=1;}
      else if(x>=375&&x<780){host.choosePlayer();return true;}
      else if(x>=780&&x<833){host.mediaAction(0);return true;}
      else if(x>=833&&x<898){host.mediaAction(1);return true;}
      else if(x>=898&&x<=980){host.mediaAction(2);return true;}
      else return false;
      if(host.view!=null)host.view.invalidate();
      host.placeMap();return true;
    }
    if(x<=377||x>=902){if(y>=190&&y<=512){host.showObdStatus();return true;}}
    return false;
  }
}
