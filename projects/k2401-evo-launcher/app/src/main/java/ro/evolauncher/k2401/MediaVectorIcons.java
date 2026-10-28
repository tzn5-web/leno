package ro.evolauncher.k2401;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;

/** Native antialiased 1280x720 transport artwork; no OEM font fallbacks. */
final class MediaVectorIcons {
  private MediaVectorIcons(){}
  static void draw(Canvas c,float cx,float cy,int action,int tint){
    Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
    p.setStyle(Paint.Style.FILL);
    p.setColor(tint);
    if(action==3){ // Pause
      c.drawRoundRect(cx-10,cy-14,cx-3,cy+14,2,2,p);
      c.drawRoundRect(cx+3,cy-14,cx+10,cy+14,2,2,p);
      return;
    }
    if(action==1){ // Play
      Path triangle=new Path();
      triangle.moveTo(cx-10,cy-15);
      triangle.lineTo(cx+15,cy);
      triangle.lineTo(cx-10,cy+15);
      triangle.close();
      c.drawPath(triangle,p);
      return;
    }
    // Previous / next: identical geometry with a pure horizontal mirror.
    c.save();
    c.translate(cx,cy);
    if(action==0)c.scale(-1f,1f);
    for(int i=0;i<2;i++){
      float left=-17+i*14;
      Path triangle=new Path();
      triangle.moveTo(left, -13);
      triangle.lineTo(left+13,0);
      triangle.lineTo(left,13);
      triangle.close();
      c.drawPath(triangle,p);
    }
    c.restore();
  }
}
