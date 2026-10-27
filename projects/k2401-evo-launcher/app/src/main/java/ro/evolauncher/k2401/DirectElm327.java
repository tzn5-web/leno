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
 * Direct read-only ELM327 Bluetooth Classic SPP client. Does NOT require Torque
 * Pro, an unofficial Torque clone, or a plugin. Does NOT send ECU writes:
 * Mode 01 (current sensor data) only; AT commands configure the ELM adapter.
 *
 * Only the explicitly paired and saved adapter MAC is used. Never auto-connect
 * to random bonded devices. Never share one SPP socket with another app.
 */
final class DirectElm327 {
  private static final UUID SPP=UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");
  private static final String PREFS="evo_launcher_prefs", KEY="elm327_mac";
  private final SharedPreferences preferences;
  private final Handler ui=new Handler(Looper.getMainLooper());
  private final ExecutorService io=Executors.newSingleThreadExecutor();
  private final Runnable onUpdate;
  private volatile boolean running, closed;
  private volatile BluetoothSocket socket;
  private volatile ObdReader.Reading sample=ObdReader.Reading.empty();
  private volatile String status="ELM327 • ALEGE ADAPTORUL";
  private volatile String selectedMac="";
  private volatile long epoch;
  private volatile boolean connectionBusy;

  DirectElm327(Context context,Runnable callback) {
    preferences=context.getApplicationContext().getSharedPreferences(PREFS,Context.MODE_PRIVATE);
    onUpdate=callback;
    selectedMac=preferences.getString(KEY,"");
  }
  boolean configured(){return selectedMac!=null&&!selectedMac.isEmpty();}
  String adapterAddress(){return selectedMac;}
  void selectAdapter(String mac){
    stop();
    if(mac==null)mac="";
    if(!mac.isEmpty()&&!BluetoothAdapter.checkBluetoothAddress(mac))
      throw new IllegalArgumentException("MAC ELM327 invalid");
    selectedMac=mac;
    preferences.edit().putString(KEY,mac).commit();
    sample=ObdReader.Reading.empty();
    status=mac.isEmpty()?"ELM327 • ALEGE ADAPTORUL":"ELM327 • CONFIGURAT";
    publish();
  }
  ObdReader.Reading current(){
    ObdReader.Reading value=sample;
    return value.live&&SystemClock.elapsedRealtime()-value.capturedAtMs>7000L?
      ObdReader.Reading.empty():value;
  }
  String status(){return status;}
  void start(){
    if(closed||running)return;
    running=true;
    long token=++epoch;
    if(!configured()){status="ELM327 • ALEGE ADAPTORUL";publish();return;}
    if(connectionBusy)return;
    connectionBusy=true;
    io.execute(()->loop(token));
  }
  void stop(){
    running=false;++epoch;
    BluetoothSocket old=socket;socket=null;
    if(old!=null)try{old.close();}catch(IOException ignored){}
    sample=ObdReader.Reading.empty();status="ELM327 • OPRIT";publish();
  }
  void close(){closed=true;stop();io.shutdownNow();}
  private boolean alive(long token){return running&&!closed&&epoch==token;}
  private void publish(){ui.post(onUpdate);}
  private void state(long token,String value){
    if(!alive(token))return;
    status=value;publish();
  }
  private void loop(long token){
    try{
      while(alive(token)&&configured()){
        BluetoothSocket link=null;
        try{
          BluetoothAdapter adapter=BluetoothAdapter.getDefaultAdapter();
          if(adapter==null){state(token,"ELM327 • FĂRĂ BLUETOOTH");return;}
          if(!adapter.isEnabled()){state(token,"ELM327 • ACTIVEAZĂ BLUETOOTH");return;}
          BluetoothDevice device=null;
          for(BluetoothDevice d:adapter.getBondedDevices())
            if(d.getAddress().equalsIgnoreCase(selectedMac)){device=d;break;}
          if(device==null){state(token,"ELM327 • ASOCIAZĂ ÎN BLUETOOTH");return;}
          state(token,"ELM327 • CONECTARE Bluetooth SPP");
          try{
            link=device.createRfcommSocketToServiceRecord(SPP);
            socket=link;link.connect();
          }catch(IOException secureFailure){
            if(link!=null)try{link.close();}catch(IOException ignored){}
            if(!alive(token))return;
            link=device.createInsecureRfcommSocketToServiceRecord(SPP);
            socket=link;link.connect();
          }
          if(!alive(token))return;
          state(token,"ELM327 • INIȚIALIZARE ADAPTOR");
          InputStream input=link.getInputStream();
          OutputStream output=link.getOutputStream();
          // Only ELM adapter setup commands. These do not alter ECU state.
          command(input,output,"ATZ",5000L,token);
          command(input,output,"ATE0",3500L,token);
          command(input,output,"ATL0",3500L,token);
          command(input,output,"ATS0",3500L,token);
          command(input,output,"ATH0",3500L,token);
          command(input,output,"ATSP0",5000L,token);
          state(token,"ELM327 • INTEROGHEZ ECU");
          int emptyScans=0;
          while(alive(token)){
            // Each value is replaced per scan; old or disconnected values are NOT retained.
            float stft=Float.NaN,ltft=Float.NaN,rpm=Float.NaN,coolant=Float.NaN;
            String s06=command(input,output,"0106",3500L,token);
            stft=parse(s06,0x06);
            String s07=command(input,output,"0107",3500L,token);
            ltft=parse(s07,0x07);
            String s0c=command(input,output,"010C",3500L,token);
            rpm=parse(s0c,0x0C);
            String s05=command(input,output,"0105",3500L,token);
            coolant=parse(s05,0x05);
            if(!alive(token))return;
            boolean live=Float.isFinite(stft)||Float.isFinite(ltft)||
              Float.isFinite(rpm)||Float.isFinite(coolant);
            sample=new ObdReader.Reading(rpm,stft,ltft,coolant,live);
            status=live?"ELM327 • ECU LIVE":"ELM327 • ECU FĂRĂ DATE";
            publish();
            if(!live){emptyScans++;if(emptyScans>2)state(token,"ELM327 • ECU NU RĂSPUNDE");}
            else emptyScans=0;
            Thread.sleep(250);
          }
        }catch(SecurityException e){state(token,"ELM327 • PERMISIUNE BLUETOOTH");return;}
        catch(Exception e){
          if(!alive(token))return;
          sample=ObdReader.Reading.empty();
          String msg=e instanceof IOException?"ELM327 • CONEXIUNE PIERDUTĂ":"ELM327 • EROARE ADAPTOR";
          state(token,msg+" (verifică să nu fie ocupat de Torque)");
          try{Thread.sleep(5000);}catch(InterruptedException interrupted){Thread.currentThread().interrupt();return;}
        }finally{
          if(link!=null)try{link.close();}catch(IOException ignored){}
          if(socket==link)socket=null;
        }
      }
    }finally{
      connectionBusy=false;
      // A pause/resume may happen while the old socket is stopping.
      // Restart safely for a newly selected adapter only if no worker is active.
      if(running&&!closed&&token!=epoch&&configured()){stop();start();}
    }
  }
  private String command(InputStream input,OutputStream output,String cmd,long timeout,long token)
      throws IOException,InterruptedException {
    if(!alive(token))throw new IOException("OBD stopped");
    // Drain leftovers from the previous response, bounded to prevent a blocking call.
    int extra=0;
    while(input.available()>0&&extra++<2048)input.read();
    output.write((cmd+"\r").getBytes(StandardCharsets.US_ASCII));output.flush();
    ByteArrayOutputStream reply=new ByteArrayOutputStream(256);
    long deadline=SystemClock.elapsedRealtime()+timeout;
    while(alive(token)&&SystemClock.elapsedRealtime()<deadline){
      int available=input.available();
      if(available>0){
        for(int i=0;i<Math.min(available,512);i++){
          int ch=input.read();
          if(ch<0)throw new IOException("ELM disconnected");
          if(ch=='>')return reply.toString("US-ASCII");
          if(reply.size()<8192)reply.write(ch);
          else throw new IOException("ELM oversized reply");
        }
      }else Thread.sleep(25);
    }
    if(!alive(token))throw new IOException("OBD stopped");
    // A missing prompt is never accepted as a fresh ECU response.
    throw new IOException("ELM timeout "+cmd);
  }

