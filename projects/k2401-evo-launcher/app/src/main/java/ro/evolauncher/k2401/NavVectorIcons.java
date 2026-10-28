package ro.evolauncher.k2401;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;

/** Sharp native icons for six pre-existing sidebar targets; no font fallback. */
final class NavVectorIcons {
  private NavVectorIcons(){}

  static void draw(Canvas c,int type,float cx,float cy,int color){
    Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
    p.setColor(color);
    p.setStyle(Paint.Style.STROKE);
    p.setStrokeWidth(3.2f);
    p.setStrokeCap(Paint.Cap.ROUND);
    p.setStrokeJoin(Paint.Join.ROUND);
    Path path=new Path();
    switch(type){
      case 0: // Home
        path.moveTo(cx-17,cy-3);path.lineTo(cx,cy-18);
        path.lineTo(cx+17,cy-3);c.drawPath(path,p);
        c.drawRoundRect(cx-13,cy-4,cx+13,cy+16,2,2,p);
        c.drawRect(cx-4,cy+5,cx+4,cy+16,p);
        break;
      case 1: // Music: two stems and elliptical note heads
        c.drawLine(cx-3,cy-14,cx-3,cy+11,p);
        c.drawLine(cx+15,cy-18,cx+15,cy+7,p);
        c.drawLine(cx-3,cy-14,cx+15,cy-18,p);
        p.setStyle(Paint.Style.FILL);
        c.drawOval(cx-15,cy+7,cx-3,cy+16,p);
        c.drawOval(cx+3,cy+3,cx+15,cy+12,p);
        break;
      case 2: // Navigation pointer
        path.moveTo(cx,cy-19);path.lineTo(cx+16,cy+17);
        path.lineTo(cx,cy+9);path.lineTo(cx-16,cy+17);
        path.close();c.drawPath(path,p);
        break;
      case 3: // Real gauges, no printed values
        c.drawArc(cx-17,cy-15,cx+17,cy+18,195,150,false,p);
        c.drawArc(cx-17,cy-15,cx+17,cy+18,0,145,false,p);
        c.drawLine(cx,cy+4,cx+10,cy-8,p);
        p.setStyle(Paint.Style.FILL);c.drawCircle(cx,cy+4,3,p);
        break;
      case 4: // Installed apps (four square tiles)
        p.setStyle(Paint.Style.FILL);
        for(int row=0;row<2;row++)for(int col=0;col<2;col++)
          c.drawRoundRect(cx-16+col*19,cy-16+row*19,
            cx-2+col*19,cy-2+row*19,2,2,p);
        break;
      case 5: // Settings: fixed vector cog and centre
        for(int i=0;i<8;i++){
          double a=(Math.PI*2*i)/8.;
          float ax=(float)Math.cos(a),ay=(float)Math.sin(a);
          c.drawLine(cx+ax*14,cy+ay*14,cx+ax*20,cy+ay*20,p);
        }
        c.drawCircle(cx,cy,14,p);
        c.drawCircle(cx,cy,6,p);
        break;
      default:break;
    }
  }
}
