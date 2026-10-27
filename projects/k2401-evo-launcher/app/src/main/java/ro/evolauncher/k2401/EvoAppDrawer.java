package ro.evolauncher.k2401;

import android.app.Dialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.Window;
import android.widget.BaseAdapter;
import android.widget.EditText;
import android.widget.GridView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;

/** Real list of installed launchable applications, not decorative fake icons. */
final class EvoAppDrawer {
  private final MainActivity host;
  private final PackageManager pm;
  private final ArrayList<Item> all=new ArrayList<>(),shown=new ArrayList<>();
  private static final class Item {
    final String name,packageName;
    Item(String name,String pkg){this.name=name;this.packageName=pkg;}
  }
  EvoAppDrawer(MainActivity owner){host=owner;pm=owner.getPackageManager();}
  int dp(float value){return (int)(value*host.getResources().getDisplayMetrics().density+.5f);}
  private void load(){
    all.clear();
    Intent query=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
    List<ResolveInfo> hits=pm.queryIntentActivities(query,0);
    HashSet<String> known=new HashSet<>();
    for(ResolveInfo info:hits){
      if(info.activityInfo==null)continue;
      String pkg=info.activityInfo.packageName;
      if(pkg.equals(host.getPackageName())||!known.add(pkg))continue;
      if(pm.getLaunchIntentForPackage(pkg)==null)continue;
      CharSequence label=info.loadLabel(pm);
      all.add(new Item(label==null?pkg:label.toString(),pkg));
    }
    Collections.sort(all,(a,b)->a.name.compareToIgnoreCase(b.name));
    shown.clear();shown.addAll(all);
  }
  void show(){
    load();
    final Dialog dialog=new Dialog(host,android.R.style.Theme_Material_NoActionBar);
    LinearLayout column=new LinearLayout(host);column.setOrientation(LinearLayout.VERTICAL);
    column.setPadding(dp(18),dp(12),dp(18),dp(12));
    column.setBackgroundColor(0xff0a111c);
    TextView header=new TextView(host);header.setText("APLICAȚII INSTALATE  •  "+all.size());
    header.setTextColor(Color.WHITE);header.setTextSize(22);
    column.addView(header,new LinearLayout.LayoutParams(-1,dp(47)));
    EditText search=new EditText(host);
    search.setSingleLine(true);search.setTextColor(Color.WHITE);search.setHintTextColor(0xff93a7bd);
    search.setHint("Caută aplicația instalată...");
    column.addView(search,new LinearLayout.LayoutParams(-1,dp(58)));
    GridView grid=new GridView(host);grid.setNumColumns(5);
    grid.setVerticalSpacing(dp(14));grid.setHorizontalSpacing(dp(8));
    grid.setStretchMode(GridView.STRETCH_COLUMN_WIDTH);
    grid.setPadding(dp(6),dp(6),dp(6),dp(6));
    final BaseAdapter adapter=new BaseAdapter(){
      @Override public int getCount(){return shown.size();}
      @Override public Object getItem(int p){return shown.get(p);}
      @Override public long getItemId(int p){return p;}
      @Override public android.view.View getView(int position,android.view.View previous,
                                                   android.view.ViewGroup parent){
        Item item=shown.get(position);
        LinearLayout tile=new LinearLayout(host);tile.setOrientation(LinearLayout.VERTICAL);
        tile.setGravity(Gravity.CENTER);
        tile.setBackgroundColor(0xff172234);
        ImageView icon=new ImageView(host);
        try{Drawable d=pm.getApplicationIcon(item.packageName);icon.setImageDrawable(d);}
        catch(Exception ignored){icon.setImageDrawable(pm.getDefaultActivityIcon());}
        icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
        tile.addView(icon,new LinearLayout.LayoutParams(dp(64),dp(66)));
        TextView label=new TextView(host);label.setText(item.name);
        label.setTextSize(13);label.setTextColor(0xffedf3fa);label.setGravity(Gravity.CENTER);
        label.setMaxLines(2);label.setEllipsize(android.text.TextUtils.TruncateAt.END);
        tile.addView(label,new LinearLayout.LayoutParams(-1,dp(43)));
        tile.setContentDescription("Deschide "+item.name);
        return tile;
      }
    };
    grid.setAdapter(adapter);
    grid.setOnItemClickListener((parent,view,position,id)->{
      String pkg=shown.get(position).packageName;
      dialog.dismiss();host.app(pkg);
    });
    search.addTextChangedListener(new TextWatcher(){
      @Override public void beforeTextChanged(CharSequence s,int start,int count,int after){}
      @Override public void onTextChanged(CharSequence s,int start,int before,int count){
        String term=s.toString().toLowerCase(Locale.ROOT);
        shown.clear();
        for(Item item:all)
          if(item.name.toLowerCase(Locale.ROOT).contains(term)||
             item.packageName.toLowerCase(Locale.ROOT).contains(term))shown.add(item);
        adapter.notifyDataSetChanged();
      }
      @Override public void afterTextChanged(Editable e){}
    });
    column.addView(grid,new LinearLayout.LayoutParams(-1,0,1));
    TextView close=new TextView(host);
    close.setText("ÎNCHIDE");close.setTextColor(Color.WHITE);close.setTextSize(19);
    close.setGravity(Gravity.CENTER);close.setBackgroundColor(0xff86223e);
    column.addView(close,new LinearLayout.LayoutParams(-1,dp(52)));
    close.setOnClickListener(v->dialog.dismiss());
    dialog.setContentView(column);
    dialog.show();
    Window window=dialog.getWindow();if(window!=null)window.setLayout(-1,-1);
  }
}
