package dev.tzn5.privatekeyboard;

import android.app.Activity;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;

/** In-app appearance editor. Stores no text, keystrokes, clipboard data or emoji history. */
public final class SettingsActivity extends Activity {
    private SharedPreferences prefs;
    private LinearLayout content;
    private LinearLayout preview;
    private int accent;

    private int dp(float n) {return Math.round(n*getResources().getDisplayMetrics().density);}

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        prefs=getSharedPreferences("appearance",MODE_PRIVATE);
        getWindow().setStatusBarColor(Color.rgb(11,14,20));
        getWindow().setNavigationBarColor(Color.rgb(11,14,20));
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        ScrollView scroll=new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(11,14,20));
        content=new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(20),dp(18),dp(20),dp(34));
        scroll.addView(content);
        setContentView(scroll);

        TextView title=text("Personalizare tastatură",25,Color.WHITE);
        title.setTypeface(null,1);
        content.addView(title);
        TextView description=text("Glass • Setări • Emoji • Română / English\nModificările se aplică imediat și rămân salvate local.",13,Color.rgb(164,175,190));
        description.setPadding(0,dp(8),0,dp(20));
        content.addView(description);

        TextView previewTitle=text("PREVIZUALIZARE",12,Color.rgb(177,190,209));
        previewTitle.setPadding(0,0,0,dp(8));
        content.addView(previewTitle);
        preview=new LinearLayout(this);
        preview.setOrientation(LinearLayout.VERTICAL);
        preview.setPadding(dp(8),dp(10),dp(8),dp(10));
        content.addView(preview,new LinearLayout.LayoutParams(-1,dp(132)));
        updatePreview();

        label("Culori și accente");
        LinearLayout themes=new LinearLayout(this);
        content.addView(themes);
        addTheme(themes,"Smoke","smoke",Color.rgb(174,191,212));
        addTheme(themes,"Ruby","ruby",Color.rgb(255,67,85));
        addTheme(themes,"Ice","ice",Color.rgb(116,204,255));

        slider("Transparență fundal Glass","transparency",0,95,38,"%",true);
        slider("Opacitate taste","key_opacity",50,100,84,"%",false);
        slider("Înălțime tastatură","height",0,20,8,"",false);
        slider("Rotunjire taste","radius",0,15,5,"",false);
        slider("Spațiere taste","spacing",1,5,2,"",false);

        label("Efecte și performanță");
        Switch blur=new Switch(this);
        blur.setText("Blur de sistem (dacă este suportat)");
        blur.setTextSize(14);
        blur.setTextColor(Color.WHITE);
        blur.setPadding(0,dp(4),0,dp(12));
        blur.setChecked(prefs.getBoolean("blur",false));
        blur.setOnCheckedChangeListener((button,checked)->prefs.edit().putBoolean("blur",checked).apply());
        content.addView(blur);
        TextView note=text("Blur poate fi dezactivat de One UI sau poate afecta fluiditatea. Transparența și chenarul tastelor funcționează independent.",12,Color.rgb(166,178,193));
        content.addView(note);

        Switch haptic=new Switch(this);
        haptic.setText("Feedback tactil la apăsare");
        haptic.setTextSize(14);
        haptic.setTextColor(Color.WHITE);
        haptic.setPadding(0,dp(12),0,dp(12));
        haptic.setChecked(prefs.getBoolean("haptic",false));
        haptic.setOnCheckedChangeListener((button,checked)->prefs.edit().putBoolean("haptic",checked).apply());
        content.addView(haptic);

        TextView privacy=text("Confidențialitate: aplicația nu solicită acces la internet și nu salvează textul tastat, clipboardul sau istoricul emoji.",12,Color.rgb(169,181,197));
        privacy.setPadding(0,dp(24),0,dp(20));
        content.addView(privacy);

        Button reset=new Button(this);
        reset.setAllCaps(false);
        reset.setText("Restaurează aspectul implicit");
        reset.setOnClickListener(v->{prefs.edit().clear().apply();recreate();});
        content.addView(reset);
    }

    private TextView text(String value,int sp,int color) {
        TextView t=new TextView(this);
        t.setText(value);
        t.setTextSize(sp);
        t.setTextColor(color);
        return t;
    }
    private void label(String value) {
        TextView t=text(value,17,Color.WHITE);
        t.setTypeface(null,1);
        t.setPadding(0,dp(22),0,dp(13));
        content.addView(t);
    }
    private void addTheme(LinearLayout parent,String name,String value,int color) {
        TextView item=text(name,14,Color.WHITE);
        item.setGravity(Gravity.CENTER);
        int selected=prefs.getString("theme","smoke").equals(value)?195:90;
        GradientDrawable bg=new GradientDrawable();
        bg.setColor(Color.rgb(36,40,50));
        bg.setCornerRadius(dp(13));
        bg.setStroke(dp(2),Color.argb(selected,Color.red(color),Color.green(color),Color.blue(color)));
        item.setBackground(bg);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(46),1);
        lp.setMargins(dp(2),0,dp(2),0);
        parent.addView(item,lp);
        item.setOnClickListener(v->{prefs.edit().putString("theme",value).apply();recreate();});
    }

    private void slider(String label,String key,int min,int max,int def,String suffix,boolean percent) {
        TextView heading=text(label,14,Color.rgb(230,235,245));
        heading.setPadding(0,dp(14),0,dp(2));
        content.addView(heading);
        TextView value=text("",12,Color.rgb(154,174,196));
        content.addView(value);
        SeekBar bar=new SeekBar(this);
        bar.setMax(max-min);
        int current=prefs.getInt(key,def);
        bar.setProgress(Math.max(0,Math.min(max-min,current-min)));
        bar.setProgressTintList(ColorStateList.valueOf(Color.rgb(142,193,230)));
        bar.setThumbTintList(ColorStateList.valueOf(Color.rgb(187,220,244)));
        value.setText(current+suffix);
        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
            @Override public void onProgressChanged(SeekBar seek,int position,boolean fromUser) {
                int next=min+position;
                value.setText(next+suffix);
                if(fromUser){prefs.edit().putInt(key,next).apply();updatePreview();}
            }
            @Override public void onStartTrackingTouch(SeekBar seek){}
            @Override public void onStopTrackingTouch(SeekBar seek){}
        });
        content.addView(bar,new LinearLayout.LayoutParams(-1,dp(37)));
    }

    private void updatePreview() {
        if(preview==null)return;
        preview.removeAllViews();
        String theme=prefs.getString("theme","smoke");
        accent="ruby".equals(theme)?Color.rgb(255,67,85):
               "ice".equals(theme)?Color.rgb(116,204,255):Color.rgb(174,191,212);
        int alpha=Math.round((100-prefs.getInt("transparency",38))*2.55f);
        GradientDrawable back=new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{Color.argb(alpha,18,21,29),Color.argb(alpha,34,38,47)});
        back.setCornerRadius(dp(16));
        back.setStroke(dp(1),Color.argb(100,Color.red(accent),Color.green(accent),Color.blue(accent)));
        preview.setBackground(back);
        TextView tool=text("☺     Română  ·  English                              ⚙",12,Color.WHITE);
        tool.setGravity(Gravity.CENTER_VERTICAL);
        preview.addView(tool,new LinearLayout.LayoutParams(-1,dp(32)));
        String[][] labels={{"Q","W","E","R","T","Y","U","I","O","P"},{"A","S","D","F","G","H","J","K","L"}};
        for(String[] line:labels){
            LinearLayout row=new LinearLayout(this);
            preview.addView(row,new LinearLayout.LayoutParams(-1,dp(37)));
            for(String symbol:line){
                TextView key=text(symbol,13,Color.WHITE);
                key.setGravity(Gravity.CENTER);
                GradientDrawable shape=new GradientDrawable();
                shape.setColor(Color.argb(Math.round(prefs.getInt("key_opacity",84)*2.55f),49,55,67));
                shape.setCornerRadius(dp(3+prefs.getInt("radius",5)));
                shape.setStroke(dp(1),Color.argb(85,Color.red(accent),Color.green(accent),Color.blue(accent)));
                key.setBackground(shape);
                LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(32),1);
                lp.setMargins(dp(1),dp(2),dp(1),dp(2));
                row.addView(key,lp);
            }
        }
    }
}
