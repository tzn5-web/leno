package ro.evolauncher.k2401;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.widget.Toast;
import java.io.File;
import java.io.FileOutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import android.content.SharedPreferences;
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
import android.media.MediaMetadata;
import android.media.session.MediaController;
import android.media.session.PlaybackState;
import android.view.Gravity;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.IOException;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Twenty-one user-selectable home skins in the ORIGINAL image order, except
 * EVO DIGITAL DASH is deliberately first. Previews use bundled artwork from
 * the actual concept sheet, if present. Real time, OBD readings, media and
 * interactive controls are freshly drawn over the visual design: never read
 * ECU values from the screenshot, never paint fictitious telemetry.
 *
 * Independent of DirectElm327/MediaAccessService, preserving working drivers.
 */
final class SkinEngine {
  static final String PREFS="evo_launcher_prefs",KEY="selected_skin_v2";
  static final int PICK_SKIN_PACK=2419;
  static final String[] NAMES={
    "EVO DIGITAL DASH",
    "EVO CLASSIC","EVO FUTURE","EVO GAUGE PRO",
    "EVO MULTI INFO","EVO APPS CENTER",
    "LANCER EVOLUTION NIGHT","EVO GT COCKPIT",
    "EVO RED FRONT","LANCER MOUNTAIN","EVO SPEED","EVO SUNSET",
    "LANCER HERO","DIGITAL COCKPIT","TECH GRID",
    "GAUGES FOCUS","LANCER SHOWROOM","MINIMAL SPORT",
    "CAR STATUS","APP LAUNCHER","PERFORMANCE",
    "EVO ULTRA NEON UHD",
    "A1 • HOLOGRAPHIC VERTICAL 4K",
    "02 • HOLOGRAPHIC BLUE 4K",
    "A3 • GLASS SHOWROOM 4K",
    "RACE HUD • FINAL ALB-ROȘU",
    "RACE HUD • ANGULAR WINGS ALB-ROȘU"
  };
  // Variants correspond to concept-sheet crops in /assets/skins/atlas.webp.
  static final int COUNT=NAMES.length;
  // Each of the 21 originals has a distinct native interaction/gauge profile,
  // rather than just recycling one of six dashboard canvases.
  private static final int[] STYLES={
    0,1,2,3,4,5,6, 7,8,9,10,11,12,13, 14,15,16,17,18,19,20,21
  };
  private static final int[] COLORS={
    0xfff02e4a,0xffff3450,0xff1ec7ff,0xfff02e4a,0xff24c9ff,0xffef3551,
    0xffff314e,0xfffe3951,0xffff3556,0xffed4a50,0xff21c4eb,0xffff7650,
    0xffff3650,0xffed3154,0xff29d6ee,0xffed2e54,0xfff55b43,0xff27cdf0,
    0xffe52b51,0xff33b6ea,0xffee334d,0xff29d5ff
  };
  private final MainActivity host;
  private final ThemeNativePanels nativePanels;
  private final SharedPreferences prefs;
  private final Paint p=new Paint(3);
  private final CleanSkinArt cleanArt=new CleanSkinArt();
  private final UltraCockpitTheme ultra;
  private final CinematicTrioTheme trio;
  private final RaceHudFinalTheme raceHud;
  private Bitmap atlas;
  private Bitmap fullArt;
  private int fullArtId=-1;
  private boolean fullArtIsClean=false;
  private AlertDialog galleryDialog;
  private int selected;
  private final Rect mediaRect=new Rect(860,74,1265,412);
  private final Rect statsRect=new Rect(860,462,1266,689);
  private final Rect appRect=new Rect(13,630,197,714);
  private final Rect skinRect=new Rect(201,630,385,714);
  private final Rect mapsRect=new Rect(389,630,573,714);

