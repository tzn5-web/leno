package ro.evolauncher.k2401;

import android.app.Application;
import android.content.SharedPreferences;
import android.os.Process;
import java.io.PrintWriter;
import java.io.StringWriter;

/**
 * Persist the actual Java exception from OEM Android 10 hardware.
 * No remote telemetry, no personal data upload, no MCU modifications.
 */
public final class EvoApplication extends Application {
  @Override public void onCreate(){
    super.onCreate();
    final Thread.UncaughtExceptionHandler previous=Thread.getDefaultUncaughtExceptionHandler();
    Thread.setDefaultUncaughtExceptionHandler((thread,error)->{
      try{
        StringWriter trace=new StringWriter();
        error.printStackTrace(new PrintWriter(trace));
        SharedPreferences preferences=getSharedPreferences("evo_startup_recovery",MODE_PRIVATE);
        preferences.edit().putString("last_exception",trace.toString())
          .putLong("last_crash_wallclock",System.currentTimeMillis())
          .putString("last_thread",thread.getName())
          .commit();
      }catch(Throwable ignored){}
      if(previous!=null)previous.uncaughtException(thread,error);
      else Process.killProcess(Process.myPid());
    });
  }
}
