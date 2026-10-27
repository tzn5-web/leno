package ro.evolauncher.k2401;

import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;

/** Real, user-configurable app shortcuts; no hardcoded decorative fake icons. */
final class ShortcutDock extends HorizontalScrollView {
  private static final String KEY="dock_pins_v1";
  private final MainActivity host;
  private final PackageManager pm;
  private final SharedPreferences prefs;
  private final LinearLayout row;
  private final ArrayList<String> pins=new ArrayList<>();
  ShortcutDock(MainActivity activity){
    super(activity);host=activity;pm=activity.getPackageManager();
    prefs=activity.getSharedPreferences("evo_launcher_prefs",Context.MODE_PRIVATE);
    setHorizontalScrollBarEnabled(false);setFillViewport(true);
    GradientDrawable bg=new GradientDrawable();bg.setColor(0xe20b111b);bg.setCornerRadius(dp(16));bg.setStroke(dp(1),0xff693040);
    setBackground(bg);setPadding(dp(9),dp(7),dp(9),dp(5));
    row=new LinearLayout(activity);row.setOrientation(LinearLayout.HORIZONTAL);
    addView(row,new LayoutParams(-2,-1));load();render();
  }
  private int dp(float x){return (int)(x*getResources().getDisplayMetrics().density+0.5f);}
  private void load(){
    pins.clear();String saved=prefs.getString(KEY,null);
    if(saved!=null){for(String part:saved.split(","))if(!part.isEmpty()&&!pins.contains(part))pins.add(part);}
    else{String[] defaults={"com.google.android.apps.maps","com.google.android.apps.youtube.music","org.prowl.torque","com.android.chrome"};
      for(String pkg:defaults)if(pm.getLaunchIntentForPackage(pkg)!=null)pins.add(pkg);
      persist();
    }
  }
  private void persist(){prefs.edit().putString(KEY,TextUtils.join(",",pins)).apply();}
  private String label(String pkg){try{return pm.getApplicationLabel(pm.getApplicationInfo(pkg,0)).toString();}catch(Exception ex){return pkg;}}
  private LinearLayout tile(String caption){
    LinearLayout cell=new LinearLayout(host);cell.setOrientation(LinearLayout.VERTICAL);cell.setGravity(Gravity.CENTER);
    LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(dp(96),-1);cp.setMargins(dp(3),0,dp(3),0);row.addView(cell,cp);
    TextView name=new TextView(host);name.setText(caption);name.setTextColor(Color.WHITE);name.setTextSize(12);
    name.setGravity(Gravity.CENTER);name.setMaxLines(1);name.setEllipsize(TextUtils.TruncateAt.END);
    ImageView icon=new ImageView(host);icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
    LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(dp(53),dp(53));ip.bottomMargin=dp(7);
    cell.addView(icon,ip);cell.addView(name,new LinearLayout.LayoutParams(-1,dp(25)));
    cell.setTag(icon);return cell;
  }
  private void render(){
    row.removeAllViews();
    for(int i=0;i<pins.size();i++){
      final int index=i;String pkg=pins.get(i);LinearLayout cell=tile(label(pkg));
      ImageView icon=(ImageView)cell.getTag();
      try{icon.setImageDrawable(pm.getApplicationIcon(pkg));}catch(Exception ex){icon.setImageDrawable(pm.getDefaultActivityIcon());}
      cell.setContentDescription("Pin "+label(pkg));
      cell.setOnClickListener(v->host.app(pkg));
      cell.setOnLongClickListener(v->{options(index);return true;});
    }
    LinearLayout add=tile("Adaugă");TextView plus=new TextView(host);plus.setText("+");plus.setTextColor(0xfff5f6f9);
    plus.setTextSize(40);plus.setGravity(Gravity.CENTER);
    ImageView placeholder=(ImageView)add.getTag();int pos=add.indexOfChild(placeholder);
    add.removeView(placeholder);add.addView(plus,pos,new LinearLayout.LayoutParams(dp(53),dp(53)));
    add.setContentDescription("Adaugă aplicație");add.setOnClickListener(v->choose(-1));
  }
  private void options(int index){
    new AlertDialog.Builder(host).setTitle(label(pins.get(index))).setItems(
      new String[]{"Schimbă aplicația","Mută la stânga","Mută la dreapta","Elimină"},
      (dialog,which)->{
        if(which==0){choose(index);return;}
        if(which==3){pins.remove(index);}
        else if(which==1&&index>0)Collections.swap(pins,index,index-1);
        else if(which==2&&index<pins.size()-1)Collections.swap(pins,index,index+1);
        persist();render();
      }).setNegativeButton("Anulează",null).show();
  }
  private void choose(int replaceIndex){
    Intent launcher=new Intent(Intent.ACTION_MAIN);launcher.addCategory(Intent.CATEGORY_LAUNCHER);
    List<ResolveInfo> found=pm.queryIntentActivities(launcher,0);
    ArrayList<String> packages=new ArrayList<>();HashSet<String> seen=new HashSet<>();
    for(ResolveInfo info:found){
      if(info.activityInfo==null)continue;
      String pkg=info.activityInfo.packageName;
      if(pkg.equals(host.getPackageName())||!seen.add(pkg)||pm.getLaunchIntentForPackage(pkg)==null)continue;
      packages.add(pkg);
    }
    Collections.sort(packages,(a,b)->label(a).compareToIgnoreCase(label(b)));
    if(packages.isEmpty()){new AlertDialog.Builder(host).setMessage("Nu există aplicații lansabile instalate.").setPositiveButton("OK",null).show();return;}
    String[] names=new String[packages.size()];
    for(int i=0;i<packages.size();i++)names[i]=label(packages.get(i));
    final int[] replaceIndexHolder={replaceIndex};
    new AlertDialog.Builder(host).setTitle("Alege aplicația").setItems(names,(dialog,which)->{
      String pkg=packages.get(which);int previous=pins.indexOf(pkg);
      if(previous>=0&&previous!=replaceIndex){pins.remove(previous);if(replaceIndex>previous)replaceIndexHolder[0]--;}
      int slot=replaceIndexHolder[0];if(slot<0||slot>=pins.size())pins.add(pkg);else pins.set(slot,pkg);
      persist();render();
    }).setNegativeButton("Anulează",null).show();
  }
}
