package com.android.inputmethod.latin.setup;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;

/**
 * Glass customization. Persists only appearance switches and opacity,
 * never text, clipboard, emoji history or app usage.
 */
public final class GlassActivity extends Activity {
    private int dp(int n) {
        return Math.round(n * getResources().getDisplayMetrics().density);
    }

    private TextView text(LinearLayout parent, String caption, int size) {
        TextView view = new TextView(this);
        view.setText(caption);
        view.setTextColor(Color.WHITE);
        view.setTextSize(size);
        view.setPadding(0, dp(9), 0, dp(9));
        parent.addView(view);
        return view;
    }

    private Button button(LinearLayout parent, String caption) {
        Button button = new Button(this);
        button.setText(caption);
        button.setAllCaps(false);
        parent.addView(button);
        return button;
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        SharedPreferences preferences = getSharedPreferences("s24_glass", Context.MODE_PRIVATE);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(26), dp(20), dp(20));
        root.setBackgroundColor(Color.rgb(24, 29, 39));
        root.setGravity(Gravity.TOP);

        text(root, "Xiaomi Keyboard · Glass", 24);
        text(root, "Tastele, chenarele și caracterele rămân originale. Se modifică doar transparența fundalului.", 14);

        TextView indicator = text(root, "", 17);
        SeekBar opacity = new SeekBar(this);
        opacity.setMax(100);
        opacity.setProgress(preferences.getInt("opacity", 45));
        root.addView(opacity);
        indicator.setText("Opacitate fundal: " + opacity.getProgress() + "%  ·  Transparență: "
                + (100 - opacity.getProgress()) + "%");
        opacity.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int value, boolean fromUser) {
                indicator.setText("Opacitate fundal: " + value + "%  ·  Transparență: "
                        + (100 - value) + "%");
                if (fromUser) preferences.edit().putInt("opacity", value).apply();
            }
            @Override public void onStartTrackingTouch(SeekBar bar) { }
            @Override public void onStopTrackingTouch(SeekBar bar) { }
        });

        CheckBox blur = new CheckBox(this);
        blur.setText("Efect de estompare Glass, dacă este suportat de telefon");
        blur.setTextColor(Color.WHITE);
        blur.setChecked(preferences.getBoolean("blur", true));
        blur.setOnCheckedChangeListener((view, enabled) ->
                preferences.edit().putBoolean("blur", enabled).apply());
        root.addView(blur);

        CheckBox emoji = new CheckBox(this);
        emoji.setText("Selector emoji avansat (categorii, căutare locală)");
        emoji.setTextColor(Color.WHITE);
        emoji.setChecked(preferences.getBoolean("advanced_emoji", true));
        emoji.setOnCheckedChangeListener((view, enabled) ->
                preferences.edit().putBoolean("advanced_emoji", enabled).apply());
        root.addView(emoji);

        text(root, "0% = complet transparent, 100% = fundal original opac. Pentru a vedea schimbarea, redeschide tastatura.", 13);
        text(root, "Nu sunt colectate date prin aceste setări. Cuvintele tastate sunt administrate în continuare de motorul LatinIME original.", 12);

        button(root, "Setări tastatură Xiaomi (original)").setOnClickListener(v -> {
            Intent open = new Intent();
            open.setClassName(getPackageName(),
                    "com.android.inputmethod.latin.settings.SettingsActivity");
            try { startActivity(open); }
            catch (RuntimeException ignored) { }
        });

        button(root, "Activează tastatura").setOnClickListener(v ->
                startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)));
        button(root, "Alege tastatura implicită").setOnClickListener(v -> {
            InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            if (manager != null) manager.showInputMethodPicker();
        });

        setContentView(root);
    }
}
