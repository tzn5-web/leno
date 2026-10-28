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
    "CAR STATUS","APP LAUNCHER","PERFORMANCE"
  };
  // Variants correspond to concept-sheet crops in /assets/skins/atlas.webp.
  static final int COUNT=NAMES.length;
  // Each of the 21 originals has a distinct native interaction/gauge profile,
  // rather than just recycling one of six dashboard canvases.
  private static final int[] STYLES={
    0,1,2,3,4,5,6, 7,8,9,10,11,12,13, 14,15,16,17,18,19,20
  };
  private static final int[] COLORS={
    0xfff02e4a,0xffff3450,0xff1ec7ff,0xfff02e4a,0xff24c9ff,0xffef3551,
    0xffff314e,0xfffe3951,0xffff3556,0xffed4a50,0xff21c4eb,0xffff7650,
    0xffff3650,0xffed3154,0xff29d6ee,0xffed2e54,0xfff55b43,0xff27cdf0,
    0xffe52b51,0xff33b6ea,0xffee334d
  };
  private final MainActivity host;
  private final SharedPreferences prefs;
  private final Paint p=new Paint(3);
  private Bitmap atlas;
  private Bitmap fullArt;
  private int fullArtId=-1;
  private AlertDialog galleryDialog;
  private int selected;
  private final Rect mediaRect=new Rect(640,86,1260,364);
  private final Rect statsRect=new Rect(640,387,1260,699);
  private final Rect appRect=new Rect(13,630,132,714);
  private final Rect skinRect=new Rect(142,630,267,714);
  private final Rect mapsRect=new Rect(277,630,391,714);

  SkinEngine(MainActivity activity){
    host=activity;
    prefs=host.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
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
    options.inPreferredConfig=Bitmap.Config.RGB_565;
    // The official 21 designs always come from the APK assets.
    try(InputStream stream=host.getAssets().open("skins/atlas.webp")){
      atlas=BitmapFactory.decodeStream(stream,null,options);
    }catch(IOException|RuntimeException ignored){}
    if(atlas==null){
      File root=packDir();
      File local=root==null?null:new File(root,"atlas.webp");
      if(local!=null&&local.isFile())atlas=BitmapFactory.decodeFile(local.getPath(),options);
    }
  }
  private Bitmap fullArt(int id){
    if(fullArt!=null&&!fullArt.isRecycled()&&fullArtId==id)return fullArt;
    if(fullArt!=null&&!fullArt.isRecycled())fullArt.recycle();
    fullArt=null;fullArtId=id;
    // Prefer APK-bundled images even if an older prerelease imported a ZIP.
    try(InputStream stream=host.getAssets().open(
      String.format(Locale.US,"skins/skin_%02d.webp",id))){
      BitmapFactory.Options opts=new BitmapFactory.Options();
      opts.inPreferredConfig=Bitmap.Config.RGB_565;
      fullArt=BitmapFactory.decodeStream(stream,null,opts);
    }catch(IOException|RuntimeException ignored){}
    if(fullArt==null){
      File root=packDir();
      File image=root==null?null:new File(root,String.format(Locale.US,"skin_%02d.webp",id));
      if(image!=null&&image.isFile()){
        BitmapFactory.Options opts=new BitmapFactory.Options();
        opts.inPreferredConfig=Bitmap.Config.RGB_565;
        fullArt=BitmapFactory.decodeFile(image.getAbsolutePath(),opts);
      }
    }
    return fullArt;
  }
  int selection(){return selected;}
  void select(int id){
    selected=clamp(id);
    if(fullArt!=null&&!fullArt.isRecycled())fullArt.recycle();fullArt=null;fullArtId=-1;
    prefs.edit().putInt(KEY,selected).commit();
    if(host.view!=null)host.view.invalidate();
    host.placeMap();
  }
  void release(){
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
    colour(0xff090f18);c.drawColor(0xff090f18);
    Bitmap original=fullArt(id);
    if(original!=null&&!original.isRecycled()){
      p.setFilterBitmap(true);
      c.drawBitmap(original,null,new Rect(0,0,1280,720),p);
      return;
    }
    if(atlas!=null&&!atlas.isRecycled()){
      int w=atlas.getWidth()/3,h=atlas.getHeight()/7;
      Rect src=new Rect((id%3)*w,(id/3)*h,(id%3+1)*w,(id/3+1)*h);
      p.setFilterBitmap(true);
      c.drawBitmap(atlas,src,new Rect(0,0,1280,720),p);
      return;
    }
    // Offline procedural fallback: actual car scenes are supplied as concept
    // artwork, not assembled by fabricating photos or telemetry.
    colour(0xff080e1b);
    p.setShader(new LinearGradient(0,0,1280,720,0xff172135,
      0xff070a10,Shader.TileMode.CLAMP));
    c.drawRect(0,0,1280,720,p);p.setShader(null);
    colour(0x501f2b3c);
    for(int a=-720;a<1800;a+=28)c.drawLine(a,0,a+700,720,p);
    // Deliberately generic Lancer-inspired silhouette if image asset missing.
    colour(0xff152232);
    Path silhouette=new Path();silhouette.moveTo(85,500);silhouette.lineTo(165,450);
    silhouette.lineTo(290,385);silhouette.lineTo(465,377);
    silhouette.lineTo(545,438);silhouette.lineTo(596,468);
    silhouette.lineTo(609,515);silhouette.lineTo(88,515);silhouette.close();
    c.drawPath(silhouette,p);
    colour(COLORS[id]);
    p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3);c.drawPath(silhouette,p);
    c.drawCircle(205,515,39,p);c.drawCircle(491,515,39,p);
    p.setStyle(Paint.Style.FILL);
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
    text(c,"YT",x+59,y+145,45,Color.WHITE,true);
    text(c,"MUSIC",x+52,y+176,19,Color.WHITE,true);
    text(c,shorten(song,27),x+174,y+124,26,Color.WHITE,true);
    text(c,shorten(artist,35),x+174,y+163,17,0xffa9b9ce,false);
    line(c,x+178,y+178,x+w-20,y+178,0xff405266,4);
    if(media!=null&&media.getPlaybackState()!=null){
      boolean playing=media.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
      text(c,"◀◀",x+220,y+h-25,26,0xffeff5ff,true);
      panel(c,x+350,y+h-72,58,57,accent,29);
      text(c,playing?"Ⅱ":"▶",x+369,y+h-31,29,Color.WHITE,true);
      text(c,"▶▶",x+490,y+h-25,26,0xffeff5ff,true);
    }else{
      text(c,"◀◀",x+220,y+h-25,26,0xffeff5ff,true);
      panel(c,x+350,y+h-72,58,57,accent,29);
      text(c,"▶",x+369,y+h-31,29,Color.WHITE,true);
      text(c,"▶▶",x+490,y+h-25,26,0xffeff5ff,true);
    }
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
    final int crimson=0xfffa304d,azure=0xff30cfff,ice=0xffedf6ff;
    // Repaint only the obsolete labels / clock from the original render.
    panel(c,2,4,308,46,0xf009121e,11);
    text(c,"EVO DIGITAL DASH",19,36,24,ice,true);
    panel(c,352,86,236,87,0xf0081421,17);
    text(c,time(),373,130,43,ice,true);
    text(c,shorten(date(),27),373,159,16,0xffcddde9,false);

    // The mockup has "0 km/h" without a vehicle-speed PID. Do not make it
    // appear live: replace just its centre with a real connection indicator.
    panel(c,379,246,169,155,0xf0081420,17);
    text(c,"ECU / ELM327",393,281,17,0xffa7bcd1,true);
    ObdReader.Reading data=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    text(c,data.live?"CONECTAT":"N/A",393,333,27,data.live?0xff5af5ba:ice,true);
    text(c,"DATE LIVE",393,362,15,azure,true);

    // Main round gauges. Semi-opaque black under the *dynamic* arcs hides
    // baked-in readings and keeps the original tachometer-like placement.
    colour(0xf207111e);c.drawCircle(240,328,108,p);c.drawCircle(658,328,108,p);
    gauge(c,240,323,98,"RPM",val(data.rpm,0),"rpm",data.rpm,0,8000,crimson,1);
    gauge(c,658,323,98,"TEMP APĂ",val(data.coolantC,0),"°C",
      data.coolantC,40,120,azure,2);

    // Media panel exactly within the right-hand rectangular music location.
    panel(c,799,74,466,362,0xee08121e,15);
    stroke(c,799,74,466,362,crimson,15);
    text(c,shorten(host.mediaName,25),822,108,22,ice,true);
    MediaController controller=host.media;
    Bitmap cover=null;
    if(controller!=null&&controller.getMetadata()!=null){
      cover=controller.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
      if(cover==null)cover=controller.getMetadata().getBitmap(MediaMetadata.METADATA_KEY_ART);
    }
    panel(c,821,128,124,146,0xff3f1526,10);
    if(cover!=null){
      colour(Color.WHITE);p.setFilterBitmap(true);
      c.drawBitmap(cover,null,new Rect(823,130,943,272),p);
    }else{
      centered(c,"YT",883,202,42,ice,true);
      centered(c,"MUSIC",883,231,17,ice,true);
    }
    String song="",performer="";
    if(controller!=null&&controller.getMetadata()!=null){
      CharSequence t=controller.getMetadata().getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence a=controller.getMetadata().getText(MediaMetadata.METADATA_KEY_ARTIST);
      song=t==null?"":t.toString();performer=a==null?"":a.toString();
    }
    if(song.isEmpty())song="Fără redare activă";
    if(performer.isEmpty())performer="Alege playerul / MediaSession";
    text(c,shorten(song,22),962,183,23,ice,true);
    text(c,shorten(performer,29),962,218,16,0xff9fb2c6,false);
    line(c,967,260,1242,260,0xff41556c,4);
    if(controller!=null&&controller.getMetadata()!=null&&controller.getPlaybackState()!=null){
      long duration=controller.getMetadata().getLong(MediaMetadata.METADATA_KEY_DURATION);
      long pos=controller.getPlaybackState().getPosition();
      if(duration>0&&pos>=0)line(c,967,260,967+275f*Math.min(1f,(float)pos/duration),260,
        crimson,4);
    }
    panel(c,999,319,70,73,crimson,33);
    boolean playing=controller!=null&&controller.getPlaybackState()!=null&&
      controller.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    centered(c,"◀◀",967,363,27,ice,true);
    centered(c,playing?"Ⅱ":"▶",1034,368,29,ice,true);
    centered(c,"▶▶",1143,363,27,ice,true);
    text(c,controller==null?"MEDIA OFFLINE":"MEDIA LIVE",823,417,13,
      controller==null?0xffacbacb:0xff5af5ba,true);

    // The two rectangular live fuel-trim instruments correspond to the two
    // cards in the original lower right, not a duplicate four-dial panel.
    compactDigitalFuelTrim(c,799,462,223,226,"STFT B1",data.stft,azure);
    compactDigitalFuelTrim(c,1034,462,229,226,"LTFT B1",data.ltft,crimson);
    text(c,"K2401 • "+NAMES[0],416,698,16,0xffb5c8d9,true);

    // Small functional bottom dock instead of a 620x310 HUD obscuring the car.
    panel(c,5,630,389,88,0xe60a1320,14);
    stroke(c,5,630,389,88,0xffa72a43,14);
    String[] shortcuts={"APLICAȚII","SKINURI","HARTĂ"};
    String[] icons={"▦","◈","➤"};
    int[] bx={13,142,277},bw={119,125,114};
    for(int i=0;i<3;i++){
      panel(c,bx[i],635,bw[i],76,0xff1b2a3b,9);
      centered(c,icons[i],bx[i]+bw[i]/2f,671,29,crimson,true);
      centered(c,shortcuts[i],bx[i]+bw[i]/2f,699,13,ice,true);
    }
  }
  private void compactDigitalFuelTrim(Canvas c,int x,int y,int w,int h,
                                      String name,float reading,int accent){
    panel(c,x,y,w,h,0xf0081421,16);
    stroke(c,x,y,w,h,accent,16);
    text(c,name,x+19,y+44,23,iceForFuelTrim(),true);
    String value=val(reading,1);
    text(c,value,x+19,y+118,52,iceForFuelTrim(),true);
    text(c,"%",x+w-33,y+116,19,accent,true);
    line(c,x+17,y+154,x+w-17,y+154,0xff344457,4);
    if(Float.isFinite(reading)){
      float ratio=clipped(reading,-25,25);
      line(c,x+17,y+154,x+17+(w-34)*ratio,y+154,accent,5);
    }
    text(c,Float.isFinite(reading)?"ECU • LIVE":"ECU • N/A",
      x+19,y+196,16,Float.isFinite(reading)?0xff70dbbd:0xffa8b6c8,true);
  }
  private int iceForFuelTrim(){return Color.WHITE;}

  void draw(Canvas c){
    int id=selected,accent=COLORS[id],style=STYLES[id];
    if(id==0){drawEvoDigitalDashNative(c);return;}
    drawArt(c,id);
    // Source mockups had baked numbers ("4. EVO DIGITAL DASH", "22:36").
    // Draw the real selected skin index and live time on top of those examples.
    panel(c,18,9,604,58,0xee07101c,11);
    stroke(c,18,9,604,58,accent,11);
    text(c,String.format(Locale.US,"%02d / 21",id+1),35,48,23,accent,true);
    text(c,shorten(NAMES[id],30),156,48,27,Color.WHITE,true);
    // Scrims replace baked/fake numbers and transport labels in source image.
    renderTime(c,accent,style);
    if(id==0)drawDigitalDashFastGauges(c,accent);
    renderMusic(c,accent,style);
    stats(c,accent,style);
    strip(c,accent);
    sideRail(c,accent);
    text(c,shorten(NAMES[id],30),410,700,18,Color.WHITE,true);
  }
  boolean touch(float x,float y){
    // The App Center and App Launcher backgrounds include decorative example
    // icons. Touching that area opens the REAL installed-app search drawer.
    if(selected==0&&x>100&&x<629&&y>220&&y<573){
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
    id=clamp(id);
    if(atlas!=null&&!atlas.isRecycled()){
      int w=atlas.getWidth()/3,h=atlas.getHeight()/7;
      return Bitmap.createBitmap(atlas,(id%3)*w,(id/3)*h,w,h);
    }
    // No absent-asset crash: render the actual live layout for preview.
    Bitmap fallback=Bitmap.createBitmap(320,180,Bitmap.Config.RGB_565);
    Canvas canvas=new Canvas(fallback);
    canvas.scale(.25f,.25f);
    int previous=selected;selected=id;
    try{draw(canvas);}finally{selected=previous;}
    return fallback;
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
                for(int i=0;i<COUNT;i++){
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
        for(int i=0;i<COUNT;i++)if(!seen[i])
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
    galleryDialog=new AlertDialog.Builder(host).setTitle("Skinuri EVO • 21 modele • primul EVO DIGITAL DASH")
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
      fullPreview=Bitmap.createBitmap(1280,720,Bitmap.Config.RGB_565);
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
    });
    dialog.show();
  }
}
