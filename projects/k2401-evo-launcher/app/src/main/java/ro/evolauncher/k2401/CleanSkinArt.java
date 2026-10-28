package ro.evolauncher.k2401;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;

/**
 * Purely visual, non-interactive layer for 21 EVO theme backgrounds.
 *
 * The older image files are tiny upscaled AI mockups with baked-in false RPM,
 * weather, track titles, app icons, clocks and status labels. This layer draws
 * only a vehicle/scene crop from each image; all typography, UI, 4 PID data,
 * actual installed apps, Android media and touch controls are drawn by existing
 * native Android code. This class NEVER touches ELM327/Bluetooth/player logic.
 *
 * All geometry is authored in the real 1280x720 K2401 viewport. Canvas paths,
 * labels and dashboard arcs thus stay pin-sharp, independent of photo quality.
 */
final class CleanSkinArt {
  private static final int COUNT=21,W=1280,H=720;
  // Source ROIs selected per original image after an individual visual audit.
  // Exclude the source's low-res text/UI and retain the vehicle or skyline.
  private static final int[][] SRC={
    {350,465,544,685},   // 00 Digital Dash: car on motorway
    {305,65,770,333},    // 01 Classic: silver Evo
    {187,297,535,533},   // 02 Future: rear night city
    {125,75,619,377},    // 03 Gauge Pro: cutaway vehicle
    {325,55,797,352},    // 04 Multi Info: mountain road
    {0,0,0,0},           // 05 App Center: pure native UI
    {321,105,770,393},  // 06 Evolution Night: black Evo front
    {566,150,829,415},   // 07 GT Cockpit: rear and road
    {446,93,787,370},   // 08 Red Front: red garage
    {402,191,814,428},   // 09 Mountain
    {326,105,656,480},  // 10 Speed: vehicle top view
    {352,95,846,409},   // 11 Sunset
    {175,213,636,510},  // 12 Lancer Hero
    {225,378,507,557},  // 13 Digital Cockpit
    {0,0,0,0},           // 14 Tech Grid: pure native UI
    {585,252,826,458},  // 15 Gauge Focus
    {350,256,826,557},  // 16 Showroom
    {459,279,866,478},  // 17 Minimal Sport
    {168,164,724,592},  // 18 Car Status
    {0,0,0,0},           // 19 App Launcher: pure native UI
    {436,204,898,614}   // 20 Performance
  };
  // Scene windows are positioned away from real clock, gauges and media.
  // The scene must stay at its exact original K2401 coordinate, at 1:1 pixels.
  // Moving/enlarging the cut-outs introduces blur and changes approved compositions.
  private static final int[][] DEST=SRC;
  static int count(){return COUNT;}
  private static final int[] REDS={
    0xfffa314e,0xfff23848,0xff30cafe,0xfffa3853,0xff26c2e6,
    0xffed3053,0xfffa354f,0xfffd3952,0xfffb4255,0xff2accff,
    0xffed3953,0xfffc7254,0xfffb4056,0xff23cbff,0xfff23455,
    0xfff0405a,0xff37cafa,0xfff23d55,0xff30d9ec,0xffed3654,0xfff54055
  };
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  private void solid(int color){paint.reset();paint.setAntiAlias(true);paint.setFilterBitmap(true);paint.setColor(color);}
  private void round(Canvas c,float x,float y,float w,float h,int color,float radius){
    solid(color);c.drawRoundRect(x,y,x+w,y+h,radius,radius,paint);
  }
  private void stroke(Canvas c,float x,float y,float w,float h,int color,float radius,float width){
    solid(color);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(width);
    c.drawRoundRect(x,y,x+w,y+h,radius,radius,paint);paint.setStyle(Paint.Style.FILL);
  }
  private void line(Canvas c,float x,float y,float xx,float yy,int color,float width){
    solid(color);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeWidth(width);
    c.drawLine(x,y,xx,yy,paint);
  }
  private void label(Canvas c,String str,float x,float y,int size,int color){
    solid(color);
    paint.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
    paint.setTextSize(size);paint.setTextAlign(Paint.Align.CENTER);
    c.drawText(str,x,y,paint);paint.setTextAlign(Paint.Align.LEFT);
  }
  /**
   * High-resolution vector-only pictograms. Avoid fallback emoji fonts and
   * blurry baked-in image icons on Android 10 head units.
   */
  private void icon(Canvas c,int index,float x,float y,int color){
    solid(color);paint.setStrokeWidth(3.2f);paint.setStrokeCap(Paint.Cap.ROUND);
    paint.setStrokeJoin(Paint.Join.ROUND);paint.setStyle(Paint.Style.STROKE);
    if(index==0){ // Home
      Path roof=new Path();roof.moveTo(x-13,y-1);roof.lineTo(x,y-13);
      roof.lineTo(x+13,y-1);roof.moveTo(x-10,y-2);roof.lineTo(x-10,y+12);
      roof.lineTo(x+10,y+12);roof.lineTo(x+10,y-2);
      c.drawPath(roof,paint);
      c.drawLine(x-2,y+12,x-2,y+4,paint);c.drawLine(x+3,y+12,x+3,y+4,paint);
    }else if(index==1){ // Media note
      c.drawLine(x+2,y-12,x+2,y+6,paint);
      c.drawLine(x+2,y-12,x+14,y-15,paint);
      c.drawLine(x+14,y-15,x+14,y+3,paint);
      c.drawOval(x-8,y+4,x+3,y+12,paint);
      c.drawOval(x+4,y+1,x+15,y+9,paint);
    }else if(index==2){ // Navigation pointer
      Path pointer=new Path();pointer.moveTo(x,y-15);
      pointer.lineTo(x+13,y+14);pointer.lineTo(x,y+6);
      pointer.lineTo(x-12,y+13);pointer.close();c.drawPath(pointer,paint);
    }else if(index==3){ // ECU round gauge
      c.drawArc(x-13,y-13,x+13,y+13,145,251,false,paint);
      c.drawLine(x,y,x+8,y-8,paint);paint.setStyle(Paint.Style.FILL);
      c.drawCircle(x,y,3.2f,paint);paint.setStyle(Paint.Style.STROKE);
    }else if(index==4){ // Apps grid
      paint.setStyle(Paint.Style.FILL);
      for(int row=0;row<2;row++)for(int col=0;col<2;col++){
        float left=x-13+col*16,top=y-12+row*16;
        c.drawRoundRect(left,top,left+11,top+11,2,2,paint);
      }
    }else{ // Settings / mechanical gear
      c.drawCircle(x,y,10,paint);c.drawCircle(x,y,3,paint);
      for(int i=0;i<8;i++){
        double angle=i*Math.PI/4;
        c.drawLine(x+(float)Math.cos(angle)*11,y+(float)Math.sin(angle)*11,
          x+(float)Math.cos(angle)*16,y+(float)Math.sin(angle)*16,paint);
      }
    }
    paint.setStyle(Paint.Style.FILL);
  }

