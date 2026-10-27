package ro.evolauncher.k2401;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * 21 photographic designs produced for this project. The original generated
 * screenshots are intentionally NEVER redrawn or substituted with generic art.
 * Import the companion ZIP once using Android's document picker. The validated
 * 1280x720 WebPs are kept in private app storage and survive device reboots.
 *
 * The photographs are DECORATIVE: dynamic ECU and media data is rendered on
 * top by EvoSkinPainter, not read from the images or manufactured by the app.
 */
final class EvoSkinStore {
  static final int COUNT=21, REQUEST_IMPORT=2471;
  static final String[] NAMES={
    "EVO DIGITAL DASH","EVO CLASSIC","EVO FUTURE","EVO GAUGE PRO",
    "EVO MULTI INFO","EVO APPS CENTER","LANCER EVOLUTION NIGHT",
    "EVO GT COCKPIT","EVO RED FRONT","LANCER MOUNTAIN",
    "EVO SPEED","EVO SUNSET","LANCER HERO","DIGITAL COCKPIT",
    "TECH GRID","GAUGES FOCUS","LANCER SHOWROOM","MINIMAL SPORT",
    "CAR STATUS","APP LAUNCHER","PERFORMANCE"
  };
  private final Context context;
  private final SharedPreferences prefs;
  private final File root;
  private int current;
  private Bitmap cached;
  private int cachedIndex=-1;

  EvoSkinStore(Context host){
    context=host.getApplicationContext();
    prefs=context.getSharedPreferences("evo_launcher_prefs",Context.MODE_PRIVATE);
    root=new File(context.getFilesDir(),"evo_skins_21");
    current=Math.max(0,Math.min(COUNT-1,prefs.getInt("evo_skin_index",0)));
  }
  int current(){return current;}
  String currentName(){return NAMES[current];}
  boolean installed(){return hasImage(current);}
  boolean hasAll(){
    for(int i=0;i<COUNT;i++)if(!hasImage(i))return false;
    return true;
  }
  boolean hasImage(int index){return index>=0&&index<COUNT&&file(index).isFile();}
  void select(int index){
    if(index<0||index>=COUNT)throw new IllegalArgumentException("Invalid skin "+index);
    current=index;
    if(!prefs.edit().putInt("evo_skin_index",index).commit())
      throw new IllegalStateException("Cannot save selected skin");
  }
  private File file(int index){return new File(root,String.format(Locale.US,"skin_%02d.webp",index));}
  private static void copyBounded(InputStream in,OutputStream out,int max)throws IOException{
    byte[] buffer=new byte[8192];int total=0,n;
    while((n=in.read(buffer))!=-1){
      total+=n;if(total>max)throw new IOException("Image exceeds size limit");
      out.write(buffer,0,n);
    }
  }
  /**
   * ZIP slip-safe and ZIP bomb-bounded import. A failed validation preserves
   * previously installed images and selected skin; no ROM/global changes.
   */
  void importArchive(Uri source)throws IOException {
    if(source==null)throw new IOException("Selectează arhiva ZIP.");
    File staging=new File(context.getCacheDir(),"evo_skin_import_"+android.os.Process.myPid());
    erase(staging);
    if(!staging.mkdirs())throw new IOException("Nu se poate crea folderul temporar");
    boolean[] present=new boolean[COUNT];long total=0L;
    try{
      try(InputStream raw=context.getContentResolver().openInputStream(source)){
        if(raw==null)throw new IOException("Nu pot deschide ZIP");
        try(ZipInputStream zin=new ZipInputStream(new BufferedInputStream(raw))){
          ZipEntry entry;
          while((entry=zin.getNextEntry())!=null){
            String name=entry.getName();
            if("README.txt".equals(name)||"skins/atlas.webp".equals(name)){zin.closeEntry();continue;}
            if(entry.isDirectory()){zin.closeEntry();continue;}
            if(!name.matches("skins/skin_[0-9]{2}\\.webp"))
              throw new IOException("Fișier neașteptat în arhivă: "+name);
            int index=Integer.parseInt(name.substring(11,13));
            if(index>=COUNT||present[index])throw new IOException("Skin invalid sau duplicat: "+name);
            File target=new File(staging,String.format(Locale.US,"skin_%02d.webp",index));
            try(OutputStream out=new FileOutputStream(target)){
              copyBounded(zin,out,1536*1024);
            }
            total+=target.length();if(total>25L*1024*1024)throw new IOException("Arhivă prea mare");
            BitmapFactory.Options opts=new BitmapFactory.Options();
            opts.inJustDecodeBounds=true;BitmapFactory.decodeFile(target.getPath(),opts);
            if(opts.outWidth!=1280||opts.outHeight!=720)
              throw new IOException("Imaginea "+name+" nu are 1280×720.");
            present[index]=true;zin.closeEntry();
          }
        }
      }
      for(int i=0;i<COUNT;i++)
        if(!present[i])throw new IOException("Lipsește "+String.format(Locale.US,"skin_%02d.webp",i));
      if(!root.exists()&&!root.mkdirs())throw new IOException("Nu pot salva imaginile.");
      // Images have all been validated; replace only after validation.
      for(int i=0;i<COUNT;i++){
        File src=new File(staging,String.format(Locale.US,"skin_%02d.webp",i));
        File target=file(i);
        File tmp=new File(root,target.getName()+".new");
        try(InputStream in=new java.io.FileInputStream(src);
            OutputStream out=new FileOutputStream(tmp)){
          copyBounded(in,out,1536*1024);
        }
        if(target.exists()&&!target.delete())throw new IOException("Nu pot înlocui "+target.getName());
        if(!tmp.renameTo(target))throw new IOException("Nu pot finaliza "+target.getName());
      }
      synchronized(this){if(cached!=null)cached.recycle();cached=null;cachedIndex=-1;}
      prefs.edit().putBoolean("evo_skins_imported_v1",true).commit();
    }finally{erase(staging);}
  }
  private static void erase(File where){
    if(where==null||!where.exists())return;
    File[] children=where.listFiles();
    if(children!=null)for(File c:children)erase(c);
    where.delete();
  }
  synchronized Bitmap bitmap(int index){
    if(index<0||index>=COUNT||!hasImage(index))return null;
    if(cachedIndex==index&&cached!=null&&!cached.isRecycled())return cached;
    if(cached!=null&&!cached.isRecycled())cached.recycle();
    cached=null;cachedIndex=-1;
    BitmapFactory.Options opts=new BitmapFactory.Options();
    opts.inPreferredConfig=Bitmap.Config.RGB_565;
    try{
      cached=BitmapFactory.decodeFile(file(index).getPath(),opts);
      if(cached!=null)cachedIndex=index;
    }catch(RuntimeException|OutOfMemoryError fail){cached=null;}
    return cached;
  }
  Bitmap thumbnail(int index){
    if(!hasImage(index))return null;
    BitmapFactory.Options opts=new BitmapFactory.Options();
    opts.inSampleSize=4;opts.inPreferredConfig=Bitmap.Config.RGB_565;
    try{return BitmapFactory.decodeFile(file(index).getPath(),opts);}
    catch(RuntimeException|OutOfMemoryError fail){return null;}
  }
  synchronized void release(){
    if(cached!=null&&!cached.isRecycled())cached.recycle();
    cached=null;cachedIndex=-1;
  }
}
