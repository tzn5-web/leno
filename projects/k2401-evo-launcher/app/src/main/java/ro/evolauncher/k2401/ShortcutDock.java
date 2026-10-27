package ro.evolauncher.k2401;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.Drawable;
import android.view.Gravity;
import android.view.View;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;

/** Configurable Home shortcut dock: native Android icons, persisted order and safe launch intents. */
final class ShortcutDock extends HorizontalScrollView {
  private static final String PREF="evo_launcher_prefs", KEY="shortcut_packages_v1";
  private final Activity host;
  private final SharedPreferences prefs;
  private final PackageManager pm;
  private final ArrayList<String> packages=new ArrayList<>();
  private final LinearLayout bar;
  private final int white=Color.WHITE, muted=0xffa1abb9, accent=0xffe92742;

  ShortcutDock(Activity activity){
    super(activity);host=activity;pm=activity.getPackageManager();
    prefs=activity.getSharedPreferences(PREF,Context.MODE_PRIVATE);
    setHorizontalScrollBarEnabled(false);setFillViewport(false);
    GradientDrawable background=new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
       new int[]{0xf9151921,0xff070b10});
    background.setCornerRadius(dp(17));background.setStroke(dp(1),0xff393741);
    setBackground(background);
    bar=new LinearLayout(activity);bar.setOrientation(LinearLayout.HORIZONTAL);
    bar.setGravity(Gravity.CENTER_VERTICAL);bar.setPadding(dp(8),0,dp(8),0);
    addView(bar,new LayoutParams(-2,-1));
    load();redraw();
  }
  private int dp(float n){return (int)(n*getResources().getDisplayMetrics().density+0.5f);}
  private void load(){
    packages.clear();
    String saved=prefs.getString(KEY,null);
    if(saved==null){
      Collections.addAll(packages,"com.google.android.apps.maps","com.google.android.dialer",
       "com.google.android.youtube","com.spotify.music","com.android.chrome");
    }else{
      String[] parts=saved.split("\\|",-1);
      for(String s:parts)if(!s.isEmpty()&&!packages.contains(s))packages.add(s);
    }
  }
  private void save(){StringBuilder b=new StringBuilder();for(String s:packages){if(b.length()>0)b.append('|');b.append(s);}prefs.edit().putString(KEY,b.toString()).apply();redraw();}
  void refresh(){redraw();}
  private TextView text(String s,int size,int color){
    TextView v=new TextView(host);v.setText(s);v.setTextColor(color);v.setTextSize(size);
    v.setGravity(Gravity.CENTER);v.setSingleLine(true);v.setEllipsize(android.text.TextUtils.TruncateAt.END);return v;
  }
  private void redraw(){
    bar.removeAllViews();
    for(int i=0;i<packages.size();i++)addTile(i,false);
    addTile(packages.size(),true);
  }
  private void addTile(int index,boolean plus){
    String pkg=plus?"":packages.get(index);
    Intent launch=plus?null:pm.getLaunchIntentForPackage(pkg);
    LinearLayout tile=new LinearLayout(host);tile.setOrientation(LinearLayout.VERTICAL);tile.setGravity(Gravity.CENTER);
    LinearLayout.LayoutParams tileParams=new LinearLayout.LayoutParams(dp(97),-1);tileParams.setMargins(dp(2),0,dp(2),0);
    bar.addView(tile,tileParams);
    if(plus||launch==null){
      TextView add=text("+",32,plus?white:muted);
      GradientDrawable bg=new GradientDrawable();bg.setColor(0xff222a36);bg.setCornerRadius(dp(14));
      bg.setStroke(dp(1),plus?accent:0xff38404b);
      add.setBackground(bg);tile.addView(add,new LinearLayout.LayoutParams(dp(50),dp(50)));
    }else{
      ImageView image=new ImageView(host);
      try{Drawable drawable=pm.getApplicationIcon(pkg);image.setImageDrawable(drawable);}catch(PackageManager.NameNotFoundException ignored){}
      image.setScaleType(ImageView.ScaleType.FIT_CENTER);
      tile.addView(image,new LinearLayout.LayoutParams(dp(50),dp(50)));
    }
    String label=plus?"Adaugă":"Aplicație";
    if(!plus&&launch!=null){try{label=pm.getApplicationLabel(pm.getApplicationInfo(pkg,0)).toString();}catch(PackageManager.NameNotFoundException ignored){}}
    TextView caption=text(label,12,white);
    LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(dp(90),dp(29));lp.topMargin=dp(4);
    tile.addView(caption,lp);
    tile.setContentDescription(plus?"Adaugă scurtătură":label+". Apasă lung pentru editare");
    tile.setOnClickListener(v->{if(plus)choose(-1);else launch(pkg);});
    if(!plus)tile.setOnLongClickListener(v->{edit(index);return true;});
  }
  private void launch(String pkg){
    Intent i=pm.getLaunchIntentForPackage(pkg);
    if(i==null){Toast.makeText(host,"Aplicația nu este instalată. Apasă lung pentru schimbare.",Toast.LENGTH_LONG).show();return;}
    try{host.startActivity(i);}catch(RuntimeException e){Toast.makeText(host,"Nu se poate deschide aplicația.",Toast.LENGTH_LONG).show();}
  }
  private void edit(int index){
    final String[] options={"Schimbă aplicația","Mută la stânga","Mută la dreapta","Elimină pinul"};
    new AlertDialog.Builder(host).setTitle("Personalizează pinul")
      .setItems(options,(d,which)->{
        if(which==0)choose(index);
        else if(which==1&&index>0){Collections.swap(packages,index,index-1);save();}
        else if(which==2&&index<packages.size()-1){Collections.swap(packages,index,index+1);save();}
        else if(which==3){packages.remove(index);save();}
      }).setNegativeButton("Anulează",null).show();
  }
  private void choose(int replaceIndex){
    Intent query=new Intent(Intent.ACTION_MAIN);query.addCategory(Intent.CATEGORY_LAUNCHER);
    List<ResolveInfo> installed=pm.queryIntentActivities(query,0);
    ArrayList<ResolveInfo> apps=new ArrayList<>();
    HashSet<String> seen=new HashSet<>();
    for(ResolveInfo info:installed){
      if(info.activityInfo==null)continue;
      String pkg=info.activityInfo.packageName;
      if(pkg.equals(host.getPackageName())||!seen.add(pkg))continue;
      if(pm.getLaunchIntentForPackage(pkg)!=null)apps.add(info);
    }
    Collections.sort(apps,(a,b)->String.CASE_INSENSITIVE_ORDER.compare(
      a.loadLabel(pm).toString(),b.loadLabel(pm).toString()));
    if(apps.isEmpty()){Toast.makeText(host,"Nu s-au găsit aplicații instalate.",Toast.LENGTH_LONG).show();return;}
    String[] names=new String[apps.size()];
    for(int i=0;i<apps.size();i++)names[i]=apps.get(i).loadLabel(pm).toString();
    new AlertDialog.Builder(host).setTitle("Alege aplicația pentru pin")
      .setItems(names,(dialog,position)->{
        String pkg=apps.get(position).activityInfo.packageName;
        if(replaceIndex>=0&&replaceIndex<packages.size())packages.set(replaceIndex,pkg);
        else if(!packages.contains(pkg))packages.add(pkg);
        else{Toast.makeText(host,"Aplicația are deja un pin.",Toast.LENGTH_SHORT).show();return;}
        // Never keep the same app twice after a replacement.
        for(int i=packages.size()-1;i>=0;i--)if(i!=replaceIndex && packages.get(i).equals(pkg)
          && replaceIndex>=0)packages.remove(i);
        save();
      }).setNegativeButton("Anulează",null).show();
  }
}