  SkinEngine(MainActivity activity){
    host=activity;
    nativePanels=new ThemeNativePanels(activity);
    prefs=host.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
    ultra=new UltraCockpitTheme(activity);
    trio=new CinematicTrioTheme(activity,ultra);
    raceHud=new RaceHudFinalTheme(activity,ultra);
    selected=clamp(prefs.getInt(KEY,0));
    loadAtlas();
  }
  static int clamp(int id){return Math.max(0,Math.min(COUNT-1,id));}
  private File packDir(){
    if(!prefs.getBoolean("use_custom_skin_pack",false))return null;
    String name=prefs.getString("skin_pack_dir","");
    return name.isEmpty()?null:new File(host.getFilesDir(),name);
  }
  private void loadAtlas(){
    if(atlas!=null&&!atlas.isRecycled())atlas.recycle();
    atlas=null;
    BitmapFactory.Options options=new BitmapFactory.Options();
    options.inPreferredConfig=Bitmap.Config.ARGB_8888;
    // User-enabled and validated 21-skin ZIP takes priority over bundled art.
    // The previous order always loaded the APK atlas and silently ignored ZIPs.
    File root=packDir();
    File local=root==null?null:new File(root,"atlas.webp");
    if(local!=null&&local.isFile())atlas=BitmapFactory.decodeFile(local.getPath(),options);
    if(atlas==null){
      try(InputStream stream=host.getAssets().open("skins/atlas.webp")){
        atlas=BitmapFactory.decodeStream(stream,null,options);
      }catch(IOException|RuntimeException ignored){}
    }
  }
  private Bitmap fullArt(int id){
    if(fullArt!=null&&!fullArt.isRecycled()&&fullArtId==id)return fullArt;
    if(fullArt!=null&&!fullArt.isRecycled())fullArt.recycle();
    fullArt=null;fullArtId=id;fullArtIsClean=false;
    // Explicitly imported skins must win over APK assets. Never ignore a
    // successfully validated, user-selected ZIP pack.
    File importedRoot=packDir();
    File importedFile=importedRoot==null?null:new File(importedRoot,
      String.format(Locale.US,"skin_%02d.webp",id));
    if(importedFile!=null&&importedFile.isFile()){
      BitmapFactory.Options opts=new BitmapFactory.Options();
      opts.inPreferredConfig=Bitmap.Config.ARGB_8888;
      fullArt=BitmapFactory.decodeFile(importedFile.getAbsolutePath(),opts);
    }
    // Bundled clean backgrounds take priority only when no import is active.
    // UI-free audited car-scene art has priority; no baked fake ECU values.
    if(fullArt==null)try(InputStream stream=host.getAssets().open(
      String.format(Locale.US,"skins/clean/skin_%02d.webp",id))){
      BitmapFactory.Options cleanOpts=new BitmapFactory.Options();
      cleanOpts.inPreferredConfig=Bitmap.Config.ARGB_8888;
      // Build with 2560x1440 detail reconstruction, but K2401 displays a
      // 1280x720 framebuffer. Decode at exact display pixels to cut native
      // bitmap RAM from 14.1 MiB to 3.5 MiB per theme without visible loss.
      // This also prevents OEM GPU memory spikes during the 21-skin picker.
      cleanOpts.inSampleSize=2;
      fullArt=BitmapFactory.decodeStream(stream,null,cleanOpts);
      fullArtIsClean=fullArt!=null;
    }catch(IOException|RuntimeException ignored){}
    // Preserve the approved legacy photo when an old APK lacks clean assets.
    // The 2560x1440 artwork is generated from the exact 21 approved images.
    // The original 1280x720 files are the safe fallback on legacy builds.
    if(fullArt==null)try(InputStream stream=host.getAssets().open(
      String.format(Locale.US,"skins/uhd/skin_%02d.webp",id))){
      BitmapFactory.Options opts=new BitmapFactory.Options();
      opts.inPreferredConfig=Bitmap.Config.ARGB_8888;
      opts.inSampleSize=2;
      fullArt=BitmapFactory.decodeStream(stream,null,opts);
    }catch(IOException|RuntimeException ignored){}
    if(fullArt==null){
      try(InputStream stream=host.getAssets().open(
        String.format(Locale.US,"skins/skin_%02d.webp",id))){
        BitmapFactory.Options opts=new BitmapFactory.Options();
        opts.inPreferredConfig=Bitmap.Config.ARGB_8888;
        fullArt=BitmapFactory.decodeStream(stream,null,opts);
      }catch(IOException|RuntimeException ignored){}
    }
    if(fullArt==null){
      File root=packDir();
      File image=root==null?null:new File(root,String.format(Locale.US,"skin_%02d.webp",id));
      if(image!=null&&image.isFile()){
        BitmapFactory.Options opts=new BitmapFactory.Options();
        opts.inPreferredConfig=Bitmap.Config.ARGB_8888;
        fullArt=BitmapFactory.decodeFile(image.getAbsolutePath(),opts);
      }
    }
    return fullArt;
  }
  boolean isCleanArt(){return fullArtIsClean;}
  int selection(){return selected;}
  void select(int id){
    selected=clamp(id);
    if(fullArt!=null&&!fullArt.isRecycled())fullArt.recycle();fullArt=null;
    fullArtId=-1;fullArtIsClean=false;
    prefs.edit().putInt(KEY,selected).commit();
    if(host.view!=null)host.view.invalidate();
    host.placeMap();
  }
  void release(){
    ultra.release();
    trio.dispose();
    if(atlas!=null&&!atlas.isRecycled()){atlas.recycle();atlas=null;}
    if(fullArt!=null&&!fullArt.isRecycled()){fullArt.recycle();fullArt=null;}
  }
  private void colour(int c){p.setColor(c);p.setStyle(Paint.Style.FILL);p.setStrokeWidth(1);p.setShader(null);}
  private void panel(Canvas c,float x,float y,float w,float h,int fill,float radius){
    colour(fill);c.drawRoundRect(x,y,x+w,y+h,radius,radius,p);
  }
  private void stroke(Canvas c,float x,float y,float w,float h,int color,float radius){
    colour(color);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.8f);
    c.drawRoundRect(x,y,x+w,y+h,radius,radius,p);p.setStyle(Paint.Style.FILL);
  }
  private void line(Canvas c,float a,float b,float d,float e,int co,float width){
    colour(co);p.setStrokeWidth(width);p.setStrokeCap(Paint.Cap.ROUND);
    c.drawLine(a,b,d,e,p);
  }
  private void text(Canvas c,String s,float x,float y,float size,int co,boolean heavy){
    colour(co);p.setTypeface(Typeface.create(heavy?"sans-serif-condensed":"sans-serif",
      heavy?Typeface.BOLD:Typeface.NORMAL));p.setTextSize(size);
    c.drawText(s,x,y,p);
  }
  private void centered(Canvas c,String s,float x,float y,float size,int co,boolean heavy){
    p.setTypeface(Typeface.create("sans-serif-condensed",heavy?Typeface.BOLD:Typeface.NORMAL));
    p.setTextSize(size);
    text(c,s,x-p.measureText(s)/2f,y,size,co,heavy);
  }
  private String time(){
    boolean is24=host.launcherSettings==null||host.launcherSettings.use24HourClock();
    return new SimpleDateFormat(is24?"HH:mm":"hh:mm",Locale.getDefault()).format(new Date());
  }
  private String date(){
    return new SimpleDateFormat("EEEE, d MMMM yyyy",new Locale("ro","RO")).format(new Date());
  }
  private String val(float v,int decimals){
    if(!Float.isFinite(v))return "N/A";
    return String.format(Locale.US,decimals==0?"%.0f":"%+.1f",v);
  }
  private String shorten(String s,int chars){
    if(s==null||s.isEmpty())return "";
    return s.length()>chars?s.substring(0,chars-1)+"…":s;
  }
  private void drawArt(Canvas c,int id){
    // The original 21 mockups are only PHOTO sources. Drawing the full mockup
    // on Home duplicated low-resolution icons, sample RPM, fake weather, track
    // names and status indicators. All interactive UI is drawn natively.
    Bitmap scene=fullArt(id);
    cleanArt.draw(c,scene,id,fullArtIsClean);
  }
  private void renderTime(Canvas c,int accent,int style){
    // Original concept artwork contains a static clock (22:36 etc.). On the
    // actual screen its sample digits MUST be covered by the running time.
    panel(c,20,78,602,132,0xee09111d,15);
    stroke(c,20,78,602,132,accent,15);
    text(c,time(),37,153,66,Color.WHITE,true);
    text(c,shorten(date(),34),246,155,23,0xffd2ddeb,true);
    text(c,shorten(NAMES[selected],34),246,189,17,accent,true);
    text(c,"K2401 • LIVE",42,193,15,accent,true);
  }
  private void renderMusic(Canvas c,int accent,int style){
    // Dynamic media covers *baked* fake track/controls from original previews.
    Rect r=mediaRect;int x=r.left,y=r.top,w=r.width(),h=r.height();
    panel(c,x,y,w,h,0xf20d1625,18);
    stroke(c,x,y,w,h,accent,18);
    panel(c,x+18,y+17,41,41,accent,10);
    text(c,"▶",x+29,y+46,22,Color.WHITE,true);
    text(c,shorten(host.mediaName,24),x+72,y+46,24,Color.WHITE,true);
    String song="",artist="";
    MediaController media=host.media;
    if(media!=null&&media.getMetadata()!=null){
      CharSequence t=media.getMetadata().getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence a=media.getMetadata().getText(MediaMetadata.METADATA_KEY_ARTIST);
      song=t==null?"":t.toString();artist=a==null?"":a.toString();
    }
    if(song.isEmpty()){
      song=host.mediaPackage.isEmpty()?"Alege playerul":"Fără redare activă";
      artist=host.mediaPackage.isEmpty()?"Apasă aici pentru lista de playere":"Control MediaSession / Play";
    }
    panel(c,x+23,y+77,130,128,0xff412030,12);
    text(c,"MEDIA",x+44,y+154,26,Color.WHITE,true);
    text(c,shorten(song,27),x+174,y+124,26,Color.WHITE,true);
    text(c,shorten(artist,35),x+174,y+163,17,0xffa9b9ce,false);
    line(c,x+178,y+178,x+w-20,y+178,0xff405266,4);
    boolean playing=media!=null&&media.getPlaybackState()!=null&&
      media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,x+238,y+h-39,0,0xffeff5ff);
    panel(c,x+350,y+h-72,58,57,accent,29);
    MediaVectorIcons.draw(c,x+379,y+h-43,playing?3:1,Color.WHITE);
    MediaVectorIcons.draw(c,x+509,y+h-39,2,0xffeff5ff);
  }
  private static float clipped(float value,float lo,float hi){
    return Math.max(0f,Math.min(1f,(value-lo)/Math.max(1f,hi-lo)));
  }
  // All 21 skins use their own palette (COLORS[id]), one of seven native
  // gauge geometries, and one of three placements. Only ECU values influence
  // arcs, needles and bars; absent PIDs have neither needles nor filled arcs.
  private void gauge(Canvas c,float cx,float cy,int radius,String name,String value,
                     String unit,float reading,float from,float to,int accent,int style){
    int geometry=style%7,edition=style/7;
    boolean valid=Float.isFinite(reading);
    float progress=valid?clipped(reading,from,to):0f;
    final int neon=edition==1?0xff22d3ef:edition==2?0xffed577b:accent;
    int applied=geometry==2?neon:accent;
    if(geometry==4||geometry==5){
      float left=cx-radius,top=cy-radius*.73f;
      panel(c,left,top,2f*radius,1.68f*radius,0xf0081523,9);
      stroke(c,left,top,2f*radius,1.68f*radius,applied,9);
      text(c,name,left+13,top+26,16,0xffdae5ee,true);
      text(c,value,left+13,cy+18,geometry==5?33:30,Color.WHITE,true);
      text(c,unit,left+16,cy+40,12,0xffa9c0d4,false);
      float width=2f*radius-26f;
      panel(c,left+13,top+1.43f*radius,width,7,0xff273a4e,3);
      if(valid)panel(c,left+13,top+1.43f*radius,width*progress,7,applied,3);
      if(geometry==5&&valid){
        for(int t=0;t<10;t++){
          float x=left+15+t*width/10f;
          if(t<=progress*10f)line(c,x,top+1.12f*radius,x,top+1.31f*radius,applied,3);
        }
      }
      return;
    }
    // EVO Digital Dash only: decorative outer neon segments (not a fake
    // sensor reading). The inner arc/needle below remains ECU-driven and
    // is empty when a PID is unavailable. This matches the approved red/cyan
    // cockpit without changing any ECU value, unit or touch function.
    if(style==1||style==2){
      float outer=radius+17f;
      colour(style==1?0xff205b97:0xff1f9bd0);
      p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(7f);
      c.drawArc(cx-outer,cy-outer,cx+outer,cy+outer,130,292,false,p);
      colour(style==1?0xfff63157:0xff25d6ff);
      p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(9f);
      c.drawArc(cx-outer,cy-outer,cx+outer,cy+outer,
        style==1?135:190,style==1?105:156,false,p);
      colour(style==1?0xff25bcfb:0xfff03a56);
      p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(8f);
      c.drawArc(cx-outer,cy-outer,cx+outer,cy+outer,
        style==1?250:355,style==1?150:50,false,p);
      p.setStyle(Paint.Style.FILL);
    }
    colour(0xed06101c);
    c.drawCircle(cx,cy,radius+5,p);
    if(geometry==3)stroke(c,cx-radius-3,cy-radius-3,radius*2+6,radius*2+6,applied,9);
    colour(0xff37495f);p.setStrokeWidth(geometry==2?12f:geometry==6?5f:8f);
    p.setStyle(Paint.Style.STROKE);
    int startAngle=(geometry==6)?155:135;
    int span=(geometry==6)?230:270;
    c.drawArc(cx-radius,cy-radius,cx+radius,cy+radius,startAngle,span,false,p);
    if(valid){
      colour(applied);p.setStyle(Paint.Style.STROKE);
      p.setStrokeCap(Paint.Cap.ROUND);
      p.setStrokeWidth(geometry==2?12f:geometry==6?5f:8f);
      c.drawArc(cx-radius,cy-radius,cx+radius,cy+radius,startAngle,span*progress,false,p);
      if(geometry==2){
        p.setStrokeWidth(2.5f);
        c.drawArc(cx-radius+11,cy-radius+11,cx+radius-11,cy+radius-11,
          startAngle,span*progress,false,p);
      }
    }
    p.setStyle(Paint.Style.FILL);
    if(geometry==1||geometry==6){
      for(int i=0;i<=12;i++){
        float a=(float)Math.toRadians(startAngle+span*i/12f);
        float x1=cx+(radius-14)*(float)Math.cos(a);
        float y1=cy+(radius-14)*(float)Math.sin(a);
        float x2=cx+(radius-5)*(float)Math.cos(a);
        float y2=cy+(radius-5)*(float)Math.sin(a);
        line(c,x1,y1,x2,y2,(valid&&i/12f<=progress)?applied:0xff51647c,2.5f);
      }
      if(geometry==1&&valid){
        float a=(float)Math.toRadians(startAngle+span*progress);
        line(c,cx,cy,cx+(radius-23)*(float)Math.cos(a),
          cy+(radius-23)*(float)Math.sin(a),applied,2.7f);
      }
    }
    centered(c,value,cx,cy+13,radius>65?39:28,Color.WHITE,true);
    centered(c,name,cx,cy+radius+25,17,0xffe6edf4,true);
    centered(c,unit,cx,cy+radius+43,13,applied,false);
    if(!valid)centered(c,"ECU N/A",cx,cy+radius*.50f,12,0xff9baac2,false);
  }
  private void stats(Canvas c,int accent,int style){
    ObdReader.Reading rd=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    float[] vs={rd.rpm,rd.stft,rd.ltft,rd.coolantC};
    String[] names={"RPM","STFT B1","LTFT B1","TEMP APĂ"};
    String[] units={"rpm","%","%","°C"};
    float[] lower={0,-25,-25,40},upper={8000,25,25,120};
    Rect area=statsRect;
    int x=area.left,y=area.top,w=area.width(),h=area.height();
    panel(c,x,y,w,h,0xe80a101c,16);
    stroke(c,x,y,w,h,accent,16);
    text(c,"EVO • OBD-II LIVE",x+20,y+30,21,Color.WHITE,true);
    String status=host.obd==null?"N/A":host.obd.status();
    text(c,shorten(status,35),x+210,y+29,15,rd.live?0xff64eac4:0xffa0aabc,false);
    line(c,x+14,y+43,x+w-14,y+43,0xff415164,1);
    if(style==0){
      // EVO Digital Dash has the two FAST rings on the left. On the right,
      // keep the remaining two actual (slow) ECU gauges, not two duplicate
      // fast RPM/STFT readings.
      gauge(c,x+174,y+149,84,names[2],val(vs[2],1),units[2],vs[2],
        lower[2],upper[2],0xffeda551,2);
      gauge(c,x+445,y+149,84,names[3],val(vs[3],0),units[3],vs[3],
        lower[3],upper[3],0xff54d6ba,2);
    }else if(style==2||style==7||style==13||style==15||style==20){
      int rad=75;
      gauge(c,x+115,y+149,rad,names[0],val(vs[0],0),units[0],vs[0],lower[0],upper[0],accent,style);
      gauge(c,x+315,y+149,rad,names[1],val(vs[1],1),units[1],vs[1],lower[1],upper[1],0xff18c6ff,style);
      gauge(c,x+486,y+122,47,names[2],val(vs[2],1),units[2],vs[2],lower[2],upper[2],0xffed9545,style);
      gauge(c,x+486,y+240,47,names[3],val(vs[3],0),units[3],vs[3],lower[3],upper[3],0xffed5960,style);
    }else{
      int rad=(style%7==4||style%7==5)?64:(style/7==2?54:57);
      for(int i=0;i<4;i++){
        float cx=x+84+i*(w-168)/3f,cy=y+((style%7==4||style%7==5)?140:137);
        int color=i==0?accent:i==1?0xff20c8fa:i==2?0xffec9b35:0xffef4552;
        gauge(c,cx,cy,rad,names[i],val(vs[i],i==0||i==3?0:1),units[i],
          vs[i],lower[i],upper[i],color,style);
      }
    }
  }
  private void strip(Canvas c,int accent){
    panel(c,6,621,393,97,0xf107101e,16);
    stroke(c,6,621,393,97,accent,16);
    panel(c,13,630,119,79,0xff202839,12);
    panel(c,142,630,125,79,0xff202839,12);
    panel(c,277,630,114,79,0xff202839,12);
    text(c,"▦",48,676,30,accent,true);
    text(c,"APLICAȚII",23,701,14,Color.WHITE,true);
    text(c,"◈",186,675,30,accent,true);
    text(c,"SKINURI",166,700,14,Color.WHITE,true);
    text(c,"➤",316,675,29,accent,true);
    text(c,"HARTĂ",310,700,14,Color.WHITE,true);
  }
  private void sideRail(Canvas c,int accent){
    panel(c,3,228,82,385,0xd20a111b,14);
    String[] icons={"⌂","♫","➤","◉","▦","⚙"};
    String[] names={"HOME","MEDIA","HARTĂ","OBD","APPS","SET"};
    for(int i=0;i<6;i++){
      int top=233+i*61;
      panel(c,9,top,69,56,0xff172032,8);
      centered(c,icons[i],43,top+31,25,i==4?accent:0xffe9f1f9,true);
      centered(c,names[i],43,top+48,10,0xffc3ccdc,true);
    }
  }
  private void drawDigitalDashFastGauges(Canvas c,int accent){
    // EVO DIGITAL DASH replaces the two prominent photographed sample gauges
    // with the actual instantaneous ECU RPM and STFT B1. No speed or simulated
    // sensor values are shown, and these controls are interactive via touch.
    ObdReader.Reading data=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    panel(c,101,220,527,353,0xee07111e,24);
    stroke(c,101,220,527,353,accent,24);
    text(c,"RPM + STFT • ECU LIVE",123,255,19,0xffd5e5f7,true);
    gauge(c,240,384,91,"RPM",val(data.rpm,0),"rpm",data.rpm,0,8000,accent,2);
    gauge(c,481,384,91,"STFT B1",val(data.stft,1),"%",data.stft,-25,25,
      0xff2dd4ff,2);
    text(c,"ACTUALIZARE PRIORITARĂ",210,541,17,0xff8dd6ea,true);
  }

  /**
   * EVO DIGITAL DASH. Unlike a generic two-column HUD, place real controls
   * on the same geometry as the approved original:
   *  left RPM and coolant tachometers; centre status; upper right real media;
   *  lower right STFT and LTFT. The illustrated car/road stays visible.
   * No generated screenshot number is trusted as a live ECU measurement.
   */
  private void drawEvoDigitalDashNative(Canvas c){
    drawArt(c,0);
    // The approved Digital Dash has no duplicated 01/21 gallery header.
    // Real clock is already drawn below; title remains in the bottom strip.
    final int crimson=0xfffa304d,azure=0xff30cfff,ice=0xffedf6ff;
    // The shared native status bar above already renders the EVO DIGITAL DASH
    // title once. Do not add another opaque title card over the first skin.
    panel(c,420,86,255,87,0xff081421,17);
    text(c,time(),441,130,43,ice,true);
    text(c,shorten(date(),27),441,159,16,0xffcddde9,false);

    // The mockup has "0 km/h" without a vehicle-speed PID. Do not make it
    // appear live: replace just its centre with a real connection indicator.
    panel(c,446,246,171,155,0xff081420,17);
    text(c,"ECU / ELM327",460,281,17,0xffa7bcd1,true);
    ObdReader.Reading data=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    text(c,data.live?"CONECTAT":"N/A",460,333,27,data.live?0xff5af5ba:ice,true);
    text(c,data.live?"DATE LIVE":"FĂRĂ DATE",460,362,15,
      data.live?azure:0xff9db0c4,true);

    // Main round gauges. Semi-opaque black under the *dynamic* arcs hides
    // baked-in readings and keeps the original tachometer-like placement.
    colour(0xff07111e);c.drawCircle(298,300,144,p);c.drawCircle(735,305,127,p);
    gauge(c,298,300,136,"RPM",val(data.rpm,0),"rpm",data.rpm,0,8000,crimson,1);
    gauge(c,735,305,117,"TEMP APĂ",val(data.coolantC,0),"°C",
      data.coolantC,40,120,azure,2);

    // Media panel exactly within the right-hand rectangular music location.
    panel(c,860,74,405,338,0xff08121e,15);
    stroke(c,860,74,405,338,crimson,15);
    text(c,shorten(host.mediaName,22),882,108,22,ice,true);
    MediaController controller=host.media;
    Bitmap cover=null;
    if(controller!=null&&controller.getMetadata()!=null){
      cover=controller.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
      if(cover==null)cover=controller.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ART);
    }
    panel(c,882,128,118,146,0xff3f1526,10);
    if(cover!=null){
      colour(Color.WHITE);p.setFilterBitmap(true);
      c.drawBitmap(cover,null,new Rect(884,130,998,272),p);
    }else{
      // Do not draw a YouTube logo if Morphe, Spotify or another player is selected.
      centered(c,"MEDIA",941,211,23,ice,true);
    }
    String song="",performer="";
    if(controller!=null&&controller.getMetadata()!=null){
      CharSequence t=controller.getMetadata().getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence a=controller.getMetadata().getText(MediaMetadata.METADATA_KEY_ARTIST);
      song=t==null?"":t.toString();performer=a==null?"":a.toString();
    }
    if(song.isEmpty())song="Fără redare activă";
    if(performer.isEmpty())performer="Alege playerul / MediaSession";
    text(c,shorten(song,19),1012,183,22,ice,true);
    text(c,shorten(performer,25),1012,218,15,0xff9fb2c6,false);
    line(c,1012,260,1242,260,0xff41556c,4);
    if(controller!=null&&controller.getMetadata()!=null&&controller.getPlaybackState()!=null){
      long duration=controller.getMetadata().getLong(MediaMetadata.METADATA_KEY_DURATION);
      long pos=controller.getPlaybackState().getPosition();
      if(duration>0&&pos>=0)line(c,1012,260,1012+230f*Math.min(1f,(float)pos/duration),260,
        crimson,4);
    }
    panel(c,1089,319,70,73,crimson,33);
    boolean playing=controller!=null&&controller.getPlaybackState()!=null&&
      controller.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,1040,363,0,ice);
    MediaVectorIcons.draw(c,1124,363,playing?3:1,ice);
    MediaVectorIcons.draw(c,1211,363,2,ice);
    text(c,controller==null?"MEDIA OFFLINE":"MEDIA LIVE",882,398,13,
      controller==null?0xffacbacb:0xff5af5ba,true);

    // The two rectangular live fuel-trim instruments correspond to the two
    // cards in the original lower right, not a duplicate four-dial panel.
    compactDigitalFuelTrim(c,860,426,194,205,"STFT B1",data.stft,azure);
    compactDigitalFuelTrim(c,1066,426,199,205,"LTFT B1",data.ltft,crimson);
    text(c,"K2401 • "+NAMES[0],590,698,16,0xffb5c8d9,true);

    // Small functional bottom dock instead of a 620x310 HUD obscuring the car.
    panel(c,5,630,573,88,0xff0a1320,14);
    stroke(c,5,630,573,88,0xffa72a43,14);
    String[] shortcuts={"APLICAȚII","SKINURI","HARTĂ"};
    int[] bx={13,201,389},bw={184,184,184};
    for(int i=0;i<3;i++){
      panel(c,bx[i],635,bw[i],76,0xff1b2a3b,9);
      // Crisp vector artwork: exact same original on-screen touch rectangles.
      cleanArt.shortcutIcon(c,i,bx[i]+bw[i]/2f,660,crimson);
      centered(c,shortcuts[i],bx[i]+bw[i]/2f,699,13,ice,true);
    }
  }
  private void compactDigitalFuelTrim(Canvas c,int x,int y,int w,int h,
                                      String name,float reading,int accent){
    panel(c,x,y,w,h,0xff081421,16);
    stroke(c,x,y,w,h,accent,16);
    text(c,name,x+19,y+44,23,iceForFuelTrim(),true);
    String value=val(reading,1);
    text(c,value,x+19,y+118,52,iceForFuelTrim(),true);
    text(c,"%",x+w-33,y+116,19,accent,true);
    line(c,x+17,y+h-64,x+w-17,y+h-64,0xff344457,4);
    if(Float.isFinite(reading)){
      float ratio=clipped(reading,-25,25);
      line(c,x+17,y+h-64,x+17+(w-34)*ratio,y+h-64,accent,5);
    }
    text(c,Float.isFinite(reading)?"ECU • LIVE":"ECU • N/A",
      x+19,y+h-21,16,Float.isFinite(reading)?0xff70dbbd:0xffa8b6c8,true);
  }
  private int iceForFuelTrim(){return Color.WHITE;}


  /**
   * Remaining 20 designs: the original image remains the base layer, while
   * skin-specific instrument placements prevent a single giant generic
   * right-hand OBD rectangle from obscuring the car photograph.
   * No demo RPM, fuel trim, speed, tyre pressure or fuel range is used.
   */
  private void drawPhotoSkin(Canvas c,int id,int accent){
    drawArt(c,id);
    final ObdReader.Reading rd=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    // Layouts: 1=motorsport dial row, 2=large tachometer,
    // 3=compact telemetry bars, 4=right-hand 2x2 cluster,
    // 5=vehicle status, 6=full app-list artwork.
    final int[] shape={0,1,2,1,3,4,1,2,3,1,4,3,4,2,4,3,4,1,5,6,4};
    int kind=shape[id];
    final int[] clocksX={0,37,856,450,38,40,40,40,40,40,40,40,38,670,40,460,40,40,44,40,40};
    int cx=clocksX[id],cy=(id==2||id==7||id==13)?512:65;
    if(id==15)cy=65;
    // Replace the picture's decorative/sample clock, keeping it in roughly
    // the same native region as the approved concept.
    panel(c,cx,cy,kind==2?333:285,105,0xe60a1420,13);
    stroke(c,cx,cy,kind==2?333:285,105,accent,13);
    text(c,time(),cx+17,cy+53,45,Color.WHITE,true);
    text(c,shorten(date(),24),cx+17,cy+84,14,0xffbbcbdb,false);
    ObdReader.Reading data=rd;
    float[] vv={data.rpm,data.stft,data.ltft,data.coolantC};
    String[] nn={"RPM","STFT B1","LTFT B1","TEMP APĂ"};
    String[] unit={"rpm","%","%","°C"};
    float[] low={0,-25,-25,40},high={8000,25,25,120};
    int[] colors={accent,0xff32c8fa,0xffe9a23d,0xff62ddc1};
    if(kind==1){
      // EVO Classic, Gauge Pro, Night, Mountain, Hero, Minimal Sport:
      // analogue instrument strip near the photo's lower row.
      panel(c,94,479,1172,234,0xe408111d,17);
      stroke(c,94,479,1172,234,accent,17);
      for(int i=0;i<4;i++){
        float x=235+290*i;
        gauge(c,x,561,69,nn[i],val(vv[i],i==0||i==3?0:1),
          unit[i],vv[i],low[i],high[i],colors[i],id);
      }
    }else if(kind==2){
      // Future / GT Cockpit: one giant actual RPM dial plus compact values
      // at the right, retaining the illustrated vehicle under the RPM ring.
      panel(c,91,185,426,335,0xc6091521,20);
      stroke(c,91,185,426,335,accent,20);
      gauge(c,302,348,119,"RPM",val(vv[0],0),"rpm",vv[0],0,8000,accent,id);
      for(int i=1;i<4;i++){
        float y=420+90*(i-1);
        miniValue(c,738,y,148,78,nn[i],vv[i],unit[i],colors[i],i);
      }
    }else if(kind==3){
      // Multi Info / digital-bar examples: narrow live numerical bars.
      panel(c,94,516,1169,197,0xdf09131f,17);
      stroke(c,94,516,1169,197,accent,17);
      for(int i=0;i<4;i++)
        miniValue(c,112+286*i,535,263,155,nn[i],vv[i],unit[i],colors[i],i);
    }else if(kind==4){
      // App Center, Digital Dash derivative, Tech Grid, showroom and
      // Performance: four independent gauges in a right-side cluster.
      panel(c,780,384,486,328,0xd808121e,17);
      stroke(c,780,384,486,328,accent,17);
      for(int i=0;i<4;i++){
        float x=890+(i%2)*254,y=463+(i/2)*148;
        gauge(c,x,y,48,nn[i],val(vv[i],i==0||i==3?0:1),unit[i],
          vv[i],low[i],high[i],colors[i],id);
      }
    }else if(kind==5){
      // Car Status: never borrow fabricated tyre PSI / fuel range from
      // concept art; present only sensors currently read from the ECU.
      panel(c,778,108,483,550,0xed08121e,18);
      stroke(c,778,108,483,550,accent,18);
      text(c,"STARE VEHICUL • ECU",802,151,23,Color.WHITE,true);
      for(int i=0;i<4;i++){
        int y=187+i*111;
        miniValue(c,802,y,437,96,nn[i],vv[i],unit[i],colors[i],i);
      }
      text(c,"Alte valori nu sunt disponibile prin PID-urile citite.",799,678,14,
        0xffbbcad9,false);
    }else if(kind==6){
      // The app-list-themed original uses real installed apps, not fake
      // destinations. A touch anywhere in the large panel opens AppsDrawer.
      panel(c,115,149,1050,449,0xe70a1420,19);
      stroke(c,115,149,1050,449,accent,19);
      text(c,"APLICAȚII INSTALATE",153,225,38,Color.WHITE,true);
      text(c,"APASĂ AICI PENTRU LISTA REALĂ DE APLICAȚII",153,291,20,
        0xff9dbdd5,false);
      text(c,"CĂUTARE • PICTOGRAME REALE • LANSARE DIRECTĂ",153,341,17,accent,true);
      miniValue(c,153,411,227,127,nn[0],vv[0],unit[0],colors[0],0);
      miniValue(c,394,411,227,127,nn[1],vv[1],unit[1],colors[1],1);
    }
    // Music is drawn only where the original has a media player. Other
    // concepts expose media through the existing Home side navigation.
    if(kind!=5&&kind!=6)nativeMediaOverlay(c,id,accent);
    panel(c,6,628,392,89,0xe608121e,15);
    stroke(c,6,628,392,89,accent,15);
    String[] names={"APLICAȚII","SKINURI","HARTĂ"},glyph={"▦","◈","➤"};
    int[] x={14,143,278},width={118,125,112};
    for(int i=0;i<3;i++){
      panel(c,x[i],633,width[i],76,0xff1c2b3b,9);
      centered(c,glyph[i],x[i]+width[i]/2f,670,30,accent,true);
      centered(c,names[i],x[i]+width[i]/2f,699,13,Color.WHITE,true);
    }
    text(c,String.format(Locale.US,"%02d / 21  %s",id+1,NAMES[id]),
      413,705,17,Color.WHITE,true);
  }
  private void miniValue(Canvas c,int x,float y,int w,int h,String name,
                         float value,String unit,int accent,int type){
    panel(c,x,y,w,h,0xee0b1623,13);
    stroke(c,x,y,w,h,accent,13);
    text(c,name,x+14,y+30,19,accent,true);
    text(c,val(value,type==0||type==3?0:1),x+14,y+77,35,Color.WHITE,true);
    text(c,unit,x+w-47,y+78,16,0xffc2d4e5,false);
    line(c,x+14,y+h-20,x+w-14,y+h-20,0xff384d63,4);
    if(Float.isFinite(value)){
      float ratio=type==0?clipped(value,0,8000):type==3?
        clipped(value,40,120):clipped(value,-25,25);
      line(c,x+14,y+h-20,x+14+(w-28)*ratio,y+h-20,accent,4);
    }
  }
  private void nativeMediaOverlay(Canvas c,int id,int accent){
    int x=id==2?936:id==3?798:799;
    int y=(id==8||id==11)?79:78;
    int w=1264-x,h=(id==2)?292:297;
    // Compact native media panel sits over the image's mocked track,
    // ensuring the album/title/transport state are never invented.
    panel(c,x,y,w,h,0xf0081421,15);
    stroke(c,x,y,w,h,accent,15);
    text(c,shorten(host.mediaName,23),x+18,y+31,21,Color.WHITE,true);
    MediaController m=host.media;
    String title="",artist="";
    Bitmap art=null;
    if(m!=null&&m.getMetadata()!=null){
      CharSequence song=m.getMetadata().getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence performer=m.getMetadata().getText(MediaMetadata.METADATA_KEY_ARTIST);
      title=song==null?"":song.toString();
      artist=performer==null?"":performer.toString();
      art=m.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
      if(art==null)art=m.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ART);
    }
    if(title.isEmpty())title="Fără redare activă";
    if(artist.isEmpty())artist="MediaSession / alege player";
    int cover=Math.min(123,Math.max(67,w/3));
    panel(c,x+18,y+59,cover,cover,0xff481a32,11);
    if(art!=null){
      colour(Color.WHITE);p.setFilterBitmap(true);
      c.drawBitmap(art,null,new Rect(x+18,y+59,x+18+cover,y+59+cover),p);
    }else{
      centered(c,"MEDIA",x+18+cover/2f,y+116,22,Color.WHITE,true);
    }
    int textX=x+cover+32;
    text(c,shorten(title,Math.max(8,(w-cover-45)/15)),textX,y+111,21,Color.WHITE,true);
    text(c,shorten(artist,Math.max(8,(w-cover-45)/11)),textX,y+145,14,0xffa2b5c8,false);
    line(c,x+19,y+h-99,x+w-19,y+h-99,0xff45596c,3);
    boolean playing=m!=null&&m.getPlaybackState()!=null&&
      m.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,x+w*.24f,y+h-43,0,Color.WHITE);
    panel(c,x+w*.48f-17,y+h-84,70,68,accent,28);
    MediaVectorIcons.draw(c,x+w*.48f+18,y+h-50,playing?3:1,Color.WHITE);
    MediaVectorIcons.draw(c,x+w*.80f,y+h-43,2,Color.WHITE);
  }

  private void drawNativeStatusBar(Canvas c,int id){
    // Static concept images contain old fake Android status icons and times.
    // Always cover those illustrated values with real system clock + skin name.
    panel(c,0,0,1280,54,0xf508111d,0);
    text(c,String.format(Locale.US,"%02d/21   %s",id+1,NAMES[id]),
      17,36,23,Color.WHITE,true);
    // Avoid drawing a second clock above a real native clock card.
    // Digital Dash has its own large clock; the other 20 render an independent
    // header clock only if their layout has no visible native clock card.
    if(id>0&&ThemeNativePanels.profile(id).clock==null)
      text(c,time(),1153,36,23,0xffd8e7f5,true);
  }
  /**
   * Approved theme #02: the background is ONLY photography. Every clock,
   * frame, label, album image, sensor number and touch control is drawn live.
   * No centre ECU/ABS/Doors/Airbag mock panel is ever created.
   */
  private void drawCinematicTwo(Canvas c){
    Bitmap photo=fullArt(1);
    colour(0xff050e1c);
    c.drawRect(0,0,1280,720,p);
    if(photo!=null&&!photo.isRecycled()){
      colour(Color.WHITE);
      p.setFilterBitmap(true);
      c.drawBitmap(photo,new Rect(0,0,photo.getWidth(),photo.getHeight()),
        new Rect(0,0,1280,720),p);
    }

    // Five icons plus the existing Settings action, all working and vector.
    panel(c,0,0,89,720,0xe6060e1b,0);
    int[] cy={72,169,266,363,460,557};
    for(int i=0;i<6;i++){
      NavVectorIcons.draw(c,i,45,cy[i],i==0?0xff5cc9ff:0xffdbeaff);
    }

    // Responsive native date/clock. No stale static time in the photo.
    text(c,time(),119,73,57,Color.WHITE,true);
    text(c,shorten(date(),33),123,113,17,0xffdeeafa,false);

    // Cinematic, clean instrument faces with genuine OBD-II PID values.
    ObdReader.Reading rd=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    final int ice=0xff36bdff, crimson=0xffff455d;
    colour(0xef07111f);
    c.drawCircle(237,449,158,p);
    c.drawCircle(1071,450,147,p);
    gauge(c,237,449,145,"RPM",val(rd.rpm,0),"rpm",rd.rpm,0,8000,crimson,1);
    gauge(c,1071,450,132,"TEMP APĂ",val(rd.coolantC,0),"°C",
      rd.coolantC,40,120,ice,2);

    // Real selected music player only. No branded placeholders, no static art.
    panel(c,884,13,381,148,0xea061021,15);
    stroke(c,884,13,381,148,0xff2b8bd2,15);
    text(c,shorten(host.mediaName,23),998,43,19,Color.WHITE,true);
    MediaController m=host.media;
    String song="",artist="";
    Bitmap album=null;
    if(m!=null&&m.getMetadata()!=null){
      CharSequence t=m.getMetadata().getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence a=m.getMetadata().getText(MediaMetadata.METADATA_KEY_ARTIST);
      song=t==null?"":t.toString();artist=a==null?"":a.toString();
      album=m.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
      if(album==null)album=m.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ART);
    }
    if(song.isEmpty())song="Fără redare activă";
    if(artist.isEmpty())artist="Alege playerul / MediaSession";
    panel(c,896,28,88,89,0xff152b46,8);
    if(album!=null){
      colour(Color.WHITE);p.setFilterBitmap(true);
      c.drawBitmap(album,null,new Rect(898,30,982,115),p);
    }else centered(c,"MEDIA",940,78,15,0xffd9edff,true);
    text(c,shorten(song,24),998,73,17,Color.WHITE,true);
    text(c,shorten(artist,27),998,96,13,0xff9dc3e9,false);
    boolean playing=m!=null&&m.getPlaybackState()!=null&&
      m.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    MediaVectorIcons.draw(c,1040,133,0,Color.WHITE);
    MediaVectorIcons.draw(c,1126,133,playing?3:1,Color.WHITE);
    MediaVectorIcons.draw(c,1214,133,2,Color.WHITE);

    // Fuel trims stay functional and clearly separate from coolant. They do
    // not imply that ABS/Airbag/Doors data are available via ELM327.
    panel(c,876,596,388,108,0xe9091524,12);
    stroke(c,876,596,388,108,0xff305f96,12);
    text(c,"STFT B1",895,631,16,ice,true);
    text(c,val(rd.stft,1)+"%",1031,632,25,Color.WHITE,true);
    text(c,"LTFT B1",895,672,16,crimson,true);
    text(c,val(rd.ltft,1)+"%",1031,673,25,Color.WHITE,true);
    // Do not add any centre vehicle-status panel: only approved native HUD.
  }

  private boolean touchCinematicTwo(float x,float y){
    if(x<90){
      int slot=Math.round((y-72f)/97f);
      if(slot<0||slot>5)return false;
      if(Math.abs(y-(72+97*slot))>43)return false;
      if(slot==4){host.showInstalledApps();return true;}
      host.page=slot;
      if(host.view!=null)host.view.invalidate();
      host.placeMap();
      return true;
    }
    if(x>=884&&y>=13&&x<=1265&&y<=161){
      if(y>=106){
        host.mediaAction(x<1080?0:x<1168?1:2);
      }else host.choosePlayer();
      return true;
    }
    if(x>=117&&x<=650&&y<=142){showPicker();return true;}
    if((x>=93&&x<=402&&y>=290&&y<=610)||
       (x>=922&&x<=1226&&y>=292&&y<=594)||
       (x>=876&&x<=1264&&y>=596&&y<=704)){
      host.showObdStatus();
      return true;
    }
    return false;
  }

  void draw(Canvas c){
    // Independent 22nd UHD cockpit; original 21 themes remain unchanged.
    if(selected==21){ultra.draw(c);return;}
    if(selected==RaceHudFinalTheme.ID||selected==RaceHudFinalTheme.ANGULAR_ID){raceHud.draw(c);return;}
    if(selected>=CinematicTrioTheme.FIRST&&selected<=CinematicTrioTheme.LAST){trio.draw(c,selected);return;}
    // EVO Digital Dash has its own bespoke left/right interactive cockpit.
    // The remaining twenty models use layouts aligned to the *individual*
    // source artwork, rather than one generic four-gauge card on the right.
    int id=selected;
    if(id==0){drawEvoDigitalDashNative(c);return;}
    if(id==1){drawCinematicTwo(c);return;}
    drawArt(c,id);
    drawNativeStatusBar(c,id);
    nativePanels.draw(c,id);
  }
  void ultraTouchDown(float x,float y){if(selected>=21)ultra.down(x,y);}
  void ultraTouchMove(float x,float y){if(selected>=21)ultra.move(x,y);}
  void ultraTouchCancel(){ultra.cancel();}
  boolean ultraTouchUp(float x,float y){
    if(selected==21)return ultra.up(x,y);
    if(selected==RaceHudFinalTheme.ID||selected==RaceHudFinalTheme.ANGULAR_ID)
      return ultra.upSlotOnly(x,y)||raceHud.touch(x,y);
    if(selected>=CinematicTrioTheme.FIRST&&selected<=CinematicTrioTheme.LAST)
      return ultra.upSlotOnly(x,y)||trio.touch(x,y);
    return false;
  }
  boolean touch(float x,float y){
    if(selected==21)return ultra.touch(x,y);
    if(selected==RaceHudFinalTheme.ID||selected==RaceHudFinalTheme.ANGULAR_ID)return raceHud.touch(x,y);
    if(selected>=CinematicTrioTheme.FIRST&&selected<=CinematicTrioTheme.LAST)
      return trio.touch(x,y);
    if(selected==1)return touchCinematicTwo(x,y);
    if(selected>0&&nativePanels.touch(x,y))return true;
    if(selected==0&&x>=860&&x<=1265&&y>=74&&y<=412){
      if(y>=302){
        host.mediaAction(x<1080?0:x<1165?1:2);
      }else host.choosePlayer();
      return true;
    }
    // The App Center and App Launcher backgrounds include decorative example
    // icons. Touching that area opens the REAL installed-app search drawer.
    if(selected==0&&((x>100&&x<629&&y>220&&y<573)||
        (x>=627&&x<=843&&y>=220&&y<=436))){
      host.showObdStatus();return true;
    }
    if((selected==5||selected==19)&&x>95&&x<620&&y>225&&y<620){
      host.showInstalledApps();return true;
    }
    if(x<108&&y<66){host.showInstalledApps();return true;}
    if(x<90&&y>=228&&y<=615){
      int slot=Math.min(5,Math.max(0,(int)((y-233)/61)));
      if(slot==4){host.showInstalledApps();return true;}
      int[] pageMap={0,1,2,3,4,5};
      host.page=pageMap[slot];
      if(host.view!=null)host.view.invalidate();
      host.placeMap();return true;
    }
    if(appRect.contains((int)x,(int)y)){host.showInstalledApps();return true;}
    if(skinRect.contains((int)x,(int)y)){showPicker();return true;}
    if(mapsRect.contains((int)x,(int)y)){host.page=2;host.view.invalidate();host.placeMap();return true;}
    if(mediaRect.contains((int)x,(int)y)){
      if(y>mediaRect.bottom-92){
        int button=x<mediaRect.left+340?0:x<mediaRect.left+470?1:2;
        host.mediaAction(button);
      }else host.choosePlayer();
      return true;
    }
    if(statsRect.contains((int)x,(int)y)){host.showObdStatus();return true;}
    return false;
  }
  Bitmap preview(int id){
    // Show the ACTUAL native skin in the gallery. Never show the source
    // concept image with fake music titles, clocks, app logos or ECU values.
    id=clamp(id);
    Bitmap thumb=Bitmap.createBitmap(480,270,Bitmap.Config.ARGB_8888);
    Canvas stage=new Canvas(thumb);
    stage.scale(480f/1280f,270f/720f);
    int before=selected;
    try{
      selected=id;
      draw(stage);
    }finally{
      selected=before;
    }
    return thumb;
  }
  void choosePack(){
    Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);
    intent.setType("application/zip");
    intent.addCategory(Intent.CATEGORY_OPENABLE);
    try{host.startActivityForResult(intent,PICK_SKIN_PACK);}
    catch(RuntimeException problem){
      new AlertDialog.Builder(host).setTitle("Importă skinuri")
        .setMessage("Selectorul de fișiere ZIP nu este disponibil pe firmware-ul Android.")
        .setPositiveButton("OK",null).show();
    }
  }
  private static void removeTree(File root){
    if(root==null||!root.exists())return;
    File[] children=root.listFiles();
    if(children!=null)for(File child:children)removeTree(child);
    root.delete();
  }
  void importPack(Uri uri){
    if(uri==null)return;
    new Thread(()->{
      String folder="skins_pack_"+System.currentTimeMillis();
      File temp=new File(host.getFilesDir(),folder);
      boolean[] seen=new boolean[COUNT];
      boolean atlasSeen=false;
      long total=0L;int entries=0;
      String error=null;
      try{
        if(!temp.mkdirs())throw new IOException("Nu pot crea directorul skinurilor");
        try(InputStream incoming=host.getContentResolver().openInputStream(uri)){
          if(incoming==null)throw new IOException("Nu pot citi arhiva ZIP");
          try(ZipInputStream zip=new ZipInputStream(incoming)){
            ZipEntry entry;
            while((entry=zip.getNextEntry())!=null){
              if(++entries>32)throw new IOException("Prea multe fișiere în pachet");
              if(entry.isDirectory())continue;
              String file=entry.getName();
              // The original 21-design ZIP includes documentation.
              if("README.txt".equalsIgnoreCase(file)){zip.closeEntry();continue;}
              if(file.startsWith("skins/"))file=file.substring(6);
              boolean isAtlas="atlas.webp".equals(file);
              int index=-1;
              if(!isAtlas){
                for(int i=0;i<21;i++){
                  if(file.equals(String.format(Locale.US,"skin_%02d.webp",i))){index=i;break;}
                }
              }
              if(!isAtlas&&index<0)throw new IOException("Fișier nepermis: "+file);
              if(file.contains("/")||file.contains("\\")||file.contains(".."))
                throw new IOException("Cale periculoasă în arhivă");
              File destination=new File(temp,file);
              long bytes=0;byte[] buffer=new byte[8192];
              try(FileOutputStream out=new FileOutputStream(destination)){
                int length;
                while((length=zip.read(buffer))!=-1){
                  total+=length;bytes+=length;
                  if(total>28000000L||bytes>3500000L)
                    throw new IOException("Pachetul depășește limita de memorie");
                  out.write(buffer,0,length);
                }
              }
              BitmapFactory.Options header=new BitmapFactory.Options();
              header.inJustDecodeBounds=true;
              BitmapFactory.decodeFile(destination.getAbsolutePath(),header);
              if(header.outWidth<80||header.outHeight<45||
                 header.outWidth>2400||header.outHeight>1600)
                throw new IOException("Imagine invalidă: "+file);
              if(isAtlas)atlasSeen=true;else seen[index]=true;
              zip.closeEntry();
            }
          }
        }
        if(!atlasSeen)throw new IOException("Lipsește atlas.webp");
        for(int i=0;i<21;i++)if(!seen[i])
          throw new IOException("Lipsește skin_"+String.format(Locale.US,"%02d",i)+".webp");
        if(!prefs.edit().putString("skin_pack_dir",folder).putBoolean("use_custom_skin_pack",true).commit())
          throw new IOException("Nu pot salva selecția imaginilor");
      }catch(Exception e){error=e.getMessage();removeTree(temp);}
      final String failure=error;
      host.runOnUiThread(()->{
        if(failure!=null){
          new AlertDialog.Builder(host).setTitle("Import skinuri nereușit")
            .setMessage(failure).setPositiveButton("OK",null).show();
        }else{
          if(fullArt!=null&&!fullArt.isRecycled())fullArt.recycle();
          fullArt=null;fullArtId=-1;
          loadAtlas();
          if(host.view!=null)host.view.invalidate();
          Toast.makeText(host,"21 skinuri importate. EVO Digital Dash este primul.",
            Toast.LENGTH_LONG).show();
          showPicker();
        }
      });
    },"k2401-skinpack-import").start();
  }
  private int dp(int pixels){return Math.round(pixels*host.getResources().getDisplayMetrics().density);}
  void showPicker(){
    // Thumbnails use the *actual original screenshots* from the concept sheet,
    // NOT thumbnails of some other skin. One tap -> full-screen preview -> Apply.
    ScrollView scroll=new ScrollView(host);scroll.setBackgroundColor(0xff0b121f);
    LinearLayout list=new LinearLayout(host);list.setOrientation(LinearLayout.VERTICAL);
    list.setPadding(dp(14),dp(10),dp(14),dp(15));scroll.addView(list);
    for(int i=0;i<COUNT;i++){
      final int index=i;
      LinearLayout entry=new LinearLayout(host);entry.setGravity(Gravity.CENTER_VERTICAL);
      entry.setPadding(dp(6),dp(5),dp(6),dp(5));
      entry.setBackgroundColor(i==selected?0xff35212d:0xff121b2a);
      Bitmap image=preview(i);
      ImageView thumbnail=new ImageView(host);
      thumbnail.setImageBitmap(image);
      thumbnail.setScaleType(ImageView.ScaleType.FIT_CENTER);
      entry.addView(thumbnail,new LinearLayout.LayoutParams(dp(230),dp(128)));
      TextView title=new TextView(host);
      title.setText((i+1)+". "+NAMES[i]+(i==selected?"  ✓":""));
      title.setTextColor(Color.WHITE);title.setTextSize(17);
      title.setPadding(dp(20),0,0,0);
      entry.addView(title,new LinearLayout.LayoutParams(0,-2,1f));
      list.addView(entry,new LinearLayout.LayoutParams(-1,dp(146)));
      entry.setOnClickListener(v->previewDialog(index));
    }
    galleryDialog=new AlertDialog.Builder(host).setTitle("Skinuri EVO • "+COUNT+" modele • 21 originale + 6 teme noi")
      .setView(scroll).setNegativeButton("Închide",null).create();
    galleryDialog.show();
  }
  private void previewDialog(int which){
    if(galleryDialog!=null){galleryDialog.dismiss();galleryDialog=null;}
    // The enlarged preview must show the REAL functional Home canvas,
    // not just the original AI mockup with fake RPM / time / media numbers.
    // Live ECU values remain live; unavailable values are labelled N/A.
    Bitmap fullPreview=null;
    try{
      fullPreview=Bitmap.createBitmap(1280,720,Bitmap.Config.ARGB_8888);
      int previous=selected;selected=which;
      try{draw(new Canvas(fullPreview));}
      finally{selected=previous;}
    }catch(RuntimeException|OutOfMemoryError failure){
      if(fullPreview!=null&&!fullPreview.isRecycled())fullPreview.recycle();
      fullPreview=null;
    }
    final Bitmap rendered=fullPreview;
    Bitmap fallback=rendered==null?fullArt(which):null;
    if(fallback==null&&rendered==null)fallback=preview(which);
    ImageView view=new ImageView(host);
    view.setImageBitmap(rendered==null?fallback:rendered);
    view.setScaleType(ImageView.ScaleType.FIT_CENTER);
    view.setAdjustViewBounds(true);
    view.setMinimumHeight(dp(250));
    AlertDialog dialog=new AlertDialog.Builder(host).setTitle((which+1)+". "+NAMES[which]+" • LIVE")
      .setView(view)
      .setPositiveButton("APLICĂ ACEST SKIN",(d,w)->{
        select(which);host.page=0;
        if(host.view!=null)host.view.invalidate();
        host.placeMap();
        android.widget.Toast.makeText(host,"Skin salvat: "+NAMES[which],
          android.widget.Toast.LENGTH_SHORT).show();
      })
      .setNeutralButton("Următorul",(d,w)->previewDialog((which+1)%COUNT))
      .setNegativeButton("Înapoi",(d,w)->previewDialog((which+COUNT-1)%COUNT))
      .create();
    dialog.setOnDismissListener(d->{
      // Avoid retaining a 1280x720 preview after the picker is closed.
      view.setImageDrawable(null);
      if(rendered!=null&&!rendered.isRecycled())rendered.recycle();
      // The preview temporarily draws a different skin. Restore the active
      // theme's native hit rectangles before any subsequent touch.
      if(host.view!=null)host.view.invalidate();
    });
    dialog.show();
  }
}
