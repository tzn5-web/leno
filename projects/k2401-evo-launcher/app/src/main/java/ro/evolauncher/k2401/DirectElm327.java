package ro.evolauncher.k2401;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Read-only ELM327 transport. Bluetooth Classic SPP and BLE GATT UART are
 * probed on the one PAIRED device explicitly selected by the driver.
 * Only read-only OBD Mode 01 PIDs are sent. A single worker serializes all
 * ECU transactions: no overlapping requests, no fake readings.
 *
 * RPM and STFT are sampled every fast cycle; coolant and LTFT are slower.
 * Actual ECU/adapter response time, not a fictional 1ms timer, controls rate.
 */
final class DirectElm327 {
  private static final UUID SPP=UUID.fromString("00001101-0000-1000-8000-00805f9b34fb");
  private static final String PREFS="evo_launcher_prefs",KEY="elm327_mac",KEY_MODE="elm327_last_mode";
  private static final long FAST_STALE=2200L,SLOW_STALE=14000L;
  private final Context context;
  private final SharedPreferences preferences;
  private final Handler ui=new Handler(Looper.getMainLooper());
  private final ExecutorService io=Executors.newSingleThreadExecutor();
  private final Runnable onUpdate;
  private volatile boolean running,closed;
  private volatile BluetoothSocket classic;
  private volatile ElmBleSerial ble;
  private volatile ObdReader.Reading sample=ObdReader.Reading.empty();
  private volatile String state="ELM327 • ALEGE ADAPTORUL";
  private volatile String selectedMac="",mode="AUTO",stage="NECONECTAT",lastFailure="";
  private volatile long epoch,roundTripMs;
  private volatile int ratePerSecond;
  // This flag is owned by the I/O worker except at start() scheduling.
  private boolean workerActive;
  private final float[] values={Float.NaN,Float.NaN,Float.NaN,Float.NaN};
  private final long[] times={0,0,0,0};
  private final int[] pids={0x0C,0x06,0x05,0x07};
  // Index 0=RPM, 1=STFT, 2=coolant, 3=LTFT.
  private long fastCounter;

