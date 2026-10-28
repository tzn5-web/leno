package ro.evolauncher.k2401;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.media.MediaMetadata;
import android.media.session.MediaController;
import android.media.session.PlaybackState;
import android.os.SystemClock;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;

/**
 * Unique native foreground widgets for each of the 20 non-Digital-Dash themes.
 * The approved illustration is a decorative scene only. Every clock, PID,
 * album and tappable app tile in these areas is rendered from Android or ECU
 * data and aligned with that illustration's ORIGINAL layout. No fake sensor
 * or mock music values are ever passed to these widgets.
 *
 * 0/EVO Digital Dash has its own bespoke native instrument panel in SkinEngine.
 */
final class ThemeNativePanels {
  static final class Layout {
    final Rect clock, media, status, apps;
    final Rect[] g;
    final int mode; // 1=apps, 2=diagnostics, 3=telemetry, 0=normal
    Layout(Rect t,Rect m,Rect s,Rect a,int[][] g,int mode){
      clock=t;media=m;status=s;apps=a;this.mode=mode;
      this.g=new Rect[4];for(int i=0;i<4;i++)this.g[i]=new Rect(g[i][0],g[i][1],
        g[i][0]+g[i][2],g[i][1]+g[i][3]);
    }
  }
  private final MainActivity host;
  private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
  private final ArrayList<String> installed=new ArrayList<>();
  private final ArrayList<Rect> appRects=new ArrayList<>();
  private Layout layout;
  private int lastStyle=-1;
  private static final int WHITE=0xfff0f7fd,MUTED=0xff9aacbf;
  private static final int[] PALETTE={
    0xffed3349,0xff30c8ff,0xffe9a044,0xff55d8b9,0xffa786ff
  };
  private static Rect rect(int x,int y,int w,int h){
    return new Rect(x,y,x+w,y+h);
  }
  private static int[][] four(int x,int y,int w,int h,int gap){
    int single=(w-3*gap)/4;
    return new int[][]{{x,y,single,h},{x+single+gap,y,single,h},
      {x+2*(single+gap),y,single,h},{x+3*(single+gap),y,single,h}};
  }
  private static int[][] rightGrid(int x,int y,int w,int h,int gap){
    int ww=(w-gap)/2,hh=(h-gap)/2;
    return new int[][]{{x,y,ww,hh},{x+ww+gap,y,ww,hh},
      {x,y+hh+gap,ww,hh},{x+ww+gap,y+hh+gap,ww,hh}};
  }
  private static int[][] verticalFour(int x,int y,int w,int h,int gap){
    int hh=(h-3*gap)/4;
    return new int[][]{{x,y,w,hh},{x,y+hh+gap,w,hh},
      {x,y+2*(hh+gap),w,hh},{x,y+3*(hh+gap),w,hh}};
  }
  private static int[][] leftHero(int x,int y,int w,int h,int rightX,int rightY,int rightW,int rightH){
    int gap=10,hh=(rightH-2*gap)/3;
    return new int[][]{{x,y,w,h},{rightX,rightY,rightW,hh},
      {rightX,rightY+hh+gap,rightW,hh},
      {rightX,rightY+2*(hh+gap),rightW,hh}};
  }
  // The positions here follow the original 1280x720 concept screenshots.
  // Their 4 PID regions are different for each theme, not a global right card.
  static Layout profile(int id){
    switch(id){
      case 1: return new Layout(rect(105,58,213,203),rect(780,59,480,359),
        rect(105,269,210,147),null,four(104,447,1154,242,12),0); // Classic
      case 2: return new Layout(rect(285,528,269,157),rect(945,55,320,308),
        null,rect(643,523,618,177),leftHero(107,89,641,419,761,85,169,387),0); // Future
        // Clock covers illustrated 22:36; launcher tiles now represent real apps.
      case 3: return new Layout(rect(628,58,160,138),rect(795,52,463,359),
        rect(964,393,296,298),null,four(103,449,890,240,11),0); // Gauge Pro
      case 4: return new Layout(rect(105,61,243,184),rect(920,55,340,331),
        rect(918,495,342,181),null,four(101,496,799,179,10),3); // Multi Info
      case 5: return new Layout(null,rect(920,55,338,314),
        null,rect(105,64,796,614),rightGrid(923,396,331,282,9),1); // Apps
      case 6: return new Layout(rect(104,65,238,183),rect(787,67,471,341),
        rect(103,257,227,140),null,four(105,455,1155,240,12),0); // Evolution Night
      case 7: return new Layout(rect(101,18,273,84),rect(925,65,336,308),
        null,null,leftHero(105,100,665,455,780,386,474,308),0); // GT
      case 8: return new Layout(rect(105,63,233,168),rect(844,57,411,339),
        null,null,four(443,448,813,221,10),0); // Red Front
      case 9: return new Layout(rect(108,55,252,192),rect(914,57,341,311),
        rect(108,251,248,151),null,four(105,458,1151,215,12),0); // Mountain
      case 10:return new Layout(rect(101,50,259,174),rect(938,51,319,337),
        rect(103,255,259,213),null,verticalFour(674,32,235,496,7),2); // Speed
        // Live RPM/STFT/LTFT/ECT cover all four illustrated fictional values.
      case 11:return new Layout(rect(100,59,284,175),rect(934,55,324,335),
        null,null,four(104,385,1153,271,12),0); // Sunset
        // Hide the baked 2520/-3.2/+2.8/89 examples rather than showing both.
      case 12:return new Layout(rect(102,52,305,203),rect(773,52,486,347),
        rect(102,262,268,142),null,rightGrid(778,413,478,282,12),0); // Hero
      case 13:return new Layout(rect(374,54,380,141),rect(832,53,423,310),
        null,null,leftHero(112,166,633,389,838,386,411,296),0); // Cockpit
      case 14:return new Layout(rect(103,58,429,155),rect(925,52,331,297),
        null,rect(106,245,690,436),rightGrid(835,363,422,310,13),1); // Grid
      case 15:return new Layout(rect(505,58,295,135),null,
        null,null,new int[][]{{102,177,315,375},{115,567,478,128},
          {620,567,493,128},{936,181,313,365}},0); // Focus
      case 16:return new Layout(rect(104,57,277,157),rect(827,57,431,323),
        rect(101,422,260,251),null,rightGrid(840,396,412,295,11),2); // Showroom
      case 17:return new Layout(rect(106,52,305,160),rect(908,58,350,336),
        null,null,four(105,449,1153,243,12),0); // Minimal Sport
      case 18:return new Layout(rect(98,49,344,118),null,
        rect(735,117,525,558),null,rightGrid(750,207,488,430,11),2); // Status
      case 19:return new Layout(rect(98,49,305,81),null,
        null,rect(109,120,1148,563),new int[][]{
          {700,590,125,78},{833,590,125,78},{965,590,125,78},{1097,590,125,78}
        },1); // Launcher
      case 20:return new Layout(rect(118,45,370,85),null,
        null,null,new int[][]{{104,152,270,213},{913,153,340,222},
          {105,417,286,228},{931,429,324,226}},0); // Performance
      default:return new Layout(rect(112,55,250,143),rect(813,56,442,317),
        null,null,rightGrid(820,404,432,288,10),0);
    }
  }
  ThemeNativePanels(MainActivity activity){host=activity;loadApps();}
  private void loadApps(){
    installed.clear();
    try{
      PackageManager pm=host.getPackageManager();
      Intent query=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
      HashSet<String> seen=new HashSet<>();
      List<ResolveInfo> matches=pm.queryIntentActivities(query,0);
      Collections.sort(matches,(a,b)->{
        String al=String.valueOf(a.loadLabel(pm)),bl=String.valueOf(b.loadLabel(pm));
        return al.compareToIgnoreCase(bl);
      });
      for(ResolveInfo r:matches){
        if(r.activityInfo==null)continue;
        String pkg=r.activityInfo.packageName;
        if(!pkg.equals(host.getPackageName())&&seen.add(pkg)&&pm.getLaunchIntentForPackage(pkg)!=null)
          installed.add(pkg);
      }
    }catch(RuntimeException ignored){}
  }
  private void fill(Canvas c,Rect area,int bg,int border,int radius){
    if(area==null)return;
    p.setColor(bg);p.setShader(null);p.setStyle(Paint.Style.FILL);
    c.drawRoundRect(area.left,area.top,area.right,area.bottom,radius,radius,p);
    if(border!=0){p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2f);p.setColor(border);
      c.drawRoundRect(area.left,area.top,area.right,area.bottom,radius,radius,p);}
    p.setStyle(Paint.Style.FILL);
  }
  private void text(Canvas c,String label,float x,float y,float font,int color,boolean bold){
    p.setColor(color);p.setShader(null);p.setTypeface(Typeface.create(
      bold?"sans-serif-condensed":"sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));
    p.setTextSize(font);p.setStyle(Paint.Style.FILL);p.setTextAlign(Paint.Align.LEFT);
    c.drawText(label,x,y,p);
  }
  private void middle(Canvas c,String s,float x,float y,float font,int color){
    p.setColor(color);p.setShader(null);p.setTypeface(Typeface.DEFAULT_BOLD);
    p.setTextSize(font);p.setStyle(Paint.Style.FILL);p.setTextAlign(Paint.Align.CENTER);
    c.drawText(s,x,y,p);p.setTextAlign(Paint.Align.LEFT);
  }
  private void line(Canvas c,float x,float y,float x2,float y2,int color,float width){
    p.setColor(color);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(width);
    p.setStrokeCap(Paint.Cap.ROUND);c.drawLine(x,y,x2,y2,p);p.setStyle(Paint.Style.FILL);
  }
  private static String crop(String s,int max){
    if(s==null)return "";return s.length()>max?s.substring(0,max-1)+"…":s;
  }
  private int accent(int id){return new int[]{
    0xffe52e4c,0xff26cafa,0xffe04b63,0xff31d0fa,0xffdc3a55,
    0xfff13751,0xfff14451,0xffff3247,0xff35cafa,0xfff44858,
    0xffef9652,0xffec3a55,0xfff23752,0xff27d2f3,0xffe93356,
    0xffe85c4b,0xff27d5ef,0xffe94056,0xff35d6f8,0xfff1354c
  }[Math.max(1,Math.min(20,id))-1];}
  private void clock(Canvas c,Rect area,int accent){
    if(area==null)return;
    fill(c,area,0xff0a1421,accent,14);
    float x=area.left+13,y=area.top;
    boolean hour24=host.launcherSettings==null||host.launcherSettings.use24HourClock();
    String now=new SimpleDateFormat(hour24?"HH:mm":"hh:mm",Locale.getDefault()).format(new java.util.Date());
    String date=new SimpleDateFormat("EEE, d MMM yyyy",new Locale("ro","RO")).format(new java.util.Date());
    float size=Math.min(62,Math.max(26,area.height()*.40f));
    text(c,now,x,y+Math.min(area.height()*.54f,80),size,WHITE,true);
    text(c,date,x,y+Math.min(area.height()*.80f,122),Math.min(18,Math.max(12,area.height()*.13f)),MUTED,false);
  }
  private void status(Canvas c,Rect area,int color){
    if(area==null)return;
    fill(c,area,0xff091321,color,12);
    ObdReader.Reading rd=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    String state=host.obd==null?"OBD neconectat":host.obd.status();
    text(c,"STARE VEHICUL • OBD-II",area.left+13,area.top+28,Math.min(17,area.width()/15f),WHITE,true);
    text(c,crop(state,Math.max(11,area.width()/10)),area.left+13,
      area.top+59,Math.min(15,area.width()/17f),rd.live?0xff62e8ba:MUTED,false);
    if(area.height()>125){
      text(c,"RPM",area.left+13,area.top+101,15,MUTED,false);
      String rpm=Float.isFinite(rd.rpm)?String.format(Locale.US,"%.0f",rd.rpm):"N/A";
      text(c,rpm+" rpm",area.left+76,area.top+101,17,WHITE,true);
    }
  }
  private void media(Canvas c,Rect area,int accent){
    if(area==null)return;
    fill(c,area,0xff091320,accent,16);
    int x=area.left,y=area.top,w=area.width(),h=area.height();
    text(c,crop(host.mediaName.isEmpty()?"EVO MEDIA":host.mediaName,29),x+18,y+34,
      Math.min(24,Math.max(16,h/14f)),WHITE,true);
    MediaController mc=host.media;
    Bitmap art=null;
    String title="",artist="";
    long duration=0,pos=0;
    boolean play=false;
    if(mc!=null){
      MediaMetadata data=mc.getMetadata();
      if(data!=null){
        CharSequence t=data.getText(MediaMetadata.METADATA_KEY_TITLE);
        CharSequence a=data.getText(MediaMetadata.METADATA_KEY_ARTIST);
        title=t==null?"":t.toString();artist=a==null?"":a.toString();
        art=data.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART);
        if(art==null)art=data.getBitmap(MediaMetadata.METADATA_KEY_ART);
        duration=data.getLong(MediaMetadata.METADATA_KEY_DURATION);
      }
      PlaybackState state=mc.getPlaybackState();
      if(state!=null){
        play=state.getState()==PlaybackState.STATE_PLAYING;
        pos=state.getPosition();
        if(play){long since=SystemClock.elapsedRealtime()-state.getLastPositionUpdateTime();
          pos+=(long)(Math.max(0,since)*state.getPlaybackSpeed());}
      }
    }
    if(title.isEmpty()){title="Fără redare activă";artist="Alege playerul"; }
    int artwork=Math.max(52,Math.min(h-106,w/3));
    Rect box=rect(x+16,y+53,artwork,artwork);
    fill(c,box,0xff3d1a2c,0,10);
    if(art!=null&&!art.isRecycled()){
      p.setColor(Color.WHITE);p.setStyle(Paint.Style.FILL);
      c.drawBitmap(art,null,box,p);
    }else{
      middle(c,"YT",box.centerX(),box.centerY()+12,Math.min(35,artwork*.38f),WHITE);
    }
    int right=x+artwork+28;
    text(c,crop(title,Math.max(12,(w-artwork-40)/13)),right,y+92,
      Math.max(15,Math.min(25,h/13f)),WHITE,true);
    text(c,crop(artist,Math.max(12,(w-artwork-40)/11)),right,y+120,
      Math.max(13,Math.min(18,h/17f)),MUTED,false);
    float xb=right,yb=y+h-96,wb=x+w-right-22;
    line(c,xb,yb,xb+wb,yb,0xff455566,4f);
    if(duration>0&&pos>=0)line(c,xb,yb,xb+wb*Math.min(1,(float)pos/duration),yb,accent,4f);
    final float cy=y+h-36;
    middle(c,"◀",x+w*.39f,cy,30,WHITE);
    fill(c,rect((int)(x+w*.54f)-30,(int)(cy-34),60,54),accent,0,25);
    middle(c,play?"Ⅱ":"▶",x+w*.54f,cy+1,27,WHITE);
    middle(c,"▶",x+w*.73f,cy,30,WHITE);
  }
  private static float normalize(float value,float lo,float hi){
    return Math.max(0f,Math.min(1f,(value-lo)/(hi-lo)));
  }
  private void gauge(Canvas c,Rect area,int idx,int theme,int preferred){
    if(area==null)return;
    ObdReader.Reading rd=host.obd==null?ObdReader.Reading.empty():host.obd.current();
    float[] values={rd.rpm,rd.stft,rd.ltft,rd.coolantC};
    String[] labels={"RPM","STFT B1","LTFT B1","TEMP APĂ"};
    String[] units={"rpm","%","%","°C"};
    float[] lows={0,-25,-25,40},highs={8000,25,25,120};
    float v=values[idx];
    boolean valid=Float.isFinite(v);
    int color=(idx==0?accent(theme):idx==1?0xff31c9ff:idx==2?0xfff2ae48:0xffee445d);
    int x=area.left,y=area.top,w=area.width(),h=area.height();
    fill(c,area,0xff08111e,color,Math.min(15,Math.max(6,h/8)));
    String num=!valid?"N/A":idx==0||idx==3?
      String.format(Locale.US,"%.0f",v):String.format(Locale.US,"%+.1f",v);
    if(h<135||w<150||preferred==4||preferred==5){
      text(c,labels[idx],x+11,y+Math.min(26,h*.34f),Math.min(17,Math.max(12,h*.17f)),color,true);
      text(c,num,x+13,y+Math.min(69,h*.67f),Math.min(37,Math.max(20,h*.34f)),WHITE,true);
      text(c,units[idx],x+w-46,y+h-15,Math.min(15,Math.max(11,h*.16f)),MUTED,false);
      if(valid){
        float f=normalize(v,lows[idx],highs[idx]);
        line(c,x+12,y+h-8,x+w-12,y+h-8,0xff263f4d,5);
        line(c,x+12,y+h-8,x+12+(w-24)*f,y+h-8,color,5);
      }
      return;
    }
    float rad=Math.min(w*.38f,h*.32f),cx=x+w*.5f,cy=y+h*.42f;
    int geometry=(theme+preferred)%7;
    if(geometry==3){
      Path outline=new Path();
      for(int a=0;a<8;a++){
        float phi=(float)(2*Math.PI*(a+.5)/8);
        float xx=cx+(rad+7)*(float)Math.cos(phi),yy=cy+(rad+7)*(float)Math.sin(phi);
        if(a==0)outline.moveTo(xx,yy);else outline.lineTo(xx,yy);
      }
      outline.close();p.setColor(color);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2);
      c.drawPath(outline,p);
    }
    p.setStyle(Paint.Style.STROKE);p.setColor(0xff39485b);p.setStrokeWidth(geometry==2?11:6);
    c.drawArc(cx-rad,cy-rad,cx+rad,cy+rad,135,270,false,p);
    float amount=valid?normalize(v,lows[idx],highs[idx]):0;
    if(valid){
      p.setColor(color);p.setStrokeWidth(geometry==2?11:7);
      p.setStrokeCap(Paint.Cap.ROUND);
      c.drawArc(cx-rad,cy-rad,cx+rad,cy+rad,135,270*amount,false,p);
    }
    p.setStyle(Paint.Style.FILL);
    if(geometry==1||geometry==6){
      for(int a=0;a<=10;a++){
        float angle=(float)Math.toRadians(135+a*27);
        float x1=cx+(rad-12)*(float)Math.cos(angle);
        float y1=cy+(rad-12)*(float)Math.sin(angle);
        float x2=cx+(rad-1)*(float)Math.cos(angle);
        float y2=cy+(rad-1)*(float)Math.sin(angle);
        line(c,x1,y1,x2,y2,a/10f<=amount&&valid?color:0xff566379,2);
      }
    }
    middle(c,num,cx,cy+10,Math.min(40,Math.max(23,rad*.42f)),WHITE);
    middle(c,labels[idx],cx,y+h-37,Math.min(21,Math.max(13,w*.075f)),WHITE);
    middle(c,units[idx],cx,y+h-12,Math.min(17,Math.max(11,w*.052f)),color);
  }
  private void apps(Canvas c,Rect area){
    if(area==null)return;
    fill(c,area,0xff081322,0xffbc3156,14);
    text(c,"APLICAȚII INSTALATE",area.left+16,area.top+35,23,WHITE,true);
    int cols=area.width()>700?5:3,iconH=area.height()<220?90:110,gap=8;
    int inner=area.width()-30;
    int ww=(inner-gap*(cols-1))/cols;
    appRects.clear();
    PackageManager pm=host.getPackageManager();
    int visibleRows=Math.max(1,(area.height()-66)/iconH);
    int limit=Math.min(installed.size(),cols*visibleRows);
    for(int i=0;i<limit;i++){
      int col=i%cols,row=i/cols;
      int xx=area.left+14+col*(ww+gap),yy=area.top+54+row*iconH;
      Rect item=rect(xx,yy,ww,iconH-5);
      fill(c,item,0xff172435,0xff41556c,8);
      try{
        Drawable drawable=pm.getApplicationIcon(installed.get(i));
        int size=Math.min(62,Math.max(35,item.width()/2));
        drawable.setBounds(item.centerX()-size/2,yy+9,item.centerX()+size/2,yy+size+9);
        drawable.draw(c);
        CharSequence name=pm.getApplicationLabel(pm.getApplicationInfo(installed.get(i),0));
        String title=name==null?"Aplicație":name.toString();
        middle(c,crop(title,ww/10),item.centerX(),yy+iconH-20,Math.min(16,Math.max(10,ww/11f)),WHITE);
      }catch(Exception ignored){}
      appRects.add(item);
    }
    if(installed.isEmpty())middle(c,"APLICAȚII NECUNOSCUTE",area.centerX(),
      area.centerY(),20,MUTED);
  }
  private void footer(Canvas c,int accent){
    Rect skin=rect(485,678,137,33),app=rect(629,678,140,33);
    fill(c,skin,0xe20a1826,accent,9);
    fill(c,app,0xe20a1826,0xff35d8c9,9);
    middle(c,"SKINURI",skin.centerX(),701,14,WHITE);
    middle(c,"APLICAȚII",app.centerX(),701,14,WHITE);
  }
  private void hidePrintedDemo(Canvas c,int id){
    // The supplied original photographs include baked-in weather and sensor
    // values. These are NOT live. Mask only the unsupported example cards,
    // leaving the vehicle photograph and genuine Android/ELM overlays intact.
    Rect demo=null;
    switch(id){
      case 3:demo=rect(657,197,137,174);break; // 14°C mock card
      case 4:demo=rect(101,241,220,176);break; // 14°C mock card
      case 6:demo=rect(17,232,180,132);break; // 12°C mock card
      case 8:demo=rect(21,237,188,128);break; // 12°C mock card
      case 11:demo=rect(75,236,190,145);break; // 12°C mock card
      case 12:demo=rect(449,67,223,162);break; // sunset weather mock
      case 14:demo=rect(550,68,172,186);break; // 12°C mock card
      case 16:demo=rect(368,64,150,164);break; // showroom weather mock
      case 17:demo=rect(356,63,162,150);break; // 12°C mock card
    }
    if(demo!=null){
      fill(c,demo,0xff0a1421,0xff3d5067,11);
      text(c,"MITSUBISHI",demo.left+12,demo.top+28,16,WHITE,true);
      text(c,"EVO LAUNCHER",demo.left+12,demo.top+56,13,MUTED,false);
    }
    if(id==10){
      // Concept illustration advertises 14.1 V; this ELM poller does not
      // read the voltage PID, therefore displaying 14.1 V would be false.
      fill(c,rect(38,471,191,118),0xff0a1421,0xff415469,10);
      text(c,"OBD-II",53,518,19,WHITE,true);
      text(c,"Numai date ECU",53,548,14,MUTED,false);
    }
    if(id==15){
      // The mockup bottom strip has LTFT, 87°C and 14.1 V examples
      // underneath our real widgets. Remove every printed value first.
      fill(c,rect(424,479,840,215),0xff08111e,0,12);
    }
  }
  void draw(Canvas c,int id){
    lastStyle=id;
    hidePrintedDemo(c,id);
    layout=profile(id);
    int color=accent(id);
    clock(c,layout.clock,color);
    if(layout.apps!=null)apps(c,layout.apps);
    if(layout.status!=null)status(c,layout.status,color);
    if(layout.media!=null)media(c,layout.media,color);
    for(int i=0;i<4;i++)gauge(c,layout.g[i],i,id,layout.mode==3?4:id%7);
    footer(c,color);
  }
  boolean touch(float x,float y){
    if(layout==null)return false;
    if(x>=485&&x<=623&&y>=677){host.showSkinPicker();return true;}
    if(x>=628&&x<=771&&y>=677){host.showInstalledApps();return true;}
    if(layout.apps!=null&&layout.apps.contains((int)x,(int)y)){
      for(int i=0;i<appRects.size();i++){
        if(appRects.get(i).contains((int)x,(int)y)&&i<installed.size()){
          host.app(installed.get(i));return true;
        }
      }
      host.showInstalledApps();return true;
    }
    if(layout.media!=null&&layout.media.contains((int)x,(int)y)){
      Rect m=layout.media;
      if(y>m.bottom-85){
        float fraction=(x-m.left)/(float)m.width();
        host.mediaAction(fraction<.48f?0:fraction<.64f?1:2);
      }else host.choosePlayer();
      return true;
    }
    for(Rect r:layout.g)
      if(r!=null&&r.contains((int)x,(int)y)){host.showObdStatus();return true;}
    if(layout.status!=null&&layout.status.contains((int)x,(int)y)){
      host.showObdStatus();return true;
    }
    if(layout.clock!=null&&layout.clock.contains((int)x,(int)y)){
      host.showSkinPicker();return true;
    }
    return false;
  }
}
