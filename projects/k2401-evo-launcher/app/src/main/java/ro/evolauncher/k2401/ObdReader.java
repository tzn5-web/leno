package ro.evolauncher.k2401;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.IBinder;
import android.os.Looper;
import android.os.Handler;
import android.os.RemoteException;
import android.os.SystemClock;
import org.prowl.torque.remote.ITorqueService;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Read-only Torque Pro AIDL client. Torque is the ONLY owner of the OBD adapter.
 * Values are never synthesized: unsupported, stale or disconnected => NaN / N/A.
 */
final class ObdReader {
  static final class Reading {
    final float rpm, stft, ltft, coolantC, ambientC;
    final boolean live;
    final long capturedAtMs;
    Reading(float r,float s,float l,float c,boolean active){
      this(r,s,l,c,Float.NaN,active);
    }
    Reading(float r,float s,float l,float c,float ambient,boolean active){
      rpm=r;stft=s;ltft=l;coolantC=c;ambientC=ambient;live=active;
      capturedAtMs=SystemClock.elapsedRealtime();
    }
    static Reading empty(){return new Reading(Float.NaN,Float.NaN,Float.NaN,Float.NaN,false);}
  }
  private static final String[] PIDS={"010C","0106","0107","0105","0146"};
  private static final long MAX_STALE_MS=7000L;
  private final Context context;
  private volatile DirectElm327 direct;
  private volatile boolean useDirect;
  private final Runnable onUpdate;
  private final Handler main=new Handler(Looper.getMainLooper());
  private final ExecutorService worker=Executors.newSingleThreadExecutor();
  private volatile Reading current=Reading.empty();
  private volatile String state="TORQUE NECONECTAT";
  private volatile ITorqueService remote;
  private volatile boolean busy;
  private volatile boolean running;
  // Invalidate pending IPC results whenever the service/lifecycle changes.
  private volatile long generation;
  private volatile boolean resolvedOnce;
  private boolean bound;
  private final String[] resolved=new String[PIDS.length];

