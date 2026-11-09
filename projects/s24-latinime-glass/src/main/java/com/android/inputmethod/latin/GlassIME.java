package com.android.inputmethod.latin;

import android.content.Context;
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

        glassRoot = new FrameLayout(this);
        glassRoot.addView(originalKeyboard, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        emojiButton = new TextView(this);
        emojiButton.setText("☺");
        emojiButton.setTextColor(Color.WHITE);
        emojiButton.setTextSize(22);
        emojiButton.setGravity(Gravity.CENTER);
        emojiButton.setBackground(new ColorDrawable(Color.argb(165, 45, 51, 66)));
        FrameLayout.LayoutParams buttonParams = new FrameLayout.LayoutParams(dp(36), dp(34),
                Gravity.TOP | Gravity.END);
        buttonParams.setMargins(0, dp(1), dp(5), 0);
        glassRoot.addView(emojiButton, buttonParams);
        emojiButton.setContentDescription("Deschide emoji avansate");
        emojiButton.setOnClickListener(v -> showEmoji());
        updateGlassBackground();
        return glassRoot;
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
        emojiButton.bringToFront();
        emojiButton.setVisibility(View.GONE);
    }

    private void closeEmoji() {
        if (glassRoot != null && emojiPane != null) glassRoot.removeView(emojiPane);
        emojiPane = null;
        picker = null;
        if (emojiButton != null) emojiButton.setVisibility(View.VISIBLE);
    }
}
