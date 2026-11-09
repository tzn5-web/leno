package dev.tzn5.glass;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;

/** Only stores two appearance integers. Never touches typed text. */
public final class GlassSettingsActivity extends Activity {
    static final String PREFS = "glass_visual_settings";
    static final String OPACITY = "background_opacity";
    static final String BLUR = "background_blur";

    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }

    private TextView label(String text, int size) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextColor(Color.WHITE);
        view.setTextSize(size);
        view.setPadding(0, dp(12), 0, dp(7));
        return view;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(24), dp(26), dp(24), dp(20));
        root.setBackgroundColor(Color.rgb(21, 25, 33));
        root.addView(label("Xiaomi LatinIME · Glass", 24));
        root.addView(label("Tastele, chenarele și literele sunt păstrate. Schimbăm doar fundalul.", 15));
        TextView opacityValue = label("", 17);
        root.addView(opacityValue);
        SeekBar alpha = new SeekBar(this);
        alpha.setMax(100);
        alpha.setProgress(getSharedPreferences(PREFS, MODE_PRIVATE).getInt(OPACITY, 38));
        root.addView(alpha);
        LinearLayout preview = new LinearLayout(this);
        GradientDrawable border = new GradientDrawable();
        border.setStroke(dp(1), Color.rgb(130, 148, 167));
        border.setCornerRadius(dp(15));
        preview.setBackground(border);
        LinearLayout.LayoutParams previewParams = new LinearLayout.LayoutParams(-1, dp(72));
        previewParams.topMargin = dp(14);
        root.addView(preview, previewParams);
        TextView previewText = label("A  B  C  D  E  F  G", 21);
        previewText.setGravity(Gravity.CENTER);
        preview.addView(previewText, new LinearLayout.LayoutParams(-1, -1));
        Runnable redraw = () -> {
            int value = alpha.getProgress();
            opacityValue.setText("Opacitate fundal: " + value + "%   •   Transparență: " + (100 - value) + "%");
            preview.setBackgroundColor(Color.argb(Math.round(value * 2.55f), 43, 52, 67));
            preview.invalidate();
        };
        alpha.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            public void onProgressChanged(SeekBar b, int v, boolean fromUser) {
                redraw.run();
                if (fromUser) getSharedPreferences(PREFS, MODE_PRIVATE).edit().putInt(OPACITY, v).apply();
            }
            public void onStartTrackingTouch(SeekBar b) {}
            public void onStopTrackingTouch(SeekBar b) {}
        });
        redraw.run();
        TextView blurValue = label("", 17);
        root.addView(blurValue);
        SeekBar blur = new SeekBar(this);
        blur.setMax(45);
        blur.setProgress(getSharedPreferences(PREFS, MODE_PRIVATE).getInt(BLUR, 24));
        blurValue.setText("Intensitate blur: " + blur.getProgress());
        blur.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            public void onProgressChanged(SeekBar b, int v, boolean fromUser) {
                blurValue.setText("Intensitate blur: " + v);
                if (fromUser) getSharedPreferences(PREFS, MODE_PRIVATE).edit().putInt(BLUR, v).apply();
            }
            public void onStartTrackingTouch(SeekBar b) {}
            public void onStopTrackingTouch(SeekBar b) {}
        });
        root.addView(blur);
        root.addView(label("Efectul de estompare depinde de setările și suportul One UI; transparența funcționează independent. Nu sunt memorate texte, taste sau emoji utilizate.", 14));
        setContentView(root);
    }
}
