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
    // Layered, faint red holographic lens halos behind the live dials.
    // These are lighting, never synthetic telemetry or opaque gauge plates.
    for(int side=0;side<2;side++){
      float gx=side==0?215:1065;
      reset(WHITE);
      p.setShader(new RadialGradient(gx,367,265,
        new int[]{0x2ad74650,0x126c202a,0x00000000},
        new float[]{0f,.55f,1f},Shader.TileMode.CLAMP));
      c.drawCircle(gx,367,265,p);p.setShader(null);
    }
    // Perspective floor lattice: subtle parallax/depth without a fake map.
    for(int i=-7;i<=7;i++){
      stroke(c,640,459,640+i*93,706,
        i%2==0?0x35c4c9ce:0x28d9414b,1.1f);
    }
    for(int row=0;row<6;row++){
      float t=(row+1)/6f;
      float y=460+235*t*t;
      float half=80+560*t;
      stroke(c,640-half,y,640+half,y,
        row%2==0?0x3bc2c7ce:0x2cd9414b,1.0f+1.2f*t);
    }
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
    if(variant==21||variant==27){
      // Recessed 3D glass pedestal on the two dedicated holographic themes.
      // No mock map or fake ECU values are rendered.
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
    // Fixed optical highlights on the OUTER metallic bezel are decoration,
    // not invented ECU progress. They never intersect the live tick ring.
    reset(0x8cdb4854);p.setStyle(Paint.Style.STROKE);
    p.setStrokeCap(Paint.Cap.ROUND);
    p.setStrokeWidth(radius>100?5.5f:3.4f);
    c.drawArc(cx-radius+5,cy-radius+5,cx+radius-5,cy+radius-5,
      307,38,false,p);
    reset(0x9adce2e8);p.setStyle(Paint.Style.STROKE);
    p.setStrokeCap(Paint.Cap.ROUND);
    p.setStrokeWidth(radius>100?4f:2.5f);
    c.drawArc(cx-radius+5,cy-radius+5,cx+radius-5,cy+radius-5,
      127,53,false,p);
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
    // Original, layered 3D holographic vehicle sculpture: actual transparent
    // surfaces, roof perspective, wheel volumes, specular metal and floor
    // reflection. Pure decoration, never fake ECU/door/AC readings.
    reset(WHITE);
    p.setShader(new RadialGradient(640,411,206,
      new int[]{0x37d9414b,0x13d4d9df,0x00000000},
      new float[]{0f,.52f,1f},Shader.TileMode.CLAMP));
    c.drawOval(454,378,826,472,p);p.setShader(null);
    for(int i=-5;i<=5;i++){
      stroke(c,640,410,640+i*35,476,0x38b8c1cb,1.0f);
    }
    for(int i=0;i<4;i++){
      float y=420+i*i*5.2f;
      stroke(c,470+i*6,y,810-i*6,y,
        i%2==0?0x58c7cdd4:0x45d9414b,1.1f);
    }
    // Body: translucent metallic 3D volume, not a flat outline.
    Path body=new Path();
    body.moveTo(495,367);body.lineTo(510,337);body.lineTo(548,328);
    body.lineTo(570,303);body.lineTo(596,285);body.lineTo(684,285);
    body.lineTo(710,303);body.lineTo(732,328);body.lineTo(770,337);
    body.lineTo(785,367);body.lineTo(776,408);body.lineTo(504,408);
    body.close();
    reset(WHITE);
    p.setShader(new LinearGradient(495,292,785,414,
      new int[]{0x9c303943,0x85202831,0xa50a0d12,0x6b454e58},
      new float[]{0f,.3f,.7f,1f},Shader.TileMode.CLAMP));
    c.drawPath(body,p);p.setShader(null);
    reset(0x8ae3e7eb);p.setStyle(Paint.Style.STROKE);
    p.setStrokeWidth(2.3f);c.drawPath(body,p);
    // Roof and glazing float above the rear deck in real perspective.
    Path roof=new Path();
    roof.moveTo(574,305);roof.lineTo(604,289);roof.lineTo(676,289);
    roof.lineTo(706,305);roof.lineTo(722,334);roof.lineTo(558,334);
    roof.close();
    reset(WHITE);
    p.setShader(new LinearGradient(568,290,711,340,
      new int[]{0x687b8997,0x4c222c36,0x9a0b1118},
      new float[]{0f,.42f,1f},Shader.TileMode.CLAMP));
    c.drawPath(roof,p);p.setShader(null);
    reset(0xb6d5dce2);p.setStyle(Paint.Style.STROKE);
    p.setStrokeWidth(1.8f);c.drawPath(roof,p);
    stroke(c,640,291,640,332,0x5ccbd2d9,1.0f);
    stroke(c,560,336,721,336,0x82c6cbd1,1.5f);
    // Angled side panels make the vehicle read as a floating 3D volume.
    Path left=new Path();
    left.moveTo(510,337);left.lineTo(548,329);left.lineTo(558,335);
    left.lineTo(544,386);left.lineTo(502,397);left.close();
    reset(0x65717c87);c.drawPath(left,p);
    Path right=new Path();
    right.moveTo(770,337);right.lineTo(732,329);right.lineTo(722,335);
    right.lineTo(736,386);right.lineTo(778,397);right.close();
    reset(0x50545e69);c.drawPath(right,p);
    stroke(c,548,329,544,386,0x8bdae0e5,1.5f);
    stroke(c,732,329,736,386,0x8bdae0e5,1.5f);
    // Realistic wheel recesses and metallic rims (no fabricated readings).
    for(int wheel=0;wheel<2;wheel++){
      float x=wheel==0?535:745;
      reset(0xc1080a0e);c.drawOval(x-22,382,x+22,424,p);
      reset(0xa9c8cfd6);p.setStyle(Paint.Style.STROKE);
      p.setStrokeWidth(2.0f);c.drawOval(x-17,386,x+17,418,p);
      reset(0x6c727e89);c.drawCircle(x,402,5,p);
    }
    // Three-stage rear deck and active-looking but DECORATIVE taillights.
    stroke(c,546,361,734,361,0x8be6eaee,1.6f);
    stroke(c,515,387,765,387,0x95b9c3cc,1.5f);
    stroke(c,531,405,749,405,0x88dce1e6,2f);
    stroke(c,554,397,726,397,0x70d9414b,2.2f);
    for(int side=0;side<2;side++){
      float x=side==0?525:755;
      stroke(c,x-18,376,x+18,376,0x4bd9414b,9f);
      stroke(c,x-18,376,x+18,376,0xe4f25a63,3.7f);
    }
    // Double specular highlights and a restrained red underglow.
    stroke(c,506,351,550,339,0x8de9edf1,1.3f);
    stroke(c,730,339,774,351,0x8de9edf1,1.3f);
    stroke(c,521,415,759,415,0x79d9414b,1.7f);
    stroke(c,492,432,788,432,0x43e1e5e9,1.1f);
    for(int i=0;i<5;i++){
      float y=439+i*6;
      stroke(c,540+i*13,y,740-i*13,y,0x22d9414b,1.0f);
    }
    // Vertical holographic registration beams stay inside the central panel.
    stroke(c,473,279,473,430,0x2bcdd3da,1f);
    stroke(c,807,279,807,430,0x2bcdd3da,1f);
    stroke(c,640,265,640,437,0x23e1e4e8,1f);
  }}
