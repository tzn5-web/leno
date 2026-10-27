package ro.evolauncher.k2401;

import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothProfile;
import android.content.Context;
import android.os.SystemClock;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayDeque;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * One selected ELM-compatible BLE UART. No unsolicited ECU writes and no
 * Bluetooth Classic calls. GATT notifications deliver response fragments to
 * a bounded serial byte queue. All connect, descriptor and write operations
 * are async; only the single OBD I/O worker may wait for their callbacks.
 *
 * Profiles: Nordic UART, FFF0, FFE0, vLinker 18F0, Vgate iCar Pro.
 * An unknown BLE device is never assumed to be an ELM327.
 */
final class ElmBleSerial implements AutoCloseable {
  private static final UUID CCCD=UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
  private static final UUID[][] PROFILES={
    {uuid16(0x18f0),uuid16(0x2af1),uuid16(0x2af0)}, // write, notify
    {uuid16(0xfff0),uuid16(0xfff2),uuid16(0xfff1)},
    {uuid16(0xffe0),uuid16(0xffe1),uuid16(0xffe1)},
    {UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9e"),
      UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9e"),
      UUID.fromString("6e400003-b5a3-f393-e0a9-e50e24dcca9e")},
    {UUID.fromString("e7810a71-73ae-499d-8c15-faa9aef0c3f2"),
      UUID.fromString("bef8d6c9-9c21-4c9e-b632-bd58c1009f9f"),
      UUID.fromString("bef8d6c9-9c21-4c9e-b632-bd58c1009f9f")}
  };
  private static UUID uuid16(int code) {
    return UUID.fromString(String.format(java.util.Locale.US,
      "0000%04x-0000-1000-8000-00805f9b34fb",code));
  }
  private final Context context;
  private final BluetoothDevice device;
  private final Object bufferLock=new Object();
  private final Object writeLock=new Object();
  private final ArrayDeque<Integer> receive=new ArrayDeque<>();
  private volatile BluetoothGatt gatt;
  private volatile BluetoothGattCharacteristic tx,rx;
  private volatile boolean closed,connected,ready;
  private volatile IOException failure;
  private volatile int mtu=23;
  private volatile String profile="BLE";
  private CountDownLatch connectedLatch=new CountDownLatch(1);
  private CountDownLatch servicesLatch=new CountDownLatch(1);
  private CountDownLatch notificationLatch=new CountDownLatch(1);
  private volatile CountDownLatch writeLatch;
  private volatile int writeStatus=BluetoothGatt.GATT_FAILURE;
  private final InputStream input=new InputStream(){
    @Override public int available() throws IOException {
      synchronized(bufferLock){
        if(failure!=null)throw failure;
        return receive.size();
      }
    }
    @Override public int read() throws IOException {
      synchronized(bufferLock){
        while(receive.isEmpty()){
          if(failure!=null)throw failure;
          if(closed)throw new IOException("BLE closed");
          try{bufferLock.wait(1000);}catch(InterruptedException interrupted){
            Thread.currentThread().interrupt();throw new IOException("BLE interrupted",interrupted);
          }
        }
        return receive.removeFirst();
      }
    }
  };
  private final OutputStream output=new OutputStream(){
    @Override public void write(int one) throws IOException{write(new byte[]{(byte)one},0,1);}
    @Override public void write(byte[] bytes,int offset,int length)throws IOException{
      synchronized(writeLock){
        int end=offset+length;
        while(offset<end){
          ensureReady();
          int size=Math.min(end-offset,Math.max(20,mtu-3));
          byte[] data=new byte[size];
          System.arraycopy(bytes,offset,data,0,size);
          BluetoothGattCharacteristic c=tx;
          if(c==null)throw new IOException("BLE write char missing");
          boolean acknowledged=(c.getProperties() & BluetoothGattCharacteristic.PROPERTY_WRITE)!=0;
          c.setWriteType(acknowledged ? BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT :
            BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
          CountDownLatch latch=new CountDownLatch(1);
          writeLatch=latch;
          c.setValue(data);
          BluetoothGatt session=gatt;
          if(session==null||!session.writeCharacteristic(c)){
            writeLatch=null;throw new IOException("BLE write request refused");
          }
          if(acknowledged){
            try{
              if(!latch.await(3500,TimeUnit.MILLISECONDS))throw new IOException("BLE write timeout");
            }catch(InterruptedException interrupt){
              Thread.currentThread().interrupt();throw new IOException("BLE write interrupted",interrupt);
            }
            if(writeStatus!=BluetoothGatt.GATT_SUCCESS)
              throw new IOException("BLE write status "+writeStatus);
          }else {
            // Without-response writes may not trigger callbacks on all Android 10
            // stacks. A short transport pacing delay prevents write-queue overflow.
            SystemClock.sleep(12);
          }
          offset+=size;
        }
      }
    }
  };
  private final BluetoothGattCallback callback=new BluetoothGattCallback(){
    @Override public void onConnectionStateChange(BluetoothGatt session,int status,int newState){
      if(closed)return;
      if(status==BluetoothGatt.GATT_SUCCESS&&newState==BluetoothProfile.STATE_CONNECTED){
        connected=true;connectedLatch.countDown();
        try{
          session.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH);
          if(!session.discoverServices())fail("BLE discoverServices refused");
        }catch(RuntimeException failure){fail("BLE discoverServices: "+failure.getMessage());}
      }else {
        connected=false;
        fail("BLE GATT link lost, status="+status+" state="+newState);
      }
    }
    @Override public void onServicesDiscovered(BluetoothGatt session,int status){
      if(status!=BluetoothGatt.GATT_SUCCESS){fail("BLE services status="+status);return;}
      try{
        for(int i=0;i<PROFILES.length;i++){
          UUID[] entry=PROFILES[i];
          BluetoothGattService service=session.getService(entry[0]);
          if(service==null)continue;
          BluetoothGattCharacteristic writer=service.getCharacteristic(entry[1]);
          BluetoothGattCharacteristic notifier=service.getCharacteristic(entry[2]);
          if(writer==null||notifier==null)continue;
          int writeMask=BluetoothGattCharacteristic.PROPERTY_WRITE|
            BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE;
          if((writer.getProperties()&writeMask)==0)continue;
          if((notifier.getProperties()&(BluetoothGattCharacteristic.PROPERTY_NOTIFY|
             BluetoothGattCharacteristic.PROPERTY_INDICATE))==0)continue;
          tx=writer;rx=notifier;profile="BLE "+entry[0].toString();
          servicesLatch.countDown();
          if(!session.setCharacteristicNotification(notifier,true)){
            fail("BLE enable notifications refused");return;
          }
          BluetoothGattDescriptor cccd=notifier.getDescriptor(CCCD);
          if(cccd==null){
            fail("BLE notification CCCD missing");return;
          }
          byte[] value=(notifier.getProperties()&BluetoothGattCharacteristic.PROPERTY_NOTIFY)!=0?
            BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE:
            BluetoothGattDescriptor.ENABLE_INDICATION_VALUE;
          cccd.setValue(value);
          if(!session.writeDescriptor(cccd)){fail("BLE descriptor write refused");return;}
          return;
        }
        fail("BLE ELM UART service not found (supported: 18F0, FFF0, FFE0, NUS, Vgate)");
      }catch(RuntimeException error){fail("BLE GATT services: "+error.getMessage());}
    }
    @Override public void onDescriptorWrite(BluetoothGatt session,BluetoothGattDescriptor desc,int status){
      if(status!=BluetoothGatt.GATT_SUCCESS){fail("BLE CCCD status "+status);return;}
      // Short OBD ASCII commands fit the default 23-byte MTU. Do not start
      // an overlapping MTU request just before the first UART write on OEM GATT.
      ready=true;notificationLatch.countDown();
    }
    @Override public void onMtuChanged(BluetoothGatt session,int size,int status){
      if(status==BluetoothGatt.GATT_SUCCESS)mtu=size;
    }
    @Override public void onCharacteristicChanged(BluetoothGatt session,BluetoothGattCharacteristic c){
      byte[] bytes=c.getValue();
      if(rx!=null&&c.getUuid().equals(rx.getUuid())&&bytes!=null){
        synchronized(bufferLock){
          if(receive.size()+bytes.length>8192){fail("BLE notification buffer overflow");return;}
          for(byte item:bytes)receive.addLast(item&255);
          bufferLock.notifyAll();
        }
      }
    }
    @Override public void onCharacteristicWrite(BluetoothGatt session,BluetoothGattCharacteristic c,int status){
      writeStatus=status;
      CountDownLatch latch=writeLatch;
      if(latch!=null)latch.countDown();
    }
  };
  ElmBleSerial(Context context,BluetoothDevice device){
    this.context=context.getApplicationContext();this.device=device;
  }
  String profile(){return profile;}
  InputStream input(){return input;}
  OutputStream output(){return output;}
  boolean isConnected(){return connected&&ready&&!closed&&failure==null;}
  void connect()throws IOException {
    try{
      gatt=device.connectGatt(context,false,callback,BluetoothDevice.TRANSPORT_LE);
      if(gatt==null)throw new IOException("BLE connectGatt returned null");
      if(!connectedLatch.await(11000,TimeUnit.MILLISECONDS))throw new IOException("BLE connection timed out");
      if(!servicesLatch.await(10000,TimeUnit.MILLISECONDS))throw new IOException("BLE UART service discovery timeout");
      if(!notificationLatch.await(7000,TimeUnit.MILLISECONDS))throw new IOException("BLE notification subscription timeout");
      ensureReady();
    }catch(InterruptedException error){
      Thread.currentThread().interrupt();throw new IOException("BLE connect interrupted",error);
    }catch(SecurityException error){throw new IOException("BLE security permission",error);}
    catch(RuntimeException error){throw new IOException("BLE GATT unavailable: "+error.getMessage(),error);}
    finally{if(!isConnected())close();}
  }
  private void ensureReady()throws IOException {
    if(closed)throw new IOException("BLE closed");
    if(failure!=null)throw failure;
    if(!ready)throw new IOException("BLE notifications not ready");
  }
  private void fail(String reason){
    if(failure==null)failure=new IOException(reason);
    connectedLatch.countDown();servicesLatch.countDown();notificationLatch.countDown();
    CountDownLatch latch=writeLatch;if(latch!=null)latch.countDown();
    synchronized(bufferLock){bufferLock.notifyAll();}
  }
  @Override public void close(){
    closed=true;ready=false;
    synchronized(bufferLock){bufferLock.notifyAll();}
    CountDownLatch latch=writeLatch;if(latch!=null)latch.countDown();
    BluetoothGatt session=gatt;gatt=null;
    if(session!=null){
      try{session.disconnect();}catch(RuntimeException ignored){}
      try{session.close();}catch(RuntimeException ignored){}
    }
  }
}
