package ro.evolauncher.k2401;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.IBinder;
import android.os.Parcel;
import android.os.RemoteException;
import android.os.SystemClock;

/** Read-only Torque Pro legacy plugin API bridge. Never opens an ELM327 socket. */
final class ObdReader {
  static final class Reading {
    final float rpm, stft, ltft, coolantC;
    final boolean live;
    Reading(float rpm,float stft,float ltft,float coolantC,boolean live) {
      this.rpm=rpm;this.stft=stft;this.ltft=ltft;this.coolantC=coolantC;this.live=live;
    }
    static Reading empty(){return new Reading(Float.NaN,Float.NaN,Float.NaN,Float.NaN,false);}
  }
  private static final String DESCRIPTOR="org.prowl.torque.remote.ITorqueService";
  // getValueForPid(long, boolean) is the second method of Torque's published AIDL.
  private static final int GET_VALUE=IBinder.FIRST_CALL_TRANSACTION+1;
  private final Context context;
  private final Runnable onUpdate;
  private final android.os.Handler ui=new android.os.Handler(android.os.Looper.getMainLooper());
  private volatile Reading current=Reading.empty();
  private volatile String state="TORQUE NECONECTAT";
  private volatile IBinder remote;
  private boolean bound;
  private boolean running;
  private final ServiceConnection connection=new ServiceConnection(){
    public void onServiceConnected(ComponentName name,IBinder binder){
      remote=binder;state="TORQUE CONECTAT";onUpdate.run();
    }
    public void onServiceDisconnected(ComponentName name){
      remote=null;current=Reading.empty();state="TORQUE DECONECTAT";onUpdate.run();
    }
  };
  private final Runnable poll=new Runnable(){
    public void run(){
      if(!running)return;
      IBinder b=remote;
      if(b!=null){
        try{
          float rpm=read(b,0x010c),stft=read(b,0x0106),ltft=read(b,0x0107),coolant=read(b,0x0105);
          // Torque API returns already-scaled PID values; do not apply OBD byte formulas twice.
          boolean live=Float.isFinite(rpm)&&rpm>=0&&rpm<=12000;
          current=live?new Reading(rpm,stft,ltft,coolant,true):Reading.empty();
          state=live?"TORQUE LIVE":"TORQUE • FĂRĂ DATE ECU";
        }catch(Exception e){remote=null;current=Reading.empty();state="TORQUE • EROARE API";}
      }
      onUpdate.run();
      ui.postDelayed(this,500);
    }
  };
  ObdReader(Context context,Runnable onUpdate){this.context=context.getApplicationContext();this.onUpdate=onUpdate;}
  Reading current(){return current;}
  String status(){return state;}
  synchronized void start(){
    if(running)return;
    running=true;
    try{
      Intent intent=new Intent();
      intent.setComponent(new ComponentName("org.prowl.torque","org.prowl.torque.remote.TorqueService"));
      bound=context.bindService(intent,connection,Context.BIND_AUTO_CREATE);
      if(!bound)state="PORNEȘTE TORQUE PRO";
    }catch(Exception e){state="TORQUE INDISPONIBIL";}
    ui.post(poll);
  }
  synchronized void stop(){
    running=false;ui.removeCallbacks(poll);
    if(bound){try{context.unbindService(connection);}catch(Exception ignored){}bound=false;}
    remote=null;current=Reading.empty();state="TORQUE NECONECTAT";
  }
  private static float read(IBinder binder,long pid)throws RemoteException{
    Parcel data=Parcel.obtain(),reply=Parcel.obtain();
    try{
      data.writeInterfaceToken(DESCRIPTOR);data.writeLong(pid);data.writeInt(0);
      if(!binder.transact(GET_VALUE,data,reply,0))throw new RemoteException("Torque method unavailable");
      reply.readException();
      float value=reply.readFloat();
      return Float.isFinite(value)?value:Float.NaN;
    }finally{reply.recycle();data.recycle();}
  }
}
