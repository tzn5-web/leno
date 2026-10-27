package ro.evolauncher.k2401;

import android.app.AlertDialog;
import android.app.Dialog;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.widget.Button;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.ArrayList;

/**
 * Full-page 21-design visual picker, with the real original image as preview.
 * Never applies a new theme while previewing: the explicit APPLY button alone
 * persists the selection. Available on Android 10 without third-party widgets.
 */
final class EvoSkinGallery {
  private final MainActivity host;
  private final EvoSkinStore store;
  private final Runnable onApply;
  private static final int WHITE=0xffecf3fa,DIM=0xff9db1c1,BG=0xff0b1018,RED=0xffe62942;
  private final ArrayList<Bitmap> thumbs=new ArrayList<>();

  EvoSkinGallery(MainActivity owner,EvoSkinStore skins,Runnable applied){
    host=owner;store=skins;onApply=applied;
  }
  private int dp(float value){return (int)(value*host.getResources().getDisplayMetrics().density+.5f);}
  private GradientDrawable panel(int fill,int stroke){
    GradientDrawable bg=new GradientDrawable();
    bg.setColor(fill);bg.setCornerRadius(dp(11));bg.setStroke(dp(1),stroke);
    return bg;
  }
  private TextView label(String value,int size,int color){
    TextView text=new TextView(host);
    text.setText(value);text.setTextColor(color);text.setTextSize(size);
    text.setGravity(Gravity.CENTER_VERTICAL);
    return text;
  }
  private Button button(String text){
    Button b=new Button(host);b.setText(text);b.setAllCaps(false);
    b.setTextColor(Color.WHITE);
    b.setTextSize(13);
    b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xff963047));
    return b;
  }
  private void addRow(LinearLayout base,String headline,String subtitle){
    TextView title=label(headline,22,WHITE);
    title.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
    base.addView(title,new LinearLayout.LayoutParams(-1,dp(36)));
    TextView description=label(subtitle,13,DIM);
    base.addView(description,new LinearLayout.LayoutParams(-1,dp(45)));
  }
  void show(){
    final Dialog dialog=new Dialog(host,android.R.style.Theme_Material_NoActionBar);
    LinearLayout page=new LinearLayout(host);page.setOrientation(LinearLayout.VERTICAL);
    page.setPadding(dp(18),dp(12),dp(18),dp(10));page.setBackgroundColor(BG);
    addRow(page,"21 SKINURI • EVO LAUNCHER",
      "Atinge un design pentru previzualizare. EVO DIGITAL DASH este primul.");
    LinearLayout controls=new LinearLayout(host);
    Button importButton=button("IMPORTĂ CELE 21 IMAGINI");
    Button closeButton=button("ÎNCHIDE");
    controls.addView(importButton,new LinearLayout.LayoutParams(0,dp(55),2));
    controls.addView(closeButton,new LinearLayout.LayoutParams(0,dp(55),1));
    page.addView(controls,new LinearLayout.LayoutParams(-1,dp(55)));
    importButton.setOnClickListener(v->{dialog.dismiss();host.importSkinArchive();});
    closeButton.setOnClickListener(v->dialog.dismiss());

    TextView state=label(store.hasAll()?
      "21/21 fotografii originale instalate • valorile ECU sunt LIVE, nu din poze":
      "Importă o singură dată arhiva ZIP cu pozele originale. Selectorul păstrează imaginile după repornire.",
      13,store.hasAll()?0xff64dbb4:0xffffc778);
    page.addView(state,new LinearLayout.LayoutParams(-1,dp(36)));

    ScrollView scroller=new ScrollView(host);
    GridLayout grid=new GridLayout(host);
    grid.setColumnCount(3);grid.setPadding(dp(2),dp(6),dp(2),dp(14));
    for(int i=0;i<EvoSkinStore.COUNT;i++){
      final int index=i;
      LinearLayout tile=new LinearLayout(host);tile.setOrientation(LinearLayout.VERTICAL);
      tile.setPadding(dp(5),dp(5),dp(5),dp(5));
      tile.setBackground(panel(0xff182230,index==store.current()?RED:0xff43536a));
      GridLayout.LayoutParams lp=new GridLayout.LayoutParams();
      lp.width=dp(232);lp.height=dp(172);lp.setMargins(dp(6),dp(6),dp(6),dp(6));
      grid.addView(tile,lp);
      ImageView photo=new ImageView(host);
      photo.setBackgroundColor(0xff101925);
      photo.setScaleType(ImageView.ScaleType.FIT_CENTER);
      Bitmap thumb=store.thumbnail(i);
      if(thumb!=null){thumbs.add(thumb);photo.setImageBitmap(thumb);}
      else photo.setImageResource(android.R.drawable.ic_menu_gallery);
      tile.addView(photo,new LinearLayout.LayoutParams(-1,dp(128)));
      TextView name=label(String.format(java.util.Locale.US,"%02d  %s",i+1,EvoSkinStore.NAMES[i]),
        11,index==store.current()?0xffff8d9e:WHITE);
      name.setSingleLine(true);name.setEllipsize(android.text.TextUtils.TruncateAt.END);
      tile.addView(name,new LinearLayout.LayoutParams(-1,dp(25)));
      tile.setOnClickListener(v->{
        if(!store.hasImage(index)){
          new AlertDialog.Builder(host).setTitle(EvoSkinStore.NAMES[index])
            .setMessage("Imaginea originală nu a fost importată încă. Importă arhiva cu cele 21 skinuri.")
            .setPositiveButton("Importă",(d,w)->{dialog.dismiss();host.importSkinArchive();})
            .setNegativeButton("Înapoi",null).show();
        }else preview(index,dialog);
      });
    }
    scroller.addView(grid);
    page.addView(scroller,new LinearLayout.LayoutParams(-1,0,1));
    dialog.setContentView(page);
    Window window=dialog.getWindow();
    if(window!=null){window.setLayout(-1,-1);window.setBackgroundDrawableResource(android.R.color.transparent);}
    dialog.setOnDismissListener(d->{
      for(Bitmap thumb:thumbs)if(thumb!=null&&!thumb.isRecycled())thumb.recycle();
      thumbs.clear();
    });
    dialog.show();if(window!=null)window.setLayout(-1,-1);
  }
  private void preview(int selected,Dialog parent){
    final Dialog dialog=new Dialog(host,android.R.style.Theme_Material_NoActionBar);
    LinearLayout wrapper=new LinearLayout(host);
    wrapper.setPadding(dp(15),dp(10),dp(15),dp(12));
    wrapper.setBackgroundColor(BG);wrapper.setOrientation(LinearLayout.VERTICAL);
    TextView heading=label((selected+1)+". "+EvoSkinStore.NAMES[selected],21,WHITE);
    wrapper.addView(heading,new LinearLayout.LayoutParams(-1,dp(45)));
    ImageView picture=new ImageView(host);
    picture.setScaleType(ImageView.ScaleType.FIT_CENTER);
    picture.setBackgroundColor(Color.BLACK);
    Bitmap src=store.bitmap(selected);
    picture.setImageBitmap(src);
    wrapper.addView(picture,new LinearLayout.LayoutParams(-1,0,1f));
    TextView disclosure=label(
      "PREVIZUALIZARE ORIGINALĂ • Cifrele din fotografie sunt demo. Pe Home, RPM/STFT/LTFT/TEMP vin numai de la ECU.",
      13,DIM);
    wrapper.addView(disclosure,new LinearLayout.LayoutParams(-1,dp(48)));
    LinearLayout actions=new LinearLayout(host);
    Button cancel=button("ÎNAPOI");
    Button apply=button(selected==store.current()?"ACTIV DEJA":"APLICĂ ACEST SKIN");
    actions.addView(cancel,new LinearLayout.LayoutParams(0,dp(58),1));
    actions.addView(apply,new LinearLayout.LayoutParams(0,dp(58),2));
    wrapper.addView(actions);
    cancel.setOnClickListener(v->dialog.dismiss());
    apply.setOnClickListener(v->{
      store.select(selected);
      onApply.run();
      dialog.dismiss();parent.dismiss();
    });
    dialog.setContentView(wrapper);
    Window window=dialog.getWindow();
    dialog.show();if(window!=null)window.setLayout(-1,-1);
  }
}
