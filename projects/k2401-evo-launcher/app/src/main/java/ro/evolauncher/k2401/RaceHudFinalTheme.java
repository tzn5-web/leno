package ro.evolauncher.k2401;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
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
import java.io.IOException;
import java.io.InputStream;
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
  static final int ID=25, ANGULAR_ID=26, HOLO_ID=27, EVO_RED_ID=28;
  // ID 25 preserves approved circular Carbon Red; ID 26 uses separate angular wings.
  static final int MAP_X=432,MAP_Y=196,MAP_W=416,MAP_H=291;
  private static final int WHITE=0xfff5f7fc, SILVER=0xffa9b5c3,
      RED=0xffea2845, LIT=0xfff85d64, DARK=0xff06090f;
  private final MainActivity host;
  private final UltraCockpitTheme slots;
  private final Bitmap evoRedScene;
  private final Bitmap holoPhoto;
  private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  RaceHudFinalTheme(MainActivity activity,UltraCockpitTheme userSlots){
    host=activity;slots=userSlots;
    Bitmap scene=null;
    try(InputStream source=host.getAssets().open("skins/approved/evo-red-scene-3840x2160.webp")){
      BitmapFactory.Options opts=new BitmapFactory.Options();
      opts.inPreferredConfig=Bitmap.Config.RGB_565;
      opts.inSampleSize=2;
      scene=BitmapFactory.decodeStream(source,null,opts);
    }catch(IOException|RuntimeException ignored){}
    evoRedScene=scene;
    Bitmap car=null;
    try(InputStream source=host.getAssets().open(
        "skins/cinematic/hologram-mitsubishi-3840x2160.webp")){
      BitmapFactory.Options opts=new BitmapFactory.Options();
      opts.inPreferredConfig=Bitmap.Config.ARGB_8888;
      opts.inSampleSize=2; // 4K source, economical full-screen photo layer
      car=BitmapFactory.decodeStream(source,null,opts);
    }catch(IOException|RuntimeException ignored){}
    holoPhoto=car;
  }
  void dispose(){
    if(evoRedScene!=null&&!evoRedScene.isRecycled())evoRedScene.recycle();
    if(holoPhoto!=null&&!holoPhoto.isRecycled())holoPhoto.recycle();
  }
  private void drawHologramPhoto(Canvas c,int alpha){
    if(holoPhoto==null||holoPhoto.isRecycled())return;
    fill(WHITE);
    p.setAlpha(alpha);
    p.setFilterBitmap(true);
    // Only a transparent cutout of the user-approved Mitsubishi appears.
    // No source screenshot rings, frozen values or static application tiles.
    c.drawBitmap(holoPhoto,null,new Rect(0,0,1280,720),p);
    p.setAlpha(255);
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
    // Transparent native glass; no opaque flat rectangular HUD plates.
    GlassHudFx.glassPanel(c,x,y,w,h,Math.min(13f,h*.18f));
  }
  private void wings(Canvas c){
    GlassHudFx.backdrop(c,26);
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
    GlassHudFx.dial(c,cx,cy,radius,value,min,max);
  }
  private void gauge(Canvas c,int cx,int cy,String title,String value,String units,
      float sensor,float min,float max){
    arc(c,cx,cy,155,sensor,min,max,RED);
    label(c,title,cx,cy-57,21,WHITE,true,true);
    label(c,value,cx,cy+22,52,WHITE,true,true);
    label(c,units,cx,cy+51,15,SILVER,false,true);
  }

  /**
   * The independent Alamy-angular-WINGS-inspired variant: entirely native
   * scalable metallic wings, never a stock image or a second round dial skin.
   * Render only four verified PIDs. The middle map remains a real Android View.
   */
  private void angularGauge(Canvas c,boolean right,String title,
                            String value,String unit,float raw,float min,float max){
    int outer=right?1258:22;
    c.save();
    c.translate(outer,0);
    if(right)c.scale(-1,1);
    Path shell=new Path();
    shell.moveTo(22,196);shell.lineTo(292,196);shell.lineTo(368,231);
    shell.lineTo(374,432);shell.lineTo(290,475);shell.lineTo(24,475);
    shell.lineTo(0,425);shell.lineTo(0,241);shell.close();
    fill(0x9b10151b);c.drawPath(shell,p);
    fill(WHITE);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3.3f);
    c.drawPath(shell,p);p.setStyle(Paint.Style.FILL);
    // Layered, asymmetric sculptural crescents taken from the structure of
    // the reference, not the licensed photographic source.
    segment(c,9,246,70,202,WHITE,11);
    segment(c,71,203,277,203,SILVER,4);
    segment(c,9,422,66,462,RED,8);
    segment(c,66,462,288,462,SILVER,3);
    segment(c,319,254,361,278,RED,4);
    segment(c,319,419,361,390,WHITE,3);
    for(int tick=0;tick<9;tick++){
      int y=257+tick*17;
      segment(c,325,y,343-(tick%3==0?0:7),y,0xffb8c6d6,1.8f);
    }
    c.restore();
    int center=right?1086:194;
    label(c,title,center,272,22,WHITE,true,true);
    label(c,value,center,344,55,WHITE,true,true);
    label(c,unit,center,375,17,SILVER,false,true);
    int x=right?917:57;
    fill(0x6b525e6b);c.drawRoundRect(x,406,x+309,426,7,7,p);
    if(Float.isFinite(raw)){
      float normalized=Math.max(0f,Math.min(1f,(raw-min)/(max-min)));
      fill(RED);c.drawRoundRect(x,406,x+309*normalized,426,7,7,p);
    }
    label(c,"0",x,446,13,SILVER,false,false);
    label(c,right?"130°C":"8000",x+267,446,13,SILVER,false,false);
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
    return s.length()<=max?s:s.substring(0,max-1)+"…";
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
    label(c,host.skins!=null&&host.skins.selection()==EVO_RED_ID?"EVO RED":host.skins.selection()==HOLO_ID?"HOLO":host.skins.selection()==ANGULAR_ID?"WINGS":"FINAL",1183,69,13,RED,true,false);
  }
  private void holoBackground(Canvas c){
    GlassHudFx.backdrop(c,27); // 3D projection is decorative, not a fake map.
  }
  private void evoRing(Canvas c,int cx,int cy,int radius,String title,
       String value,String unit,float raw,float min,float max,boolean major){
    GlassHudFx.dial(c,cx,cy,radius,raw,min,max);
    if(major){
      label(c,value,cx,cy+14,57,WHITE,true,true);
      label(c,title,cx,cy+55,22,WHITE,true,true);
      label(c,unit,cx,cy+79,16,SILVER,false,true);
    }else{
      label(c,value,cx,cy+9,27,WHITE,true,true);
      label(c,unit,cx,cy+30,13,SILVER,false,true);
      label(c,title,cx,cy+radius+21,17,WHITE,true,true);
    }
  }
  private void approvedTop(Canvas c){
    plate(c,8,5,1264,89,0xff7f8793,0xee07090d);
    GlassHudFx.glassPanel(c,12,10,97,76,11);
    GlassHudFx.glassPanel(c,114,10,92,76,11);
    GlassHudFx.glassPanel(c,811,10,98,76,11);
    GlassHudFx.glassPanel(c,1158,10,106,76,11);
    // Only real controls and one real connection-status group; no fake tiles.
    NavVectorIcons.draw(c,4,62,39,RED);
    label(c,"APPS",62,74,14,WHITE,true,true);
    NavVectorIcons.draw(c,2,160,39,WHITE);
    label(c,"NAVI",160,74,14,WHITE,true,true);
    // Native music action stays clear of MediaSession and connection status.
    NavVectorIcons.draw(c,1,850,39,WHITE);
    label(c,"MUZICĂ",850,74,12,WHITE,true,true);
    boolean bt=false,wifi=false;
    try{
      bt=Settings.Global.getInt(host.getContentResolver(),"bluetooth_on",0)!=0;
      wifi=Settings.Global.getInt(host.getContentResolver(),"wifi_on",0)!=0;
    }catch(RuntimeException ignored){}
    label(c,"BT",975,51,17,bt?WHITE:0xff717882,true,false);
    label(c,"Wi-Fi",1030,51,17,wifi?WHITE:0xff717882,true,false);
    NavVectorIcons.draw(c,5,1218,39,RED);
    label(c,"SETUP",1218,74,14,WHITE,true,true);
    MediaController media=host.media;
    String song="Nicio redare",artist="";
    Bitmap album=null;
    if(media!=null&&media.getMetadata()!=null){
      MediaMetadata meta=media.getMetadata();
      CharSequence title=meta.getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence name=meta.getText(MediaMetadata.METADATA_KEY_ARTIST);
      if(title!=null&&!title.toString().trim().isEmpty())song=title.toString();
      if(name!=null)artist=name.toString();
      album=meta.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
      if(album==null)album=meta.getBitmap(MediaMetadata.METADATA_KEY_ART);
    }
    if(album!=null&&!album.isRecycled()){
      fill(WHITE);c.drawBitmap(album,null,new Rect(240,17,298,78),p);
    }else{
      plate(c,240,17,58,61,RED,0xff11151c);
      label(c,"♪",269,58,34,WHITE,true,true);
    }
    label(c,shorten(song,23),312,43,19,WHITE,true,false);
    if(!artist.isEmpty())label(c,shorten(artist,27),312,69,14,SILVER,false,false);
    boolean playing=media!=null&&media.getPlaybackState()!=null&&
      media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,583,49,0,WHITE);
    MediaVectorIcons.draw(c,653,49,playing?3:1,RED);
    MediaVectorIcons.draw(c,723,49,2,WHITE);
    segment(c,315,80,526,80,RED,2);
    Date now=new Date();
    label(c,new SimpleDateFormat("EEE, d MMM yyyy",new Locale("ro","RO")).format(now),
      640,122,18,SILVER,false,true);
    label(c,new SimpleDateFormat("HH:mm",Locale.getDefault()).format(now),
      640,166,45,WHITE,true,true);
    ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    label(c,"EXT "+(Float.isFinite(r.ambientC)?number(r.ambientC,0,false)+"°C":"N/A"),
      640,192,17,WHITE,false,true);
  }
  private void approvedRed(Canvas c){
    if(evoRedScene!=null&&!evoRedScene.isRecycled()){
      fill(WHITE);c.drawBitmap(evoRedScene,null,new Rect(0,0,1280,720),p);
    }else{
      c.drawColor(0xff05070c);
      fill(0xff11151c);c.drawRect(445,212,835,420,p);
    }
    // Original 4K carbon-metal scene remains under a real layered glass
    // projection; no flat car outline is promoted as a live ECU value.
    GlassHudFx.glassPanel(c,438,214,404,228,16);
    GlassHudFx.projection(c);
    drawHologramPhoto(c,206);
    // The scenic layer has no baked HUD, speed, media or ECU readings.
    ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    evoRing(c,228,344,196,"RPM",number(r.rpm,0,false),"rpm",r.rpm,0,8000,true);
    evoRing(c,1052,344,196,"TEMP APĂ",number(r.coolantC,0,false),
      "°C",r.coolantC,40,130,true);
    evoRing(c,537,476,77,"STFT",number(r.stft,1,true),"%",r.stft,-25,25,false);
    evoRing(c,743,476,77,"LTFT",number(r.ltft,1,true),"%",r.ltft,-25,25,false);
    slots.drawUserSlots(c);
    approvedTop(c);
  }
  void draw(Canvas c){
    if(host.skins!=null&&host.skins.selection()==EVO_RED_ID){approvedRed(c);return;}
    boolean holo=host.skins!=null&&host.skins.selection()==HOLO_ID;
    if(holo){holoBackground(c);drawHologramPhoto(c,222);}
    else wings(c);
    // Only skins 25/26 reserve this surface for the ACTUAL interactive map.
    // Skin 27 has a native 3D holographic projection, not a blank fake map.
    if(!holo){
      plate(c,423,187,434,310,WHITE,0xff0d1118);
      fill(0xff111a23);c.drawRect(MAP_X,MAP_Y,MAP_X+MAP_W,MAP_Y+MAP_H,p);
    }
    ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    if(host.skins!=null&&host.skins.selection()==ANGULAR_ID){
      angularGauge(c,false,"RPM",
        Float.isFinite(r.rpm)?number(r.rpm/1000f,1,false):"N/A",
        "x1000 rpm",r.rpm,0,8000);
      angularGauge(c,true,"TEMP APĂ",number(r.coolantC,0,false),
        "°C",r.coolantC,40,130);
    }else{
      gauge(c,208,347,"RPM",
        Float.isFinite(r.rpm)?number(r.rpm/1000f,1,false):"N/A",
        "x1000 rpm",r.rpm,0,8000);
      gauge(c,1072,347,"TEMP APĂ",number(r.coolantC,0,false),
        "°C",r.coolantC,40,130);
    }
    trim(c,423,"STFT",r.stft);
    trim(c,642,"LTFT",r.ltft);
    top(c);
    slots.drawUserSlots(c);
  }
  boolean touch(float x,float y){
    if(host.skins!=null&&host.skins.selection()==EVO_RED_ID){
      if(y<=96){
        if(x>=10&&x<112){host.showInstalledApps();return true;}
        if(x>=116&&x<210){host.page=2;host.placeMap();if(host.view!=null)host.view.invalidate();return true;}
        if(x>=815&&x<923){host.page=1;host.placeMap();if(host.view!=null)host.view.invalidate();return true;}
        if(x>=1156&&x<=1270){host.page=5;host.placeMap();if(host.view!=null)host.view.invalidate();return true;}
        if(x>=230&&x<550){host.choosePlayer();return true;}
        if(x>=550&&x<618){host.mediaAction(0);return true;}
        if(x>=618&&x<689){host.mediaAction(1);return true;}
        if(x>=689&&x<760){host.mediaAction(2);return true;}
      }
      if(y>=145&&y<=545&&(x<436||x>844)){
        host.showObdStatus();return true;
      }
      return false;
    }
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
