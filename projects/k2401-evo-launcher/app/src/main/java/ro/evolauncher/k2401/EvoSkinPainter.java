package ro.evolauncher.k2401;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.media.MediaMetadata;
import android.media.session.MediaController;
import android.media.session.PlaybackState;
import android.os.SystemClock;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Presents the ORIGINAL selected image pixel-for-pixel at 1280x720 and puts
 * active telemetry, clock and media controls on a separate interactive layer.
 * Backdrop illustrations are NEVER treated as ECU or media measurements.
 * Lightweight: one RGB_565 bitmap is cached; no animations or redraw loops.
 */
final class EvoSkinPainter {
  static final int W=1280,H=720;
  private static final int WHITE=0xffeff6fd,GREY=0xffa0b5c8;
  private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  private final EvoSkinStore store;

  EvoSkinPainter(EvoSkinStore skinStore){store=skinStore;}
  private void rect(Canvas c,float x,float y,float w,float h,int color,float corner){
    p.setStyle(Paint.Style.FILL);p.setShader(null);p.setColor(color);
    c.drawRoundRect(x,y,x+w,y+h,corner,corner,p);
  }
  private void text(Canvas c,String t,float x,float y,int size,int color,boolean bold){
    p.setShader(null);p.setStyle(Paint.Style.FILL);p.setColor(color);
    p.setTypeface(Typeface.create(bold?"sans-serif-medium":"sans-serif",
      bold?Typeface.BOLD:Typeface.NORMAL));
    p.setTextSize(size);p.setTextAlign(Paint.Align.LEFT);
    c.drawText(t,x,y,p);
  }
  private void centered(Canvas c,String t,float x,float y,int size,int color,boolean bold){
    p.setShader(null);p.setStyle(Paint.Style.FILL);p.setColor(color);
    p.setTypeface(Typeface.create("sans-serif-medium",bold?Typeface.BOLD:Typeface.NORMAL));
    p.setTextSize(size);p.setTextAlign(Paint.Align.CENTER);
    c.drawText(t,x,y,p);p.setTextAlign(Paint.Align.LEFT);
  }
  private void line(Canvas c,float x,float y,float x2,float y2,int color,float width){
    p.setShader(null);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(width);
    p.setStrokeCap(Paint.Cap.ROUND);p.setColor(color);
    c.drawLine(x,y,x2,y2,p);p.setStyle(Paint.Style.FILL);
  }
  private void panel(Canvas c,float x,float y,float w,float h,int border){
    rect(c,x,y,w,h,0xed08101b,14);
    p.setColor(border);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.6f);
    c.drawRoundRect(x,y,x+w,y+h,14,14,p);p.setStyle(Paint.Style.FILL);
  }
  private static String abbreviated(String s,int max){
    if(s==null||s.isEmpty())return "";
    return s.length()>max?s.substring(0,max-1)+"…":s;
  }
  private static String number(float val,int type){
    if(!Float.isFinite(val))return "N/A";
    if(type==0)return String.format(Locale.US,"%.0f",val);
    if(type==3)return String.format(Locale.US,"%.0f",val);
    return String.format(Locale.US,"%+.1f",val);
  }

  void draw(Canvas c,ObdReader.Reading live,MediaController media,
            String mediaName,boolean clock24){
    Bitmap bg=store.bitmap(store.current());
    if(bg!=null&&!bg.isRecycled()){
      p.setColor(Color.WHITE);p.setAlpha(255);p.setStyle(Paint.Style.FILL);
      c.drawBitmap(bg,null,new Rect(0,0,W,H),p);
      // The original AI-rendered demo content must not be mistaken for live
      // measurements; darken text behind the real signal layer.
      rect(c,0,0,W,H,0x2a000000,0);
    }else{
      p.setShader(new LinearGradient(0,0,W,H,0xff111c2d,0xff04080e,
        Shader.TileMode.CLAMP));
      c.drawRect(0,0,W,H,p);p.setShader(null);
      text(c,"IMPORTĂ IMAGINILE ORIGINALE",165,275,33,WHITE,true);
      text(c,"APLICAȚII → SKINURI → IMPORTĂ ZIP (21 IMAGINI)",165,321,22,GREY,false);
    }
    drawClock(c,clock24);
    drawControls(c);
    drawLiveGauges(c,live);
    drawMedia(c,media,mediaName);
    text(c,"SKIN  "+String.format(Locale.US,"%02d",store.current()+1)+
      "  •  "+store.currentName(),92,697,15,0xffe9b7bf,false);
  }
  private void drawClock(Canvas c,boolean clock24){
    // Replace the illustration's fictitious clock with the real head-unit time.
    rect(c,91,18,326,87,0xe6091420,13);
    String fmt=clock24?"HH:mm":"hh:mm a";
    String now=new SimpleDateFormat(fmt,Locale.getDefault()).format(new Date());
    String date=new SimpleDateFormat("EEEE, dd MMMM yyyy",new Locale("ro","RO")).format(new Date());
    text(c,now,109,70,52,WHITE,true);
    text(c,date,258,69,14,0xffc3d0e0,false);
  }
  private void drawControls(Canvas c){
    // These buttons ALWAYS exist on EVERY skin, even when the sample image
    // depicts no launcher controls. OEM hardware key handling is untouched.
    rect(c,8,142,78,493,0xe608101a,15);
    line(c,83,148,83,621,0xff832c40,2);
    String[] icons={"⌂","▦","♫","◉","⚙","✧"};
    String[] labels={"HOME","APPS","MEDIA","OBD","SET","SKIN"};
    for(int i=0;i<icons.length;i++){
      float y=166+i*77;
      rect(c,15,y,63,68,i==1?0xffad173b:0xff1c2835,9);
      centered(c,icons[i],46,y+32,24,WHITE,true);
      centered(c,labels[i],46,y+52,11,WHITE,true);
    }
  }
  private void drawLiveGauges(Canvas c,ObdReader.Reading data){
    // Two visual layouts, both overlaid on the actual photographed design.
    // Each PID is always mapped to its own ECU sample; N/A stays N/A.
    int style=store.current();
    boolean compact=style==0||style==2||style==5||style==6||
      style==7||style==10||style==13||style==14||style==16||
      style==18||style==19||style==20;
    float[] values={data.rpm,data.stft,data.ltft,data.coolantC};
    String[] names={"RPM","STFT B1","LTFT B1","TEMP APĂ"};
    String[] units={"rpm","%","%","°C"};
    int[] colors={0xffff3950,0xff3ccaf7,0xffffa938,0xff55dfbc};
    for(int i=0;i<4;i++){
      float x,y,w,h;
      if(compact){
        x=808+(i%2)*221;
        y=409+(i/2)*119;
        w=206;h=110;
      }else{
        x=134+i*277;
        y=559;
        w=261;h=116;
      }
      panel(c,x,y,w,h,colors[i]);
      float cy=y+51, cx=x+51;
      p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(5);
      p.setColor(0xff334054);c.drawArc(cx-31,cy-31,cx+31,cy+31,130,280,false,p);
      float value=values[i];
      if(Float.isFinite(value)){
        float ratio;
        if(i==0)ratio=Math.max(0,Math.min(1,value/8000f));
        else if(i==3)ratio=Math.max(0,Math.min(1,(value-40f)/80f));
        else ratio=Math.max(0,Math.min(1,(value+25f)/50f));
        p.setColor(colors[i]);c.drawArc(cx-31,cy-31,cx+31,cy+31,130,280*ratio,false,p);
      }
      p.setStyle(Paint.Style.FILL);
      text(c,names[i],x+92,y+30,16,colors[i],true);
      text(c,number(value,i),x+91,y+77,31,WHITE,true);
      text(c,units[i],x+w-42,y+98,13,GREY,false);
      // A missing PID draws no needle, no fabricated baseline.
      if(!Float.isFinite(value))text(c,"NO DATA",x+7,y+101,10,GREY,false);
      else text(c,i<2?"LIVE FAST":"LIVE SLOW",x+8,y+102,11,0xff72e0c2,true);
    }
  }
  private void drawMedia(Canvas c,MediaController player,String name){
    // This hides the AI mockup's fictitious track titles. It uses ONLY the
    // selected Android MediaSession, preserving the existing playback logic.
    float x=808,y=124,w=454,h=259;
    panel(c,x,y,w,h,0xffaa324c);
    text(c,"EVO MEDIA  •  "+abbreviated(name==null?"Alege playerul":name,22),
      x+23,y+33,18,WHITE,true);
    String title="",artist="";
    if(player!=null&&player.getMetadata()!=null){
      CharSequence track=player.getMetadata().getText(MediaMetadata.METADATA_KEY_TITLE);
      CharSequence author=player.getMetadata().getText(MediaMetadata.METADATA_KEY_ARTIST);
      title=track==null?"":track.toString();
      artist=author==null?"":author.toString();
    }
    if(title.isEmpty()){
      title="Fără sesiune media activă";
      artist="Atinge MEDIA pentru a alege playerul";
    }
    text(c,abbreviated(title,31),x+24,y+87,23,WHITE,true);
    text(c,abbreviated(artist,39),x+24,y+125,16,GREY,false);
    line(c,x+26,y+153,x+w-26,y+153,0xff576278,3);
    boolean playing=player!=null&&player.getPlaybackState()!=null&&
      player.getPlaybackState().getState()==PlaybackState.STATE_PLAYING;
    rect(c,x+43,y+183,106,61,0xff1d2b39,9);
    rect(c,x+177,y+183,107,61,0xffb82242,9);
    rect(c,x+313,y+183,106,61,0xff1d2b39,9);
    centered(c,"◀◀",x+96,y+225,27,WHITE,true);
    centered(c,playing?"Ⅱ":"▶",x+230,y+224,33,WHITE,true);
    centered(c,"▶▶",x+366,y+225,27,WHITE,true);
    text(c,player==null?"MediaSession indisponibilă":"MediaSession conectată",
      x+23,y+179,12,GREY,false);
  }
  /** Generic touch targets shared by all 21 designs. */
  int hit(float x,float y){
    if(x>=8&&x<=87&&y>=142&&y<=635){
      int index=(int)((y-166)/77);
      if(index>=0&&index<6)return 100+index;
    }
    if(x>=808&&x<=1262&&y>=124&&y<=383){
      if(y>=307&&y<=369){
        if(x<964)return 200; // previous
        if(x<1102)return 201; // play/pause
        return 202; // next
      }
      return 203; // player picker / media settings
    }
    if(x>=808&&x<=1262&&y>=409&&y<=655)return 300; // OBD details
    return -1;
  }
}
