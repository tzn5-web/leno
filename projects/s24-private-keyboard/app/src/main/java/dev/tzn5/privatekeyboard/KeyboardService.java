package dev.tzn5.privatekeyboard;

import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.inputmethodservice.InputMethodService;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.widget.Button;
import android.widget.LinearLayout;
import java.util.Locale;

/**
 * Local-only IME. No logging, persistence, networking, clipboard access or learning.
 * Key labels and transient Shift/Symbol state are the only app-maintained state.
 */
public final class KeyboardService extends InputMethodService {
    private LinearLayout root;
    private boolean shift;
    private boolean symbols;

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    public boolean onEvaluateFullscreenMode() {
        return false;
    }

    @Override
    public View onCreateInputView() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(31, 35, 43));
        root.setPadding(dp(3), dp(6), dp(3), dp(8));
        drawKeyboard();
        return root;
    }

    @Override
    public void onStartInput(EditorInfo attribute, boolean restarting) {
        super.onStartInput(attribute, restarting);
        shift = false;
        int kind = attribute == null ? 0 : (attribute.inputType & android.text.InputType.TYPE_MASK_CLASS);
        symbols = kind == android.text.InputType.TYPE_CLASS_NUMBER
                || kind == android.text.InputType.TYPE_CLASS_PHONE
                || kind == android.text.InputType.TYPE_CLASS_DATETIME;
        if (root != null) drawKeyboard();
    }

    private GradientDrawable keyBackground(boolean special) {
        GradientDrawable result = new GradientDrawable();
        result.setColor(special ? Color.rgb(75, 83, 98) : Color.rgb(53, 60, 72));
        result.setCornerRadius(dp(6));
        return result;
    }

    private void addRow(String... keys) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        root.addView(row, new LinearLayout.LayoutParams(-1, dp(51)));

        for (String key : keys) {
            float weight = "space".equals(key) ? 3.3f : ("enter".equals(key) ? 1.45f : 1f);
            Button button = new Button(this);
            String label = labelFor(key);
            button.setText(label);
            button.setAllCaps(false);
            button.setTextColor(Color.WHITE);
            button.setTextSize("space".equals(key) ? 12 : (key.length() > 3 ? 13 : 18));
            button.setPadding(0, 0, 0, 0);
            button.setMinWidth(0);
            button.setMinimumWidth(0);
            button.setMinHeight(0);
            button.setMinimumHeight(0);
            button.setFocusable(false);
            button.setFocusableInTouchMode(false);
            boolean special = "shift".equals(key) || "del".equals(key)
                    || "enter".equals(key) || "mode".equals(key);
            button.setBackground(keyBackground(special));
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(45), weight);
            params.setMargins(dp(2), dp(2), dp(2), dp(2));
            row.addView(button, params);
            button.setOnClickListener(v -> handle(key));
        }
    }

    private String labelFor(String key) {
        switch (key) {
            case "shift": return shift ? "⇧" : "⇧";
            case "del": return "⌫";
            case "enter": return "↵";
            case "mode": return symbols ? "ABC" : "?123";
            case "space": return "Română · English";
            default: return shift && !symbols ? key.toUpperCase(Locale.ROOT) : key;
        }
    }

    private void drawKeyboard() {
        if (root == null) return;
        root.removeAllViews();
        if (symbols) {
            addRow("1","2","3","4","5","6","7","8","9","0");
            addRow("@","#","$","%","&","-","+","(",")","/");
            addRow("*","'","\"",";",":","!","?","=","del");
            addRow("mode",",","space",".","enter");
        } else {
            addRow("q","w","e","r","t","y","u","i","o","p");
            addRow("a","s","d","f","g","h","j","k","l");
            addRow("shift","z","x","c","v","b","n","m","del");
            addRow("ă","â","î","ș","ț");
            addRow("mode",",","space",".","enter");
        }
    }

    private void handle(String key) {
        InputConnection connection = getCurrentInputConnection();
        switch (key) {
            case "shift":
                shift = !shift;
                drawKeyboard();
                return;
            case "mode":
                symbols = !symbols;
                shift = false;
                drawKeyboard();
                return;
            case "del":
                if (connection != null && !connection.deleteSurroundingTextInCodePoints(1, 0)) {
                    connection.sendKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DEL));
                    connection.sendKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DEL));
                }
                return;
            case "space":
                if (connection != null) connection.commitText(" ", 1);
                return;
            case "enter":
                if (connection == null) return;
                EditorInfo editor = getCurrentInputEditorInfo();
                int action = editor == null ? EditorInfo.IME_ACTION_NONE
                        : editor.imeOptions & EditorInfo.IME_MASK_ACTION;
                if (action != EditorInfo.IME_ACTION_NONE && action != EditorInfo.IME_ACTION_UNSPECIFIED) {
                    connection.performEditorAction(action);
                } else {
                    connection.commitText("\n", 1);
                }
                return;
            default:
                if (connection != null) {
                    connection.commitText(shift && !symbols ? key.toUpperCase(Locale.ROOT) : key, 1);
                }
                if (shift) {
                    shift = false;
                    drawKeyboard();
                }
        }
    }

    @Override
    public void onFinishInput() {
        shift = false;
        symbols = false;
        super.onFinishInput();
    }
}
