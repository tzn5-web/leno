package ro.evolauncher.k2401;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.os.Handler;
import android.os.Looper;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.LinkedHashMap;

/**
 * Android 10 Bluetooth Classic DISCOVERY + pairing for the common OBDII/ELM327
 * serial adapters. BLE advertisements are a different transport: an empty BLE
 * scan MUST NOT be interpreted as "no OBD adapter".
 * Explicit human selection only; never connects to random nearby BT devices.
 */
final class ClassicObdDiscovery {
  interface Selected { void onDevice(String address); }
  private final Activity activity;
  private final Selected selected;
  private final Handler handler=new Handler(Looper.getMainLooper());
  private final LinkedHashMap<String,BluetoothDevice> found=new LinkedHashMap<>();
  private BluetoothAdapter adapter;
  private boolean registered,finished,waitingBond;
  private BluetoothDevice pending;
  private Runnable timeout;
  private BroadcastReceiver receiver;
  private android.app.ProgressDialog progress;

  ClassicObdDiscovery(Activity activity,Selected onSelected){
    this.activity=activity;this.selected=onSelected;
  }

  void begin(){
    if(activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED){
      new AlertDialog.Builder(activity).setTitle("Căutare ELM327 Bluetooth Classic")
        .setMessage("Android 10 necesită permisiunea de locație pentru a descoperi dispozitive Bluetooth. Acordă permisiunea și reîncearcă.")
        .setPositiveButton("Permisiune",(d,w)->activity.requestPermissions(
          new String[]{Manifest.permission.ACCESS_FINE_LOCATION},2410))
        .setNegativeButton("Închide",null).show();
      return;
    }
    adapter=BluetoothAdapter.getDefaultAdapter();
    if(adapter==null||!adapter.isEnabled()){
      explain("Bluetooth Android nu este activ. Unele navigații au un modul MCU pentru apeluri telefonice care nu oferă Bluetooth Serial Port Profile aplicațiilor Android.");
      return;
    }
    found.clear();
    try{
      for(BluetoothDevice device:adapter.getBondedDevices()){
        if(device.getAddress()!=null)found.put(device.getAddress(),device);
      }
      receiver=new BroadcastReceiver(){
        @Override public void onReceive(Context ctx,Intent intent){
          if(finished)return;
          String action=intent.getAction();
          if(BluetoothDevice.ACTION_FOUND.equals(action)){
            BluetoothDevice device=intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
            if(device!=null&&device.getAddress()!=null&&found.size()<60){
              found.put(device.getAddress(),device);
              if(progress!=null)progress.setMessage("Dispozitive Classic: "+found.size()+
                ". Caut OBDII / ELM327 / V-LINK ...");
            }
          }else if(BluetoothAdapter.ACTION_DISCOVERY_FINISHED.equals(action)&&!waitingBond){
            finishScan();
          }else if(BluetoothDevice.ACTION_BOND_STATE_CHANGED.equals(action)&&waitingBond){
            BluetoothDevice bonded=intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
            if(bonded!=null&&pending!=null&&
                pending.getAddress().equalsIgnoreCase(bonded.getAddress())){
              int state=intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE,BluetoothDevice.ERROR);
              if(state==BluetoothDevice.BOND_BONDED){
                String address=pending.getAddress();
                cleanup();selected.onDevice(address);
              }else if(state==BluetoothDevice.BOND_NONE){
                cleanup();explain("Asocierea Bluetooth nu a reușit. Încearcă PIN 1234 sau 0000 în dialogul Android.");
              }
            }
          }
        }
      };
      IntentFilter filter=new IntentFilter();
      filter.addAction(BluetoothDevice.ACTION_FOUND);
      filter.addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED);
      filter.addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED);
      activity.registerReceiver(receiver,filter);registered=true;
      try{adapter.cancelDiscovery();}catch(RuntimeException ignored){}
      progress=new android.app.ProgressDialog(activity);
      progress.setTitle("ELM327 Bluetooth Classic");
      progress.setMessage("Caut dispozitive RFCOMM/SPP timp de 15 secunde...");
      progress.setCancelable(true);
      progress.setOnCancelListener(d->finishScan());
      progress.show();
      boolean started=adapter.startDiscovery();
      if(!started){
        finishScan();
        explain("Firmware-ul nu permite scanare Bluetooth Classic prin API-ul Android. Încearcă Setări Bluetooth; dacă nici acolo nu apare ELM327, Bluetooth-ul poate fi gestionat exclusiv de MCU.");
        return;
      }
      timeout=()->finishScan();
      handler.postDelayed(timeout,15000);
    }catch(RuntimeException error){
      cleanup();
      explain("Scanarea Bluetooth Classic a eșuat: "+error.getClass().getSimpleName()+
        ". Modulul BT al navigației poate să nu accepte scanarea Android.");
    }
  }
  private void finishScan(){
    if(finished||waitingBond)return;
    if(timeout!=null){handler.removeCallbacks(timeout);timeout=null;}
    try{if(adapter!=null)adapter.cancelDiscovery();}catch(RuntimeException ignored){}
    if(progress!=null){progress.dismiss();progress=null;}
    if(found.isEmpty()){
      cleanup();
      explain("Android nu vede dispozitive Bluetooth Classic, nici asociate, nici detectate. Verifică adaptorul alimentat și asocierea din Setări Bluetooth. Dacă Torque pe telefon îl vede, dar navigația nu, poate fi o limitare hardware/MCU a navigației.");
      return;
    }
    final ArrayList<BluetoothDevice> devices=new ArrayList<>(found.values());
    String[] names=new String[devices.size()];
    for(int i=0;i<devices.size();i++){
      BluetoothDevice d=devices.get(i);
      String name;
      try{name=d.getName();}catch(RuntimeException ex){name=null;}
      if(name==null||name.trim().isEmpty())name="Dispozitiv BT Classic";
      names[i]=name+" • "+d.getAddress()+
        (d.getBondState()==BluetoothDevice.BOND_BONDED?" (asociat)":" (de asociat)");
    }
    new AlertDialog.Builder(activity).setTitle("ELM327 Bluetooth Classic — alege adaptorul")
      .setItems(names,(dlg,index)->choose(devices.get(index)))
      .setNegativeButton("Anulează",(dlg,which)->cleanup())
      .setOnCancelListener(dlg->cleanup()).show();
  }
  private void choose(BluetoothDevice device){
    try{
      if(device.getBondState()==BluetoothDevice.BOND_BONDED){
        String mac=device.getAddress();cleanup();selected.onDevice(mac);return;
      }
      pending=device;waitingBond=true;
      progress=new android.app.ProgressDialog(activity);
      progress.setTitle("Asociere Bluetooth Classic");
      progress.setMessage("Confirmă dialogul Android (PIN uzual 1234 sau 0000)...");
      progress.setCancelable(true);
      progress.setOnCancelListener(d->cleanup());
      progress.show();
      boolean ok=device.createBond();
      if(!ok){cleanup();explain("Android a refuzat cererea de asociere. Asociază dispozitivul din Setări Bluetooth.");return;}
      timeout=()->{
        if(waitingBond&&!finished){
          cleanup();explain("Asocierea nu s-a confirmat în 30 de secunde. Folosește Setări Bluetooth pentru asociere.");
        }
      };
      handler.postDelayed(timeout,30000);
    }catch(RuntimeException error){
      cleanup();explain("Asocierea a eșuat: "+error.getMessage());
    }
  }
  private void cleanup(){
    finished=true;
    if(timeout!=null){handler.removeCallbacks(timeout);timeout=null;}
    try{if(adapter!=null)adapter.cancelDiscovery();}catch(RuntimeException ignored){}
    if(registered){try{activity.unregisterReceiver(receiver);}catch(IllegalArgumentException ignored){}registered=false;}
    if(progress!=null){progress.dismiss();progress=null;}
  }
  private void explain(String message){
    if(activity.isFinishing())return;
    new AlertDialog.Builder(activity).setTitle("Diagnostic Bluetooth Classic")
      .setMessage(message).setPositiveButton("Închide",null)
      .setNeutralButton("Setări Bluetooth",(dialog,which)->{
        try{activity.startActivity(new Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS));}
        catch(RuntimeException error){Toast.makeText(activity,"Setări Bluetooth indisponibile",Toast.LENGTH_LONG).show();}
      }).show();
  }
}
