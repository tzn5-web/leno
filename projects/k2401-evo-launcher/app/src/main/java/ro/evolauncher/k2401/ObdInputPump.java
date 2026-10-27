package ro.evolauncher.k2401;

import android.os.SystemClock;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;

/**
 * One blocking Bluetooth/ BLE serial reader, a bounded byte ring buffer,
 * and a prompt-framed response consumer. A flaky OEM InputStream.available()
 * is NEVER used to decide whether serial data exists.
 */
final class ObdInputPump implements AutoCloseable {
  private final InputStream source;
  private final Thread reader;
  private final Object lock=new Object();
  private final byte[] ring=new byte[16384];
  private int start,count;
  private boolean closed;
  private IOException failure;
  ObdInputPump(InputStream input){
    source=input;
    reader=new Thread(this::readWorker,"k2401-elm-serial-rx");
    reader.setDaemon(true);
    reader.start();
  }
  private void readWorker(){
    try{
      while(true){
        int ch=source.read();
        if(ch<0)throw new IOException("ELM socket closed");
        synchronized(lock){
          if(closed)return;
          if(count==ring.length){
            failure=new IOException("ELM serial receive overflow");
            lock.notifyAll();return;
          }
          ring[(start+count)%ring.length]=(byte)ch;
          count++;
          lock.notifyAll();
        }
      }
    }catch(IOException e){
      synchronized(lock){if(!closed){failure=e;lock.notifyAll();}}
    }catch(RuntimeException e){
      synchronized(lock){
        if(!closed){failure=new IOException("OEM serial reader: "+e.getMessage(),e);lock.notifyAll();}
      }
    }
  }
  void discardPriorResponse(){
    synchronized(lock){start=0;count=0;}
  }
  String untilPrompt(long timeoutMillis)throws IOException,InterruptedException{
    long deadline=SystemClock.elapsedRealtime()+timeoutMillis;
    ByteArrayOutputStream output=new ByteArrayOutputStream(128);
    synchronized(lock){
      while(true){
        while(count>0){
          int ch=ring[start]&255;
          start=(start+1)%ring.length;
          count--;
          if(ch=='>')return output.toString("US-ASCII");
          if(output.size()>=8192)throw new IOException("ELM response >8KB");
          output.write(ch);
        }
        if(failure!=null)throw failure;
        if(closed)throw new IOException("ELM receiver stopped");
        long remaining=deadline-SystemClock.elapsedRealtime();
        if(remaining<=0)throw new IOException("ELM serial prompt timeout after "+timeoutMillis+"ms");
        lock.wait(remaining);
      }
    }
  }
  @Override public void close(){
    synchronized(lock){closed=true;lock.notifyAll();}
    reader.interrupt();
    // The owner closes the SPP socket or BLE GATT transport, waking read().
  }
}