  private final ServiceConnection connection=new ServiceConnection(){
    @Override public void onServiceConnected(ComponentName name,IBinder binder){
      if(!running)return;
      generation++;
      remote=ITorqueService.Stub.asInterface(binder);
      resolvedOnce=false;
      Arrays.fill(resolved,null);
      state="TORQUE • VERIFIC ECU";
      main.post(onUpdate);
    }
    @Override public void onServiceDisconnected(ComponentName name){disconnect("TORQUE DECONECTAT");}
    @Override public void onBindingDied(ComponentName name){disconnect("TORQUE • SERVICIU OPRIT");}
    @Override public void onNullBinding(ComponentName name){disconnect("TORQUE • SERVICIU INDISPONIBIL");}
  };
  private void disconnect(String reason){
    generation++;
    remote=null; resolvedOnce=false; current=Reading.empty(); state=reason; main.post(onUpdate);
  }
  private final Runnable ticker=new Runnable(){
    @Override public void run(){
      if(!running)return;
      final ITorqueService svc=remote;
      if(svc!=null && !busy){
        busy=true;
        final long epoch=generation;
        worker.execute(()->{
          Reading next=Reading.empty();
          String nextState="TORQUE • DATE LIPSA/EXPIRATE";
          boolean clearResolved=false;
          try{
            if(!running||epoch!=generation||svc!=remote)return;
            if(!svc.isConnectedToECU()){
              nextState="TORQUE • ECU NECONECTAT";
            }else{
              // Discover once per binder connection, even if RPM is unsupported.
              if(!resolvedOnce){
                resolvePids(svc);
                resolvedOnce=true;
              }
              // Torque 2020+ supports string ID aliases, but many installed
              // versions only expose numeric 0x010C/0106/0107/0105 PIDs.
              // Try both public APIs, but NEVER synthesize an ECU measurement.
              String[] ids=resolved.clone();
              float[] fresh={Float.NaN,Float.NaN,Float.NaN,Float.NaN,Float.NaN};
              int count=0;
              for(String id:ids)if(id!=null)count++;
              if(count>0){
                String[] query=new String[count];
                int[] slots=new int[count];int p=0;
                for(int i=0;i<PIDS.length;i++)if(ids[i]!=null){query[p]=ids[i];slots[p++]=i;}
                try{
                  float[] values=svc.getPIDValues(query);
                  long[] times=svc.getPIDUpdateTime(query);
                  if(values!=null&&times!=null&&values.length==count&&times.length==count){
                    for(int i=0;i<count;i++)
                      if(isFresh(times[i])&&Float.isFinite(values[i]))fresh[slots[i]]=values[i];
                  }
                }catch(RemoteException|RuntimeException ignored){
                  // AIDL string API absent: continue with numeric legacy API.
                }
              }
              boolean numericFallback=readNumericPids(svc,fresh);
              // Only filter impossible data; never fabricate a measurement.
              fresh[0]=bounded(fresh[0],0,12000);
              fresh[1]=bounded(fresh[1],-100,100);
              fresh[2]=bounded(fresh[2],-100,100);
              fresh[3]=bounded(fresh[3],-50,170);
              fresh[4]=bounded(fresh[4],-40,85);
              boolean live=Float.isFinite(fresh[0])||Float.isFinite(fresh[1])||
                           Float.isFinite(fresh[2])||Float.isFinite(fresh[3])||
                           Float.isFinite(fresh[4]);
              next=new Reading(fresh[0],fresh[1],fresh[2],fresh[3],fresh[4],live);
              nextState=live?(numericFallback?"TORQUE • ECU LIVE (PID NUMERIC)":"TORQUE • ECU LIVE"):
                (count==0?"TORQUE • AȘTEPTĂ PID / PERMISIUNI":"TORQUE • DATE LIPSA/EXPIRATE");

            }
          }catch(RemoteException|RuntimeException ex){
            next=Reading.empty();
            nextState="TORQUE • API INDISPONIBIL";
            clearResolved=true;
          }finally{
            // An old Binder call must never resurrect readings after pause/rebind.
            if(running && epoch==generation && svc==remote){
              current=next;
              state=nextState;
              if(clearResolved){Arrays.fill(resolved,null);resolvedOnce=false;}
              main.post(onUpdate);
            }
            busy=false;
          }
        });
      }
      main.postDelayed(this,650);
    }
  };
  ObdReader(Context context,Runnable onUpdate){
    this.context=context.getApplicationContext();this.onUpdate=onUpdate;
    // Lazy creation: OEM K2401 Bluetooth stacks can crash during class/service init.
    // Never initialize the ELM327 backend while the launcher first opens.
    // Official Torque API can be selected explicitly; modified/unofficial
    // Torque apps are NOT assumed to implement org.prowl.torque's AIDL.
    this.useDirect=!"torque".equals(this.context.getSharedPreferences("evo_launcher_prefs",Context.MODE_PRIVATE)
      .getString("obd_source","direct"));
  }
  Reading current(){
    if(useDirect)return direct==null?Reading.empty():direct.current();
    Reading snapshot=current;
    // Also expire readings if the IPC worker hangs and no new poll completes.
    return snapshot.live && SystemClock.elapsedRealtime()-snapshot.capturedAtMs>MAX_STALE_MS
        ? Reading.empty() : snapshot;
  }
  String status(){return useDirect?(direct==null?"ELM327 • ALEGE ADAPTORUL":direct.status()):state;}
  String diagnostic(){return useDirect?(direct==null?"Bluetooth ELM neconfigurat":direct.details()):"Torque AIDL "+state;}
  boolean isDirect(){return useDirect;}
  String adapterAddress(){return direct==null?context.getSharedPreferences("evo_launcher_prefs",Context.MODE_PRIVATE).getString("elm327_mac",""):direct.adapterAddress();}
  void chooseDirectAdapter(String mac){
    stop();
    if(direct==null)direct=new DirectElm327(context,onUpdate);
    direct.selectAdapter(mac);
    setMode(true);
  }
  void setMode(boolean directMode){
    if(useDirect==directMode){start();return;}
    stop();
    useDirect=directMode;
    context.getSharedPreferences("evo_launcher_prefs",Context.MODE_PRIVATE).edit()
      .putString("obd_source",useDirect?"direct":"torque").commit();
    start();
  }
  synchronized void start(){
    if(useDirect){
      // Do not touch the head-unit Bluetooth driver until user chooses ELM327.
      if(adapterAddress().isEmpty()){state="ELM327 • ALEGE ADAPTORUL";return;}
      if(direct==null)direct=new DirectElm327(context,onUpdate);
      direct.start();return;
    }
    if(running)return;
    running=true;
    try{
      Intent intent=new Intent();
      intent.setComponent(new ComponentName("org.prowl.torque","org.prowl.torque.remote.TorqueService"));
      bound=context.bindService(intent,connection,Context.BIND_AUTO_CREATE);
      if(!bound)state="PORNEȘTE TORQUE PRO";
    }catch(SecurityException|IllegalArgumentException e){state="TORQUE • BIND REFUZAT";}
    main.post(ticker);
  }
  synchronized void stop(){
    if(direct!=null)direct.stop();
    running=false;generation++;main.removeCallbacks(ticker);
    if(bound){try{context.unbindService(connection);}catch(IllegalArgumentException ignored){}bound=false;}
    remote=null;resolvedOnce=false;Arrays.fill(resolved,null);current=Reading.empty();state="TORQUE NECONECTAT";
  }
  void close(){stop();if(direct!=null)direct.close();worker.shutdownNow();}

