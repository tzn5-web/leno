package ro.evolauncher.k2401;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Explicit always-available safe recovery entry point for OEM-only crashes. */
public final class SafeModeActivity extends Activity {
  private final int WHITE=0xffeaf1ff;
  private SharedPreferences data;
  @Override public void onCreate(Bundle savedState){
    super.onCreate(savedState);
    data=getSharedPreferences("evo_startup_recovery",MODE_PRIVATE);
    render();
  }
  private Button button(LinearLayout root,String label,Runnable run){
    Button b=new Button(this);b.setText(label);b.setAllCaps(false);
    root.addView(b,new LinearLayout.LayoutParams(-1,-2));
    b.setOnClickListener(v->run.run());return b;
  }
  private void render(){
    ScrollView scroll=new ScrollView(this);
    scroll.setBackgroundColor(0xff101925);
    LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);
    box.setPadding(35,35,35,40);
    scroll.addView(box);
    TextView h=new TextView(this);h.setText("K2401 EVO — RECUPERARE");
    h.setTextSize(25);h.setTextColor(WHITE);box.addView(h);
    TextView info=new TextView(this);
    info.setText("Acest ecran nu pornește harta sau Bluetooth. Poți recupera launcherul fără resetarea navigației.\n");
    info.setTextColor(WHITE);info.setTextSize(15);box.addView(info);
    button(box,"Pornește EVO fără conexiuni OBD",()->{
      getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE).edit()
        .putBoolean("evo_skip_obd_at_start",true).commit();
      data.edit().remove("last_crash_wallclock").commit();
      Intent intent=new Intent(this,MainActivity.class);
      intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP);
      startActivity(intent);finish();
    });
    button(box,"Pornește EVO cu harta și OBD dezactivate",()->{
      getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE).edit()
        .putBoolean("evo_skip_obd_at_start",true).commit();
      data.edit().remove("last_crash_wallclock").putBoolean("map_disabled",true)
        .putBoolean("map_boot_pending",false).commit();
      startActivity(new Intent(this,MainActivity.class));finish();
    });
    button(box,"Reîncearcă harta la următoarea pornire",()->{
      data.edit().remove("last_crash_wallclock").putBoolean("map_disabled",false)
        .putBoolean("map_boot_pending",false).commit();
      startActivity(new Intent(this,MainActivity.class));finish();
    });
    button(box,"Resetează doar alegerea adaptorului ELM327",()->{
      getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE).edit()
        .remove("elm327_mac").putString("obd_source","direct")
        .putBoolean("evo_skip_obd_at_start",true).commit();
      data.edit().remove("last_crash_wallclock").commit();
      render();
    });
    button(box,"Copiază diagnosticul",()->{
      ClipboardManager clipboard=(ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);
      if(clipboard!=null)clipboard.setPrimaryClip(ClipData.newPlainText("K2401 EVO crash",data.getString("last_exception","Nu există log Java salvat")));
    });
    button(box,"Încearcă pornirea normală",()->{
      getSharedPreferences("evo_launcher_prefs",MODE_PRIVATE).edit()
        .putBoolean("evo_skip_obd_at_start",false).commit();
      data.edit().remove("last_crash_wallclock").commit();
      startActivity(new Intent(this,MainActivity.class));finish();
    });
    TextView trace=new TextView(this);trace.setTextSize(12);trace.setTextColor(WHITE);
    trace.setText("ULTIMA EROARE JAVA:\n"+data.getString("last_exception",
      "Nicio excepție Java salvată. Dacă aplicația se închide în continuare, este necesar un logcat Android."));
    trace.setTextIsSelectable(true);box.addView(trace);
    setContentView(scroll);
  }
}
