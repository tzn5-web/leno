package ro.evolauncher.k2401;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
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
  private static final int BLUE=0xffd94751, ICE=0xffd8dce0, WHITE=0xfff4f0ee;
  private static final int DARK=0xff080a0e, LT=0xffaeb6bf;
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
    GlassHudFx.glassPanel(c,x,y,w,h,radius);
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
    GlassHudFx.backdrop(c,id);
    Bitmap im=scenes[i];
    if(im!=null&&!im.isRecycled()){
      // Preserve original 4K assets but remove the harsh cyan/blue dominance.
      // Art remains behind real live Canvas HUD controls, never their source.
      ColorMatrix desaturated=new ColorMatrix();
      desaturated.setSaturation(.08f);
      color(Color.WHITE);p.setFilterBitmap(true);p.setAlpha(112);
      p.setColorFilter(new ColorMatrixColorFilter(desaturated));
      c.drawBitmap(im,null,new Rect(0,0,1280,720),p);
      p.setColorFilter(null);p.setAlpha(255);
    }
    // Scene art is CLEAN: it contains no pre-painted music/date/gauges/apps.
    // Earlier versions incorrectly overpainted solid black 146px TOP and
    // 166px BOTTOM bands, hiding almost HALF of the approved cinematic scene.
    // Preserve a continuous photographic field beneath the opaque native cards.
    // Soft scene scrims improve readability without erasing the 4K environment.
    color(Color.WHITE);
    p.setShader(new LinearGradient(0,0,0,160,
      new int[]{0xe8080a0e,0x98080a0e,0x00080a0e},
      new float[]{0f,.52f,1f},Shader.TileMode.CLAMP));
    c.drawRect(0,0,1280,160,p);p.setShader(null);
    color(Color.WHITE);
    p.setShader(new LinearGradient(0,520,0,720,
      new int[]{0x00080a0e,0x98080a0e,0xe8080a0e},
      new float[]{0f,.53f,1f},Shader.TileMode.CLAMP));
    c.drawRect(0,520,1280,720,p);p.setShader(null);
    color(0x3809090c);c.drawRect(0,130,18,610,p);
    color(0x3809090c);c.drawRect(1262,130,1280,610,p);
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
  // Four fixed controls beside the native media panel, with explicit hitboxes.
  // Each control navigates to an EXISTING functional page. No rendered or
  // baked art labels: their glyphs and captions are native and scalable.
  private static final int QUICK_X=13, QUICK_Y=18, QUICK_W=56, QUICK_GAP=6, QUICK_H=76;
  private static final int[] QUICK_ICON={5,4,2,1};
  private static final String[] QUICK_TEXT={"SETUP","APPS","NAVI","MUZICĂ"};
  private void quickNavigation(Canvas c,int edge){
    for(int i=0;i<4;i++){
      int x=QUICK_X+i*(QUICK_W+QUICK_GAP);
      panel(c,x,QUICK_Y,QUICK_W,QUICK_H,9,0xff081725,edge);
      NavVectorIcons.draw(c,QUICK_ICON[i],x+28,QUICK_Y+28,BLUE);
      text(c,QUICK_TEXT[i],x+28,QUICK_Y+64,i==3?10:11,WHITE,true,true);
    }
  }
  private boolean quickNavigationTouch(float x,float y){
    if(y<QUICK_Y||y>QUICK_Y+QUICK_H)return false;
    for(int i=0;i<4;i++){
      int left=QUICK_X+i*(QUICK_W+QUICK_GAP);
      if(x>=left&&x<=left+QUICK_W){
        if(i==1){host.showInstalledApps();return true;}
        int destination=i==0?5:i==2?2:1;
        host.page=destination;
        if(host.view!=null)host.view.invalidate();
        host.placeMap();
        return true;
      }
    }
    return false;
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
      panel(c,272,21,62,62,9,0x8813171e,line);
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
    color(0x66535b64);c.drawRoundRect(x+w/2f-28,y+150,x+w/2f+28,y+h-25,6,6,p);
    if(Float.isFinite(fraction)){
      int bottom=y+h-27;
      int top=y+152;
      int filled=(int)((bottom-top)*cap(fraction));
      color(edge);
      c.drawRoundRect(x+w/2f-27,bottom-filled,x+w/2f+27,bottom,5,5,p);
    }
    for(int t=0;t<=6;t++){
      int yy=y+153+(h-180)*t/6;
      color(0xff9fa9b4);c.drawRect(x+w/2f+35,yy,x+w/2f+46,yy+2,p);
    }
  }
  private void boxGauge(Canvas c,int x,int y,int w,int h,String label,String value,
                        String unit,int edge){
    panel(c,x,y,w,h,11,0xa010141b,edge);
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
    // The only illuminated arc represents a finite live ECU reading.
    float live=Float.isFinite(fraction)?fraction:Float.NaN;
    GlassHudFx.dial(c,cx,cy,r,live,0f,1f);
    text(c,key,cx,cy-46,19,ICE,true,true);
    text(c,value,cx,cy+18,53,WHITE,true,true);
    text(c,unit,cx,cy+52,17,LT,false,true);
  }
  // Approved A1 and 02 have semi-circular fuel-trim gauges at the foot of
  // the car, NOT two additional vertical pods or full-size dials.
  private void halfGauge(Canvas c,float cx,float cy,float radius,String label,
                         String value,float fraction,int edge){
    color(0x9b10151c);
    c.drawRoundRect(cx-radius,cy-radius*.80f,cx+radius,cy+radius*.69f,20,20,p);
    color(0x997e8995);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(8);
    c.drawArc(cx-radius,cy-radius,cx+radius,cy+radius,181,178,false,p);
    if(Float.isFinite(fraction)){
      color(edge);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(9);
      c.drawArc(cx-radius,cy-radius,cx+radius,cy+radius,
        181,178*cap(fraction),false,p);
    }
    p.setStyle(Paint.Style.FILL);
    text(c,label,cx,cy-15,16,ICE,true,true);
    text(c,value,cx,cy+23,35,WHITE,true,true);
    text(c,"%",cx,cy+43,15,LT,false,true);
    text(c,"-25",cx-radius+10,cy+51,12,LT,false,false);
    text(c,"+25",cx+radius-24,cy+51,12,LT,false,false);
  }
  // Polygonal metal bezel fits the approved A3 side dial profile. It is
  // entirely vector drawn; only actual OBD readings appear in the interior.
  private void framedCircle(Canvas c,float x,float y,float radius,
                            String key,String value,String unit,float fraction,int edge){
    color(0xffb7c0ca);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2.5f);
    Path shape=new Path();
    for(int i=0;i<8;i++){
      double a=Math.PI*2*(i/8.0)-Math.PI/8;
      float px=x+(radius+10)*(float)Math.cos(a);
      float py=y+(radius+10)*(float)Math.sin(a);
      if(i==0)shape.moveTo(px,py);else shape.lineTo(px,py);
    }
    shape.close();c.drawPath(shape,p);p.setStyle(Paint.Style.FILL);
    circle(c,x,y,radius,key,value,unit,fraction,edge);
  }
  void draw(Canvas c,int id){
    if(id<FIRST||id>LAST)return;
    int line=id==24?0xffc7cbd0:0xffd94751;
    background(c,id);
    if(id==22){
      // A1 (cyber-tunnel): TWO towering side columns; STFT and LTFT are
      // smaller half-moon gauges BELOW the centre car. The source screenshot
      // never becomes a fake data layer.
      ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
      vertical(c,27,162,160,427,"RPM",
        Float.isFinite(r.rpm)?String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A",
        "x1000 rpm",r.rpm/8000f,line,0xff071b2f);
      vertical(c,1093,162,160,427,"TEMP APĂ",degrees(r.coolantC),
        "",(r.coolantC-40)/90f,0xffadb8c4,0xff071b2f);
      halfGauge(c,418,520,90,"STFT",labelValue(r.stft,true),
        (r.stft+25f)/50f,0xffd94751);
      halfGauge(c,862,520,90,"LTFT",labelValue(r.ltft,true),
        (r.ltft+25f)/50f,0xffadb8c4);
    }else if(id==23){
      // 02: premium mountain hologram: two LARGE outer round dials and two
      // SMALL half arcs across the bottom. Car remains clear in the middle.
      ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
      circle(c,155,382,148,"RPM",Float.isFinite(r.rpm)?
        String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A","x1000 rpm",
        r.rpm/8000f,line);
      circle(c,1125,382,148,"TEMP APĂ",degrees(r.coolantC),"",
        (r.coolantC-40f)/90f,0xffadb8c4);
      halfGauge(c,527,516,85,"STFT",labelValue(r.stft,true),
        (r.stft+25f)/50f,0xffd94751);
      halfGauge(c,753,516,85,"LTFT",labelValue(r.ltft,true),
        (r.ltft+25f)/50f,0xffadb8c4);
    }else{
      // A3: FOUR round hexagonal native dials around the luminous showroom:
      // RPM/STFT on left, coolant/LTFT on right. No rectangular text-only
      // placeholders and no oil/boost/voltage invented indicators.
      ObdReader.Reading r=host.obd==null?ObdReader.Reading.empty():host.obd.current();
      framedCircle(c,160,258,124,"RPM",Float.isFinite(r.rpm)?
        String.format(Locale.US,"%.1f",r.rpm/1000f):"N/A",
        "x1000 rpm",r.rpm/8000f,line);
      framedCircle(c,160,470,86,"STFT",labelValue(r.stft,true),
        "%",(r.stft+25f)/50f,0xffd94751);
      framedCircle(c,1120,258,124,"TEMP APĂ",degrees(r.coolantC),"",
        (r.coolantC-40f)/90f,0xffadb8c4);
      framedCircle(c,1120,470,86,"LTFT",labelValue(r.ltft,true),
        "%",(r.ltft+25f)/50f,0xffadb8c4);
    }
    music(c,line);
    bar(c,id,line);
    quickNavigation(c,line);
    // Exactly six live application shortcuts. All are click/hold-driven and
    // persisted under the original same app's SharedPreferences.
    personalApps.drawUserSlots(c);
  }
  boolean touch(float x,float y){
    if(quickNavigationTouch(x,y))return true;
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