  DirectElm327(Context host,Runnable callback){
    context=host.getApplicationContext();
    preferences=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
    selectedMac=preferences.getString(KEY,"");
    mode=preferences.getString(KEY_MODE,"AUTO");
    onUpdate=callback;
  }
  boolean configured(){return selectedMac!=null&&!selectedMac.isEmpty();}
  String adapterAddress(){return selectedMac;}
  String status(){return state;}
  String details(){return "Transport: "+mode+"\nEtapă: "+stage+
    "\nUltimul răspuns: "+roundTripMs+"ms / "+ratePerSecond+" PID/s"+
    (lastFailure.isEmpty()?"":"\nEroare: "+lastFailure);}
  void selectAdapter(String mac){
    stop();
    if(mac==null)mac="";
    if(!mac.isEmpty()&&!BluetoothAdapter.checkBluetoothAddress(mac))
      throw new IllegalArgumentException("MAC invalid");
    if(!mac.equalsIgnoreCase(selectedMac)){
      mode="AUTO";
      preferences.edit().putString(KEY_MODE,mode).commit();
    }
    selectedMac=mac;
    preferences.edit().putString(KEY,mac).commit();
    state=mac.isEmpty()?"ELM327 • ALEGE ADAPTORUL":"ELM327 • CONFIGURAT";
    notifyUI();
  }
  ObdReader.Reading current(){
    // Each PID has an individual freshness budget, so a slow coolant poll
    // never holds up a new RPM/STFT sample and never creates fake readings.
    synchronized(values){
      long now=SystemClock.elapsedRealtime();
      float rpm=fresh(0,now,FAST_STALE),stft=fresh(1,now,FAST_STALE);
      float water=fresh(2,now,SLOW_STALE),ltft=fresh(3,now,SLOW_STALE);
      boolean live=Float.isFinite(rpm)||Float.isFinite(stft)||
        Float.isFinite(water)||Float.isFinite(ltft);
      return new ObdReader.Reading(rpm,stft,ltft,water,live);
    }
  }
  private float fresh(int i,long now,long ttl){
    return times[i]>0&&now-times[i]<=ttl?values[i]:Float.NaN;
  }
  private void clearValues(){
    synchronized(values){
      for(int i=0;i<4;i++){values[i]=Float.NaN;times[i]=0;}
    }
    sample=ObdReader.Reading.empty();
    notifyUI();
  }
  void start(){
    if(closed||running)return;
    running=true;
    final long token=++epoch;
    if(!configured()){state="ELM327 • ALEGE ADAPTORUL";notifyUI();return;}
    synchronized(this){
      if(workerActive)return;
      workerActive=true;
    }
    io.execute(()->runWorker(token));
  }
  void stop(){
    running=false;++epoch;
    BluetoothSocket socket=classic;classic=null;
    if(socket!=null)try{socket.close();}catch(IOException ignored){}
    ElmBleSerial session=ble;ble=null;
    if(session!=null)session.close();
    clearValues();state="ELM327 • OPRIT";notifyUI();
  }
  void close(){closed=true;stop();io.shutdownNow();}
  private boolean alive(long token){return running&&!closed&&epoch==token;}
  private void notifyUI(){ui.post(onUpdate);}
  private void step(long token,String next){
    stage=next;
    if(alive(token)){state="ELM327 • "+next;notifyUI();}
  }
  private void runWorker(long token){
    try{
      while(alive(token)&&configured()){
        try{
          runConnection(token);
        }catch(SecurityException failure){
          lastFailure="Bluetooth permission: "+failure.getMessage();
          step(token,"PERMISIUNE BLUETOOTH");
          return;
        }catch(Exception failure){
          if(!alive(token))return;
          lastFailure=stage+": "+safe(failure.getMessage());
          clearValues();
          step(token,"EROARE "+stage);
          try{Thread.sleep(2200L);}catch(InterruptedException ignored){Thread.currentThread().interrupt();return;}
        }finally{
          BluetoothSocket socket=classic;classic=null;
          if(socket!=null)try{socket.close();}catch(IOException ignored){}
          ElmBleSerial session=ble;ble=null;
          if(session!=null)session.close();
        }
      }
    }finally{
      synchronized(this){workerActive=false;}
      // Explicitly restart a NEW requested generation; never stop the new
      // one from the old worker's finally block.
      if(running&&!closed&&epoch!=token&&configured())startPending();
    }
  }
  private synchronized void startPending(){
    if(workerActive||!running||closed||!configured())return;
    workerActive=true;
    final long token=epoch;
    io.execute(()->runWorker(token));
  }
  private void runConnection(long token)throws Exception{
    BluetoothAdapter adapter=BluetoothAdapter.getDefaultAdapter();
    if(adapter==null)throw new IOException("Android Bluetooth adapter missing");
    if(!adapter.isEnabled()){step(token,"ACTIVEAZĂ BLUETOOTH");running=false;return;}
    BluetoothDevice device=null;
    for(BluetoothDevice paired:adapter.getBondedDevices())
      if(paired.getAddress().equalsIgnoreCase(selectedMac)){device=paired;break;}
    boolean bleHint=preferences.getBoolean("elm327_ble_hint",false);
    if(device==null && bleHint){
      // BLE GATT usually needs discovery, but NOT Android Classic pairing.
      device=adapter.getRemoteDevice(selectedMac);
    }
    if(device==null){step(token,"ASOCIAZĂ ADAPTORUL / CAUTĂ BLE");running=false;return;}
    try{adapter.cancelDiscovery();}catch(RuntimeException ignored){}
    String pref=preferences.getString(KEY_MODE,"AUTO");
    boolean bleFirst="BLE".equals(pref)||bleHint||device.getType()==BluetoothDevice.DEVICE_TYPE_LE;
    IOException combined=null;
    for(int attempt=0;attempt<2&&alive(token);attempt++){
      boolean useBle=attempt==0?bleFirst:!bleFirst;
      if(device.getType()==BluetoothDevice.DEVICE_TYPE_LE&&!useBle)continue;
      try{
        final InputStream in;
        final OutputStream out;
        if(useBle){
          step(token,"BLE GATT • DESCOPERĂ UART");
          ElmBleSerial session=new ElmBleSerial(context,device);
          ble=session;
          session.connect();
          in=session.input();out=session.output();
          mode="BLE";
          step(token,"BLE • "+session.profile());
        }else{
          step(token,"BLUETOOTH CLASSIC • RFCOMM SPP");
          BluetoothSocket socket;
          try{
            socket=device.createRfcommSocketToServiceRecord(SPP);
            classic=socket;socket.connect();
          }catch(IOException secured){
            BluetoothSocket old=classic;classic=null;
            if(old!=null)try{old.close();}catch(IOException ignored){}
            if(!alive(token))return;
            step(token,"SPP COMPATIBILITATE");
            socket=device.createInsecureRfcommSocketToServiceRecord(SPP);
            classic=socket;socket.connect();
          }
          in=socket.getInputStream();out=socket.getOutputStream();mode="SPP";
        }
        if(!alive(token))return;
        step(token,"ATI • VERIFICĂ ELM");
        String identity;
        try{
          identity=command(in,out,"ATI",5000L,token);
        }catch(IOException initial){
          // One recovery reset only if the initial ATI failed. Do not hard
          // reset on every reconnect as the previous build did.
          step(token,"ATZ • RECUPERARE ELM");
          command(in,out,"ATZ",9000L,token);
          step(token,"ATI • DUPĂ RECUPERARE");
          identity=command(in,out,"ATI",5000L,token);
        }
        if(identity.trim().isEmpty()||identity.contains("?"))
          throw new IOException("ATI rejected: "+safe(identity));
        step(token,"INIȚIALIZARE ELM");
        command(in,out,"ATE0",3500L,token);
        command(in,out,"ATL0",3500L,token);
        command(in,out,"ATH0",3500L,token);
        try{command(in,out,"ATS0",3500L,token);}catch(IOException ignored){}
        command(in,out,"ATSP0",5500L,token);
        // A successful ATI + AT command dialogue proves the Bluetooth/GATT
        // transport. Remember it NOW, even when ignition is off and ECU
        // reports NO DATA; do not disconnect/reconnect endlessly.
        preferences.edit().putString(KEY_MODE,mode)
          .putBoolean("elm327_ble_hint","BLE".equals(mode)).commit();
        lastFailure="";
        step(token,"ADAPTOR CONECTAT • "+mode);
        String response=command(in,out,"0100",22000L,token);
        while(alive(token)&&
          !response.replaceAll("[^0-9A-F]","").toUpperCase(Locale.US).contains("4100")){
          lastFailure="Bluetooth "+mode+" funcțional; ECU răspunde: "+safe(response)+
            ". Verifică contactul/ELM.";
          step(token,"ELM CONECTAT • ECU NU RĂSPUNDE");
          Thread.sleep(2500L);
          if(!alive(token))return;
          response=command(in,out,"0100",8000L,token);
        }
        if(!alive(token))return;
        lastFailure="";
        try{command(in,out,"ATAT1",3500L,token);}catch(IOException ignored){}
        // ATAT1 learns ECU response time. Avoid forcing 100ms timeouts for
        // ISO/KWP vehicles: a 2008 Mitsubishi may not be CAN-only.
        // CAN can have a 200ms ceiling; non-CAN uses 400ms and adapts down.
        boolean canProtocol=false;
        try{
          String dpn=command(in,out,"ATDPN",3500L,token).toUpperCase(Locale.US)
            .replaceAll("[^0-9A-F]","");
          canProtocol=dpn.endsWith("6")||dpn.endsWith("7")||
            dpn.endsWith("8")||dpn.endsWith("9");
        }catch(IOException ignored){}
        try{command(in,out,canProtocol?"ATST32":"ATST64",3500L,token);}
        catch(IOException ignored){}
        // The link is already retained; now the ECU is confirmed available.
        lastFailure="";
        step(token,"ECU LIVE • "+mode);
        fastCounter=0;
        pollLoop(in,out,token);
        return;
      }catch(IOException failure){
        lastFailure=(useBle?"BLE":"SPP")+": "+safe(failure.getMessage());
        combined=failure;
        BluetoothSocket socket=classic;classic=null;
        if(socket!=null)try{socket.close();}catch(IOException ignored){}
        ElmBleSerial session=ble;ble=null;if(session!=null)session.close();
        if(useBle && device.getType()==BluetoothDevice.DEVICE_TYPE_LE)break;
      }
    }
    if(combined!=null)throw combined;
  }
  private void pollLoop(InputStream in,OutputStream out,long token)throws Exception{
    long lastCoolant=0,lastLtft=0,lastNotify=0,rateStart=SystemClock.elapsedRealtime();
    int completed=0;
    long nextAllowed=0;
    while(alive(token)){
      long now=SystemClock.elapsedRealtime();
      int[] requests=ObdPollPlan.next(now,lastCoolant,lastLtft);
      // Fast sensor requests are always first. One command outstanding.
      for(int i:requests){
        if(!alive(token))return;
        long pause=Math.max(0,nextAllowed-SystemClock.elapsedRealtime());
        if(pause>0)Thread.sleep(pause);
        long t0=SystemClock.elapsedRealtime();
        String data=command(in,out,String.format(Locale.US,"01%02X",pids[i]),
          3300L,token);
        long t1=SystemClock.elapsedRealtime();
        roundTripMs=t1-t0;completed++;
        float number=ObdPidCodec.parse(data,pids[i]);
        synchronized(values){
          values[i]=number;
          times[i]=Float.isFinite(number)?t1:0L;
        }
        if(i==2)lastCoolant=t1;
        if(i==3)lastLtft=t1;
        // Avoid blindly hammering ELM firmware; adapt to real response.
        nextAllowed=t1+ObdPollPlan.minimumGapMs(roundTripMs);
        if(t1-lastNotify>=85L){
          lastNotify=t1;notifyUI();
        }
      }
      long t=SystemClock.elapsedRealtime();
      if(t-rateStart>=1200L){
        ratePerSecond=(int)(completed*1000L/Math.max(1L,t-rateStart));
        completed=0;rateStart=t;
      }
      state="ELM327 • ECU LIVE • "+mode+" • "+ratePerSecond+" PID/s";
    }
  }
  private static String safe(String raw){
    if(raw==null)return "unknown";
    String flat=raw.replace('\r',' ').replace('\n',' ');
    return flat.length()>85?flat.substring(0,85):flat;
  }
  private String command(InputStream in,OutputStream out,String code,long timeout,long token)
      throws IOException,InterruptedException{
    if(!alive(token))throw new IOException("OBD stopped");
    // Only clear bytes from a previously completed command; do not read while
    // another request is outstanding. Prompt '>' terminates one response.
    int leftover=0;
    while(in.available()>0&&leftover++<1024)in.read();
    out.write((code+"\r").getBytes(StandardCharsets.US_ASCII));out.flush();
    ByteArrayOutputStream reply=new ByteArrayOutputStream(128);
    long deadline=SystemClock.elapsedRealtime()+timeout;
    while(alive(token)&&SystemClock.elapsedRealtime()<deadline){
      int size=in.available();
      if(size>0){
        for(int n=0;n<Math.min(size,512);n++){
          int ch=in.read();
          if(ch<0)throw new IOException("Transport closed");
          if(ch=='>')return reply.toString("US-ASCII");
          if(reply.size()>=8192)throw new IOException("ELM response too long");
          reply.write(ch);
        }
      }else Thread.sleep(8L);
    }
    if(!alive(token))throw new IOException("OBD stopped");
    throw new IOException("Timeout "+code+" waiting for ELM prompt");
  }
}