  private void resolvePids(ITorqueService svc)throws RemoteException{
    String[] known=null,supported=null;
    // New string-ID endpoints may not be implemented by old Torque builds.
    try{known=svc.listAllPIDs();}catch(RemoteException|RuntimeException ignored){}
    try{supported=svc.listECUSupportedPIDs();}catch(RemoteException|RuntimeException ignored){}
    for(int i=0;i<PIDS.length;i++){
      String match=find(PIDS[i],supported);
      // Some Torque builds report supported IDs differently: fallback to known.
      if(match==null)match=find(PIDS[i],known);
      resolved[i]=match;
    }
  }
  /** Legacy numeric PID path from the public Torque AIDL. These are only
   * read commands, NOT raw ELM writes and NOT test-mode or spoofed values.
   * Return true only when at least one sensor was actually updated.
   */
  private boolean readNumericPids(ITorqueService svc,float[] fresh){
    boolean updated=false;
    final long[] ids={0x010CL,0x0106L,0x0107L,0x0105L,0x0146L};
    long[] supported=null;
    try{supported=svc.getListOfECUSupportedPids();}catch(RemoteException|RuntimeException ignored){}
    for(int i=0;i<PIDS.length;i++){
      if(Float.isFinite(fresh[i]))continue;
      // If Torque knows unsupported IDs, avoid needless ELM traffic.
      if(supported!=null&&supported.length>0){
        boolean found=false;
        for(long sensor:supported)if(sensor==ids[i]){found=true;break;}
        if(!found)continue;
      }
      try{
        float v=svc.getValueForPid(ids[i],true);
        long timestamp=svc.getUpdateTimeForPID(ids[i]);
        if(isFresh(timestamp)&&Float.isFinite(v)){fresh[i]=v;updated=true;}
      }catch(RemoteException|RuntimeException ignored){
        // Some Torque builds do not export this deprecated numeric method.
      }
    }
    return updated;
  }

  private static String find(String pid,String[] entries){
    if(entries==null)return null;
    for(String candidate:entries){
      if(candidate==null)continue;
      String upper=candidate.trim().toUpperCase(Locale.US).replace(" ","");
      if(upper.startsWith("0X"))upper=upper.substring(2);
      if(upper.startsWith(pid)&&
         (upper.length()==pid.length()||!isHex(upper.charAt(pid.length()))))return candidate;
    }
    return null;
  }
  private static boolean isHex(char ch){
    return (ch>='0'&&ch<='9')||(ch>='A'&&ch<='F');
  }
  private static float bounded(float v,float min,float max){
    return Float.isFinite(v)&&v>=min&&v<=max?v:Float.NaN;
  }
  private static boolean isFresh(long timestamp){
    if(timestamp<=0)return false;
    // Torque versions have used both uptime-ms and Unix epoch-ms. Accept either
    // only when it points to a recent OBD update; no artificial freshness.
    long wall=System.currentTimeMillis();
    long elapsed=SystemClock.elapsedRealtime();
    return (timestamp<=wall&&wall-timestamp<=MAX_STALE_MS) ||
           (timestamp<=elapsed&&elapsed-timestamp<=MAX_STALE_MS);
  }
}
