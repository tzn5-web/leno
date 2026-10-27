package ro.evolauncher.k2401;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.EditText;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;

/** Functional searchable launcher drawer, unlike a hard-coded Apps mockup. */
final class AppsDrawer extends ScrollView {
  private final MainActivity host;
  private final PackageManager pm;
  private final GridLayout grid;
  private final ArrayList<String> apps=new ArrayList<>();
  private final EditText filter;

  AppsDrawer(MainActivity activity){
    super(activity);host=activity;pm=activity.getPackageManager();
    setBackgroundColor(0xff0b121f);setFillViewport(true);
    LinearLayout main=new LinearLayout(activity);main.setOrientation(LinearLayout.VERTICAL);
    main.setPadding(dp(24),dp(12),dp(24),dp(20));addView(main,new LayoutParams(-1,-2));
    TextView title=new TextView(activity);title.setText("APLICAȚII INSTALATE");
    title.setTextSize(26);title.setTextColor(Color.WHITE);
    main.addView(title);
    TextView detail=new TextView(activity);
    detail.setText("Apasă o aplicație pentru deschidere • Fără pictograme simulate");
    detail.setTextSize(13);detail.setTextColor(0xffa7b8c9);
    main.addView(detail);
    filter=new EditText(activity);filter.setSingleLine(true);
    filter.setHint("Caută o aplicație instalată...");
    filter.setHintTextColor(0xff8fa0b4);filter.setTextColor(Color.WHITE);
    main.addView(filter,new LinearLayout.LayoutParams(-1,dp(57)));
    grid=new GridLayout(activity);grid.setColumnCount(5);
    main.addView(grid,new LinearLayout.LayoutParams(-1,-2));
    filter.addTextChangedListener(new TextWatcher(){
      @Override public void beforeTextChanged(CharSequence s,int a,int c,int f){}
      @Override public void onTextChanged(CharSequence s,int start,int before,int count){render(s.toString());}
      @Override public void afterTextChanged(Editable e){}
    });
  }
  private int dp(int p){return Math.round(p*getResources().getDisplayMetrics().density);}
  void refresh(){
    apps.clear();
    Intent i=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
    List<ResolveInfo> available=pm.queryIntentActivities(i,0);
    HashSet<String> seen=new HashSet<>();
    for(ResolveInfo info:available){
      if(info.activityInfo==null)continue;
      String pkg=info.activityInfo.packageName;
      if(pkg.equals(host.getPackageName())||!seen.add(pkg))continue;
      if(pm.getLaunchIntentForPackage(pkg)!=null)apps.add(pkg);
    }
    Collections.sort(apps,(a,b)->name(a).compareToIgnoreCase(name(b)));
    render(filter.getText().toString());
  }
  private String name(String pkg){
    try{return pm.getApplicationLabel(pm.getApplicationInfo(pkg,0)).toString();}
    catch(Exception e){return pkg;}
  }
  private void render(String query){
    grid.removeAllViews();
    String needle=query.toLowerCase(Locale.ROOT).trim();
    int count=0;
    for(String pkg:apps){
      String label=name(pkg);
      if(!needle.isEmpty()&&!label.toLowerCase(Locale.ROOT).contains(needle)
          &&!pkg.toLowerCase(Locale.ROOT).contains(needle))continue;
      LinearLayout cell=new LinearLayout(host);
      cell.setOrientation(LinearLayout.VERTICAL);cell.setGravity(Gravity.CENTER);
      cell.setPadding(dp(4),dp(5),dp(4),dp(5));
      GradientDrawable bg=new GradientDrawable();
      bg.setColor(0xff162233);bg.setCornerRadius(dp(12));
      bg.setStroke(dp(1),0xff6d354a);cell.setBackground(bg);
      ImageView icon=new ImageView(host);icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
      try{icon.setImageDrawable(pm.getApplicationIcon(pkg));}
      catch(Exception ignore){icon.setImageDrawable(pm.getDefaultActivityIcon());}
      cell.addView(icon,new LinearLayout.LayoutParams(dp(48),dp(48)));
      TextView name=new TextView(host);name.setText(label);name.setTextColor(Color.WHITE);
      name.setTextSize(11);name.setGravity(Gravity.CENTER);
      name.setSingleLine(true);name.setEllipsize(android.text.TextUtils.TruncateAt.END);
      cell.addView(name,new LinearLayout.LayoutParams(-1,dp(25)));
      GridLayout.LayoutParams params=new GridLayout.LayoutParams();
      params.width=dp(155);params.height=dp(99);
      params.setMargins(dp(8),dp(6),dp(8),dp(6));
      grid.addView(cell,params);
      cell.setOnClickListener(v->host.app(pkg));count++;
    }
    if(count==0){
      TextView empty=new TextView(host);empty.setText("Nu există aplicații pentru această căutare.");
      empty.setTextColor(Color.WHITE);grid.addView(empty);
    }
  }
}
