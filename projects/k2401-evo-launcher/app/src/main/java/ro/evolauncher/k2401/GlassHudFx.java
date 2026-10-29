package ro.evolauncher.k2401;

import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;

/**
 * Transparent, resolution-independent silver/graphite/red HUD primitives.
 * This class draws ONLY decoration. All measurements, text, music and actions
 * remain live in their existing owners. No fake readings or hit targets.
 * Coordinates are the app's native 1280x720 logical Canvas, scaled by Dashboard.
 */
final class GlassHudFx {
  static final int WHITE=0xfff3f0ed, SILVER=0xffb7bec6, RED=0xffd9414b;
  private static final int CHARCOAL=0xff080a0e;
  private static final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  private GlassHudFx(){}
  private static void reset(int color){
    p.reset();p.setAntiAlias(true);p.setFilterBitmap(true);
    p.setColor(color);p.setStyle(Paint.Style.FILL);
  }
  private static void stroke(Canvas c,float x,float y,float xx,float yy,int color,float width){
    reset(color);p.setStrokeWidth(width);p.setStrokeCap(Paint.Cap.ROUND);
    c.drawLine(x,y,xx,yy,p);
  }
  static void backdrop(Canvas c,int variant){
    reset(CHARCOAL);
    p.setShader(new LinearGradient(0,0,0,720,
      new int[]{0xff07090d,0xff11151c,0xff07080b},
      new float[]{0f,.55f,1f},Shader.TileMode.CLAMP));
    c.drawRect(0,0,1280,720,p);p.setShader(null);
    // Directional, deliberately subdued depth lighting (never a blue scene).
    reset(WHITE);
    p.setShader(new RadialGradient(640,410,590,
      new int[]{0x2a9a3942,0x107a2933,0x00000000},
      new float[]{0f,.54f,1f},Shader.TileMode.CLAMP));
    c.drawRect(0,0,1280,720,p);p.setShader(null);
    // Carbon weave, drawn as real vectors; scales cleanly to 3840x2160.
    for(int y=115;y<690;y+=11){
      for(int x=0;x<1280;x+=23){
        stroke(c,x,y,x+8,y+3,0x0cdae0e8,.65f);
      }
    }
    // Two perspective metallic rails provide 3D depth without fake scenery.
    for(int side=0;side<2;side++){
      c.save();
      if(side==1){c.translate(1280,0);c.scale(-1,1);}
      stroke(c,0,140,83,181,0x8baeb7c0,2.6f);
      stroke(c,0,152,90,194,0x4ad9414b,2.1f);
      stroke(c,0,575,126,523,0x8baeb7c0,2.4f);
      stroke(c,0,586,133,532,0x53d9414b,1.8f);
      stroke(c,0,647,195,581,0x5ebfc6ce,1.3f);
      stroke(c,0,656,200,590,0x36d9414b,1.3f);
      c.restore();
    }
    stroke(c,0,108,1280,108,0x64c6cbd1,1.1f);
    stroke(c,400,112,880,112,0x6bd9414b,1.6f);
    stroke(c,188,707,1092,707,0x3baeb5be,1f);
    if(variant==27){
      // Recessed glass pedestal for the holographic projection, no mock map.
      glassPanel(c,424,194,432,304,18);
      projection(c);
    }
  }
  static void glassPanel(Canvas c,float x,float y,float w,float h,float radius){
    reset(WHITE);
    p.setShader(new LinearGradient(x,y,x+w*.38f,y+h,
      new int[]{0xc514181e,0x9c1c232b,0xb0080b10},
      new float[]{0f,.45f,1f},Shader.TileMode.CLAMP));
    c.drawRoundRect(x,y,x+w,y+h,radius,radius,p);p.setShader(null);
    reset(0x98b9c0c9);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.5f);
    c.drawRoundRect(x+.8f,y+.8f,x+w-.8f,y+h-.8f,radius,radius,p);
    reset(0x3ff2f0ec);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(.8f);
    c.drawRoundRect(x+4,y+4,x+w-4,y+h-4,Math.max(2,radius-4),
      Math.max(2,radius-4),p);
    // Separate red corner glints are optical trim, not buttons.
    stroke(c,x+radius,y+1,x+Math.min(w*.27f,115),y+1,0x8de24d54,1.5f);
    stroke(c,x+w-Math.min(w*.18f,65),y+h-1,x+w-radius,y+h-1,0x60e24d54,1.2f);
  }
  static void dial(Canvas c,float cx,float cy,float radius,float value,
                   float min,float max){
    reset(WHITE);
    p.setShader(new RadialGradient(cx,cy,radius,
      new int[]{0xb0080b11,0x9510151c,0x50070a0f},
      new float[]{0f,.67f,1f},Shader.TileMode.CLAMP));
    c.drawCircle(cx,cy,radius-8,p);p.setShader(null);
    reset(SILVER);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(radius>100?5.5f:3.5f);
    p.setShader(new LinearGradient(cx-radius,cy-radius,cx+radius,cy+radius,
      new int[]{0xfff1f2f3,0xff5e6873,0xffd8dce1,0xff58616b,0xfff0f0f0},
      null,Shader.TileMode.CLAMP));
    c.drawCircle(cx,cy,radius-2,p);p.setShader(null);
    reset(0x7c929ba6);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.1f);
    c.drawCircle(cx,cy,radius-15,p);
    reset(0x55343c46);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(radius>100?10:6);
    c.drawArc(cx-radius+22,cy-radius+22,cx+radius-22,cy+radius-22,
      135,270,false,p);
    if(Float.isFinite(value)&&max>min){
      float f=Math.max(0f,Math.min(1f,(value-min)/(max-min)));
      reset(0xffdc3d49);p.setStyle(Paint.Style.STROKE);
      p.setStrokeCap(Paint.Cap.ROUND);p.setStrokeWidth(radius>100?8.5f:5.5f);
      c.drawArc(cx-radius+22,cy-radius+22,cx+radius-22,cy+radius-22,
        135,270f*f,false,p);
      // A real needle appears ONLY when a finite OBD value exists.
      double angle=Math.toRadians(135+270*f);
      float len=radius-38;
      stroke(c,cx,cy,cx+(float)Math.cos(angle)*len,
        cy+(float)Math.sin(angle)*len,0xa5e04a54,radius>100?2.1f:1.2f);
      reset(0xffd8dce0);c.drawCircle(cx,cy,radius>100?3.8f:2.5f,p);
    }
    for(int i=0;i<=36;i++){
      double angle=Math.toRadians(135+i*270d/36d);
      float outer=radius-22,inner=outer-(i%6==0?15:7);
      stroke(c,cx+(float)Math.cos(angle)*inner,cy+(float)Math.sin(angle)*inner,
        cx+(float)Math.cos(angle)*outer,cy+(float)Math.sin(angle)*outer,
        i%6==0?0xc8e0e1e3:0x668e99a5,i%6==0?2.1f:1.0f);
    }
  }
  static void projection(Canvas c){
    // Purely abstract metallic vehicle-inspired wireframe; no fictional data,
    // baked lettering, navigation map, or duplicate app controls.
    Path outline=new Path();
    outline.moveTo(490,378);outline.lineTo(508,345);outline.lineTo(547,334);
    outline.lineTo(571,305);outline.lineTo(612,290);outline.lineTo(668,290);
    outline.lineTo(709,305);outline.lineTo(734,334);outline.lineTo(773,345);
    outline.lineTo(790,378);outline.lineTo(776,407);outline.lineTo(504,407);
    outline.close();
    reset(0x22272c33);c.drawPath(outline,p);
    reset(0x9bb7c0c8);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2f);
    c.drawPath(outline,p);
    stroke(c,571,305,709,305,0x9bc5cbd1,1.7f);
    stroke(c,547,334,734,334,0x80c5cbd1,1.3f);
    stroke(c,507,375,773,375,0x7fd9414b,2.5f);
    stroke(c,523,399,758,399,0x83b9bec5,1.7f);
    stroke(c,520,383,550,383,0x9bda4b56,4f);
    stroke(c,730,383,760,383,0x9bda4b56,4f);
    stroke(c,640,270,640,429,0x27d7dbe0,1f);
    stroke(c,469,420,811,420,0x45a9b4bf,1f);
  }
}