  /**
   * Decode only a matching ECU Mode 01 response (41 + requested PID).
   * Understands "41 0C 1A F8" and compact "410C1AF8".
   * Never treats NO DATA, command echo, or a mismatched PID as a reading.
   */
  static float parse(String raw,int pid){
    if(raw==null||raw.length()>8192)return Float.NaN;
    String wanted=String.format(Locale.US,"41%02X",pid);
    for(String line:raw.toUpperCase(Locale.US).split("[\\r\\n]+")){
      if(line.contains("NO DATA")||line.contains("UNABLE")||
          line.contains("ERROR")||line.contains("STOPPED")||line.contains("BUS INIT"))continue;
      String hex=line.replaceAll("[^0-9A-F]","");
      int at=hex.indexOf(wanted);
      if(at<0)continue;
      int dataAt=at+wanted.length();
      int needed=pid==0x0C?4:2;
      if(dataAt+needed>hex.length())continue;
      try{
        int a=Integer.parseInt(hex.substring(dataAt,dataAt+2),16);
        int b=pid==0x0C?Integer.parseInt(hex.substring(dataAt+2,dataAt+4),16):0;
        float result;
        switch(pid){
          case 0x06:case 0x07:result=(a-128)*100f/128f;break;
          case 0x0C:result=(256*a+b)/4f;break;
          case 0x05:result=a-40;break;
          default:return Float.NaN;
        }
        float low=pid==0x0C?0:pid==0x05?-40:-100;
        float high=pid==0x0C?12000:pid==0x05?170:100;
        if(result>=low&&result<=high)return result;
      }catch(NumberFormatException ignored){}
    }
    return Float.NaN;
  }
}
