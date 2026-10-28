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
    {441,203,679,446},   // 02 Future: rear night city
    {125,75,619,377},    // 03 Gauge Pro: cutaway vehicle
    {325,55,797,352},    // 04 Multi Info: mountain road
    {0,0,0,0},           // 05 App Center: pure native UI
    {321,105,770,393},  // 06 Evolution Night: black Evo front
    {465,47,820,420},   // 07 GT Cockpit: rear and road
    {446,91,802,442},   // 08 Red Front: red garage
    {337,95,813,426},   // 09 Mountain
    {326,105,656,480},  // 10 Speed: vehicle top view
    {352,95,846,409},   // 11 Sunset
    {175,213,636,510},  // 12 Lancer Hero
    {372,287,756,558},  // 13 Digital Cockpit
    {0,0,0,0},           // 14 Tech Grid: pure native UI
    {418,356,788,557},  // 15 Gauge Focus
    {350,256,826,557},  // 16 Showroom
    {427,107,880,446},  // 17 Minimal Sport
    {168,164,724,592},  // 18 Car Status
    {0,0,0,0},           // 19 App Launcher: pure native UI
    {436,204,898,614}   // 20 Performance
  };
  // Scene windows are positioned away from real clock, gauges and media.
  private static final int[][] DEST={
    {346,460,589,679},
    {326,110,773,414},
    {426,215,745,491},
    {161,105,653,418},
    {356,75,842,430},
    {0,0,0,0},
    {341,95,794,452},
    {451,111,810,478},
    {451,93,822,473},
    {347,94,849,438},
    {348,80,669,485},
    {365,94,861,433},
    {169,215,671,545},
    {425,290,823,563},
    {0,0,0,0},
    {430,343,808,567},
    {350,254,831,569},
    {435,121,901,464},
    {158,165,729,618},
    {0,0,0,0},
    {429,207,910,630}
  };
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

    // Original, native-resolution geometric/carbon background.
    int soft=(tone&0x00ffffff)|0x12000000;
    solid(soft);paint.setStrokeWidth(1f);
    for(int x=-720;x<1580;x+=25)c.drawLine(x,0,x+720,720,paint);
    for(int y=90;y<690;y+=76){
      line(c,95,y,1270,y,0x18315a76,1);
    }
    // A background glow/road-lines pattern that remains sharp at 1280x720.
    solid(0x1c173f61);
    c.drawCircle(id%3==1?660:420,490,325,paint);
    solid((tone&0x00ffffff)|0x16000000);
    c.drawCircle(1100,80,300,paint);
    for(int k=0;k<7;k++){
      float y=180+k*54;
      line(c,110,y,755-(k%3)*48,y-20,0x23415d83,2);
    }

    // Vehicle scene window: source ROI excludes old mockup text,
    // MediaSession album art, falsely drawn app icons and other sensor values.
    final int[] src=SRC[id],dest=DEST[id];
    if(source!=null&&!source.isRecycled()&&src[2]>src[0]&&dest[2]>dest[0]){
      int left=Math.min(source.getWidth()-1,Math.max(0,src[0]));
      int top=Math.min(source.getHeight()-1,Math.max(0,src[1]));
      int right=Math.max(left+1,Math.min(source.getWidth(),src[2]));
      int bottom=Math.max(top+1,Math.min(source.getHeight(),src[3]));
      int dx=dest[0],dy=dest[1],dw=dest[2]-dx,dh=dest[3]-dy;
      round(c,dx-7,dy-7,dw+14,dh+14,0xaa111b2a,20);
      stroke(c,dx-8,dy-8,dw+16,dh+16,(tone&0x00ffffff)|0x77000000,21,1.5f);
      c.save();
      Path clip=new Path();clip.addRoundRect(new RectF(dx,dy,dx+dw,dy+dh),14,14,Path.Direction.CW);
      c.clipPath(clip);
      solid(Color.WHITE);paint.setFilterBitmap(true);
      c.drawBitmap(source,new Rect(left,top,right,bottom),
        new Rect(dx,dy,dx+dw,dy+dh),paint);
      // High-contrast vehicle cinematography with no baked-in sensor labels.
      solid(0x23010a16);c.drawRect(dx,dy,dx+dw,dy+dh,paint);
      c.restore();
    }else{
      // App-based concepts intentionally contain no invented app logos.
      // The real installed-app grid is rendered by ThemeNativePanels.
      round(c,112,114,624,454,0x98121f30,18);
      stroke(c,112,114,624,454,(tone&0x00ffffff)|0x7a000000,18,2);
      for(int i=0;i<7;i++){
        int x=145+(i%4)*142,y=210+(i/4)*147;
        round(c,x,y,100,93,0x6617293b,12);
        stroke(c,x,y,100,93,0x433b7294,12,1);
      }
    }

    // Vector-only navigation rail. No resized screenshots or baked-in text.
    round(c,4,219,85,399,0xf208111d,12);
    stroke(c,4,219,85,399,(tone&0x00ffffff)|0x66000000,12,1);
    final String[] icon={"⌂","♫","➤","◉","▦","⚙"};
    final String[] name={"HOME","MEDIA","HARTĂ","OBD","APPS","SET"};
    for(int i=0;i<6;i++){
      int y=233+i*61;
      round(c,11,y,70,54,i==4?0xff62263c:0xff152331,8);
      if(i==4)stroke(c,11,y,70,54,tone,8,2);
      label(c,icon[i],46,y+30,25,i==4?tone:0xffeaf4fd);
      label(c,name[i],46,y+47,10,0xffd6e6f6);
    }
    // The HUD marker is art, not fake "connected" telemetry.
    line(c,105,60,1270,60,(tone&0x00ffffff)|0x88000000,1);
    line(c,95,720-16,1270,720-16,0x3337b9da,1);
  }
}
