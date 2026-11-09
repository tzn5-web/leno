package dev.tzn5.privatekeyboard;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class SetupActivity extends Activity {
    private int dp(int n) {
        return Math.round(n * getResources().getDisplayMetrics().density);
    }

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_VERTICAL);
        root.setPadding(dp(24), dp(24), dp(24), dp(24));

        TextView info = new TextView(this);
        info.setText("S24 Private Keyboard\n\nA local-only keyboard with English, Romanian letters and symbols. It does not request network access, store keystrokes, collect analytics, or use external SDKs.\n\nThe text you type is sent only to the app you are using through Android's normal input connection.");
        info.setTextSize(17);
        root.addView(info);

        Button enable = new Button(this);
        enable.setText("1. Enable keyboard in Android settings");
        enable.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)));
        root.addView(enable);

        Button choose = new Button(this);
        choose.setText("2. Select keyboard");
        choose.setOnClickListener(v -> {
            InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            if (manager != null) manager.showInputMethodPicker();
        });
        root.addView(choose);
        setContentView(root);
    }
}
