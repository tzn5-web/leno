package ro.evolauncher.k2401;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
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
  private static final int[] STYLES={
    0,1,2,3,4,5, 1,0,3,1,4,2, 1,0,5,3,1,2,4,5,0
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
    try(InputStream stream=host.getAssets().open("skins/atlas.webp")){
      BitmapFactory.Options opts=new BitmapFactory.Options();
      opts.inPreferredConfig=Bitmap.Config.RGB_565;
      atlas=BitmapFactory.decodeStream(stream,null,opts);
    }catch(IOException|RuntimeException absent){
      // Preserve bootability: missing art never stops ECU/media/launcher.
      atlas=null;
    }
  }
  static int clamp(int id){return Math.max(0,Math.min(COUNT-1,id));}
  int selection(){return selected;}
  void select(int id){
    selected=clamp(id);
    prefs.edit().putInt(KEY,selected).commit();
    if(host.view!=null)host.view.invalidate();
    host.placeMap();
  }
  void release(){
    if(atlas!=null&&!atlas.isRecycled()){atlas.recycle();atlas=null;}
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
    panel(c,20,78,300,132,0xee09111d,15);
    stroke(c,20,78,300,132,accent,15);
    text(c,time(),37,144,59,Color.WHITE,true);
    text(c,shorten(date(),28),39,180,19,0xffd2ddeb,false);
    text(c,"MITSUBISHI • EVO",40,201,13,accent,true);
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
  private void gauge(Canvas c,float cx,float cy,int radius,String name,String value,
                     String unit,float reading,float from,float to,int accent,int style){
    if(style==4 || style==5){
      panel(c,cx-radius,cy-radius*.66f,2*radius,1.62f*radius,0xf1091320,10);
      stroke(c,cx-radius,cy-radius*.66f,2*radius,1.62f*radius,accent,10);
      text(c,name,cx-radius+12,cy-radius*.66f+26,16,0xffc4d4e3,true);
      text(c,value,cx-radius+12,cy+20,35,Color.WHITE,true);
      text(c,unit,cx+radius-34,cy+42,13,accent,false);
      float pct=Float.isFinite(reading)?Math.max(0,Math.min(1,(reading-from)/(to-from))):0f;
      panel(c,cx-radius+12,cy+radius*.81f,2*radius-24,5,0xff344153,2);
      if(Float.isFinite(reading))panel(c,cx-radius+12,cy+radius*.81f,(2*radius-24)*pct,5,accent,2);
      // Small live waterfall trace is a static decoration, not fabricated history.
      return;
    }
    colour(0xff09101b);c.drawCircle(cx,cy,radius+5,p);
    colour(0xff344152);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(8);
    c.drawArc(cx-radius,cy-radius,cx+radius,cy+radius,135,270,false,p);
    if(Float.isFinite(reading)){
      float fraction=Math.max(0,Math.min(1,(reading-from)/(to-from)));
      colour(accent);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(style==2?11:8);
      c.drawArc(cx-radius,cy-radius,cx+radius,cy+radius,135,270*fraction,false,p);
    }
    p.setStyle(Paint.Style.FILL);
    centered(c,value,cx,cy+13,radius>65?39:28,Color.WHITE,true);
    centered(c,name,cx,cy+radius+25,17,0xffe6edf4,true);
    centered(c,unit,cx,cy+radius+43,13,accent,false);
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
    if(style==0){ // Digital Dash: two primary rings + two trims.
      int rad=75;
      gauge(c,x+115,y+149,rad,names[0],val(vs[0],0),units[0],vs[0],lower[0],upper[0],accent,0);
      gauge(c,x+315,y+149,rad,names[1],val(vs[1],1),units[1],vs[1],lower[1],upper[1],0xff18c6ff,0);
      gauge(c,x+486,y+122,47,names[2],val(vs[2],1),units[2],vs[2],lower[2],upper[2],0xffed9545,0);
      gauge(c,x+486,y+240,47,names[3],val(vs[3],0),units[3],vs[3],lower[3],upper[3],0xffed5960,0);
    }else{
      int rad=style==4||style==5?67:57;
      for(int i=0;i<4;i++){
        float cx=x+84+i*(w-168)/3f,cy=y+(style==4||style==5?142:137);
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
  void draw(Canvas c){
    int id=selected,accent=COLORS[id],style=STYLES[id];
    drawArt(c,id);
    // Scrims replace baked/fake numbers and transport labels in source image.
    renderTime(c,accent,style);
    renderMusic(c,accent,style);
    stats(c,accent,style);
    strip(c,accent);
    text(c,shorten(NAMES[id],30),410,700,18,Color.WHITE,true);
  }
  boolean touch(float x,float y){
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
    Bitmap fallback=Bitmap.createBitmap(640,360,Bitmap.Config.RGB_565);
    Canvas canvas=new Canvas(fallback);
    canvas.scale(.5f,.5f);
    int previous=selected;selected=id;
    try{draw(canvas);}finally{selected=previous;}
    return fallback;
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
    new AlertDialog.Builder(host).setTitle("Skinuri EVO • 21 modele • primul EVO DIGITAL DASH")
      .setView(scroll).setNegativeButton("Închide",null).show();
  }
  private void previewDialog(int which){
    Bitmap image=preview(which);
    ImageView view=new ImageView(host);
    view.setImageBitmap(image);view.setScaleType(ImageView.ScaleType.FIT_CENTER);
    view.setAdjustViewBounds(true);
    view.setMinimumHeight(dp(250));
    new AlertDialog.Builder(host).setTitle((which+1)+". "+NAMES[which])
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
      .show();
  }
}