  /**
   * The entire bitmap is deliberately NEVER stretched onto the screen:
   * its font-sized artifacts were the root cause of unreadable fake values.
   * Photo details remain at approximately native source dimensions.
   */
  void draw(Canvas c,Bitmap source,int id){
    id=Math.max(0,Math.min(COUNT-1,id));
    final int tone=REDS[id],blue=0xff2bcffa;
    solid(0xff060d17);
    paint.setShader(new LinearGradient(0,0,1250,720,
      id%3==0?0xff101c2c:id%3==1?0xff111724:0xff07192c,
      0xff050a11,Shader.TileMode.CLAMP));
    c.drawRect(0,0,W,H,paint);paint.setShader(null);

    // The 21 user-approved composition sheets remain the exact base designs.
    // Prefer the optional reconstructed 2560x1440 asset. Both images are
    // mapped to the same 1280x720 design coordinates; do not stretch a crop.
    if(source!=null&&!source.isRecycled()){
      solid(Color.WHITE);
      paint.setFilterBitmap(true);
      c.drawBitmap(source,new Rect(0,0,source.getWidth(),source.getHeight()),
        new Rect(0,0,W,H),paint);
    }else{
      // Asset failure: neutral readable background, never a fake ECU snapshot.
      solid(0xff07121e);
      c.drawRect(0,0,W,H,paint);
    }

    // The artwork contains screenshot-only status times, navigation,
    // demo app shortcuts and footer labels. Erase them BEFORE native
    // SkinEngine/ThemeNativePanels repaint the real interactive controls.
    round(c,0,0,W,55,0xff08121e,0);
    round(c,0,54,96,666,0xf508111d,0);
    round(c,0,625,W,95,0xf408111d,0);
    line(c,96,55,96,625,(tone&0x00ffffff)|0x52000000,1);

    // Exactly one native pictogram for each of six existing touch actions.
    // No duplicate wallpaper glyphs, unused labels or permanently lit Apps.
    final int[] railY={233,294,355,416,477,538};
    for(int i=0;i<railY.length;i++){
      int y=railY[i];
      round(c,11,y,70,54,i==0?0xff422335:0xff152331,8);
      if(i==0)stroke(c,11,y,70,54,tone,8,2);
      icon(c,i,46,y+27,i==0?tone:0xffeaf4fd);
    }
    // The HUD marker is art, not fake "connected" telemetry.
    line(c,105,60,1270,60,(tone&0x00ffffff)|0x88000000,1);
    line(c,95,720-16,1270,720-16,0x3337b9da,1);
  }
}
