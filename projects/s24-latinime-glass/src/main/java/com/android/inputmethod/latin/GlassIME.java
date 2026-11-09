package com.android.inputmethod.latin;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Extends the ORIGINAL LatinIME. Original keyboard views, keycaps, labels,
 * keyboard actions and dictionaries remain owned by the original code.
 *
 * Only background drawables on keyboard container views receive alpha;
 * individual key drawables and text are never changed.
 */
public final class GlassIME extends LatinIME {
    private FrameLayout glassRoot;
    private LinearLayout toolbar;
    private View originalKeyboard;
    private TextView emojiButton;
    private View emojiPane;
    private GlassEmojiPanel picker;

    private int dp(int n) {
        return Math.round(n * getResources().getDisplayMetrics().density);
    }

    public int prefOpacity() {
        return getSharedPreferences("s24_glass", Context.MODE_PRIVATE).getInt("opacity", 45);
    }

    @Override
    public View onCreateInputView() {
        originalKeyboard = super.onCreateInputView();
        if (originalKeyboard == null) return null;

        // Own narrow toolbar: the original Xiaomi suggestion strip and keys
        // remain unoccluded and retain their exact drawing/layout.
        LinearLayout outer = new LinearLayout(this);
        outer.setOrientation(LinearLayout.VERTICAL);
        toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL | Gravity.END);

        // Glass preferences are now opened through IME settingsActivity, like
        // Android's settings gear. No duplicate settings button inside keyboard.
        emojiButton = new TextView(this);
        emojiButton.setText("☺ Emoji");
        emojiButton.setTextColor(Color.WHITE);
        emojiButton.setTextSize(17);
        emojiButton.setGravity(Gravity.CENTER);
        toolbar.addView(emojiButton, new LinearLayout.LayoutParams(dp(88), dp(34)));
        emojiButton.setContentDescription("Deschide emoji avansate");
        emojiButton.setOnClickListener(v -> {
            if (emojiPane == null) showEmoji();
            else closeEmoji();
        });
        // OEM picker may hide settings gears for third-party input methods.
        // A long press is a discoverable fallback without an extra visible key.
        emojiButton.setOnLongClickListener(v -> {
            Intent settings = new Intent();
            settings.setClassName(getPackageName(),
                    "com.android.inputmethod.latin.setup.GlassActivity");
            settings.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(settings);
            return true;
        });
        outer.addView(toolbar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(34)));

        glassRoot = new FrameLayout(this);
        glassRoot.addView(originalKeyboard, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        outer.addView(glassRoot, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        updateGlassBackground();
        return outer;
    }

    @Override
    public void onStartInputView(EditorInfo attribute, boolean restarting) {
        super.onStartInputView(attribute, restarting);
        closeEmoji();
        updateGlassBackground();
        if (emojiButton != null) emojiButton.setVisibility(getSharedPreferences(
                "s24_glass", Context.MODE_PRIVATE).getBoolean("advanced_emoji", true)
                ? View.VISIBLE : View.GONE);
    }

    @Override
    public void onFinishInputView(boolean finishingInput) {
        closeEmoji();
        super.onFinishInputView(finishingInput);
    }

    private void updateGlassBackground() {
        if (originalKeyboard == null) return;
        int percentage = Math.max(0, Math.min(100, prefOpacity()));
        int alpha = (percentage * 255) / 100;
        applyBackgroundOnly(originalKeyboard, alpha);
        if (toolbar != null) toolbar.setBackgroundColor(Color.argb(alpha, 36, 42, 55));
        try {
            Window w = getWindow().getWindow();
            if (w != null) {
                w.setFormat(PixelFormat.TRANSLUCENT);
                w.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
                boolean blur = getSharedPreferences("s24_glass", Context.MODE_PRIVATE)
                        .getBoolean("blur", true);
                if (Build.VERSION.SDK_INT >= 31) {
                    if (blur) {
                        WindowManager.LayoutParams lp = w.getAttributes();
                        lp.flags |= WindowManager.LayoutParams.FLAG_BLUR_BEHIND;
                        lp.setBlurBehindRadius(dp(12));
                        w.setAttributes(lp);
                    } else {
                        w.clearFlags(WindowManager.LayoutParams.FLAG_BLUR_BEHIND);
                    }
                }
            }
        } catch (RuntimeException ignored) {
            // System-level blur is optional; never interrupt typing.
        }
    }

    private void applyBackgroundOnly(View v, int alpha) {
        String name = v.getClass().getName();
        boolean keyboardContainer = name.contains("MainKeyboardView")
                || name.endsWith(".KeyboardLayout")
                || name.contains("SuggestionStripView");
        if (keyboardContainer) {
            Drawable background = v.getBackground();
            if (background != null) {
                // Crucial: alpha only on background, not on keys or labels.
                Drawable clone = background.getConstantState() != null
                        ? background.getConstantState().newDrawable(getResources()).mutate()
                        : background.mutate();
                clone.setAlpha(alpha);
                v.setBackground(clone);
            }
        }
        if (v instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) v;
            for (int i = 0; i < group.getChildCount(); i++) {
                applyBackgroundOnly(group.getChildAt(i), alpha);
            }
        }
    }

    private void showEmoji() {
        if (glassRoot == null || emojiPane != null) return;
        picker = new GlassEmojiPanel(this, () -> closeEmoji());
        emojiPane = picker.makeView();
        glassRoot.addView(emojiPane, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        if (emojiButton != null) emojiButton.setText("✕ Închide");
    }

    private void closeEmoji() {
        if (glassRoot != null && emojiPane != null) glassRoot.removeView(emojiPane);
        emojiPane = null;
        picker = null;
        if (emojiButton != null) {
            emojiButton.setText("☺ Emoji");
            boolean enabled = getSharedPreferences("s24_glass", Context.MODE_PRIVATE)
                    .getBoolean("advanced_emoji", true);
            emojiButton.setVisibility(enabled ? View.VISIBLE : View.GONE);
        }
    }
}
