package com.buildfactory.demo;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView view = new TextView(this);
        view.setText("BuildFactoryDemo: Android APK built by CI.");
        view.setTextSize(22f);
        view.setPadding(32, 48, 32, 32);
        setContentView(view);
    }
}
