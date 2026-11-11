package com.android.inputmethod.latin;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;
import android.view.Window;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;

/**
 * Add-on to the ORIGINAL LatinIME; never redraws key glyphs or key caps.
 *
 * Original KeyboardSwitcher may call setInputView() on a theme/layout refresh.
 * Intercept that path so Glass/Emoji cannot disappear after the first view.
 *
 * Only optional visual settings are saved. No clipboard, network or keystroke
 * history is kept by this extension.
 */
public final class GlassIME extends LatinIME {

    @Override
    public void onCreate() {
        // One-time local cleanup of user-history files created by earlier
        // original LatinIME installations. No upload and no typed-text logging.
        // Invoke before original engine loads dictionaries into memory.
        try {
            SharedPreferences p = getSharedPreferences("s24_glass", Context.MODE_PRIVATE);
            if (!p.getBoolean("history_purge_v1", false)) {
                Class<?> helper = Class.forName(
                        "com.android.inputmethod.latin.personalization.PersonalizationHelper");
                java.lang.reflect.Method purge = helper.getDeclaredMethod(
                        "removeAllUserHistoryDictionaries", Context.class);
                purge.invoke(null, this);
                p.edit().putBoolean("history_purge_v1", true).apply();
            }
        } catch (ReflectiveOperationException | RuntimeException ignored) {
            // Version-dependent cleanup: no crash or data transmission.
            // The strict DEX privacy patch independently blocks new writes.
        }
        super.onCreate();
    }
    private LinearLayout outerRoot;
    private FrameLayout glassRoot;
    private LinearLayout toolbar;
    private View originalKeyboard;
    private TextView emojiButton;
    private TextView settingsButton;
    private View emojiPane;
    private GlassEmojiPanel picker;
    private final List<Drawable> backgroundLayers = new ArrayList<>();
    // The Xiaomi KeyboardView draws into a cached bitmap. Background
    // alpha changes need its original invalidateAllKeys() to refresh that
    // bitmap, without altering individual key/letter drawables.
    private final List<View> cachedKeyboardViews = new ArrayList<>();
    private int appliedBackgroundAlpha = -1;
    private boolean windowConfigured;
    private Boolean previousBlur;

    private int dp(int n) {
        return Math.round(n * getResources().getDisplayMetrics().density);
    }

    private int prefOpacity() {
        return getSharedPreferences("s24_glass", Context.MODE_PRIVATE)
                .getInt("opacity", 45);
    }

    @Override
    public View onCreateInputView() {
        View original = super.onCreateInputView();
        return original == null ? null : wrapOriginal(original);
    }

    /**
     * Crucial: LatinIME's KeyboardSwitcher can directly call setInputView()
     * during theme/layout changes, bypassing onCreateInputView().
     */
    @Override
    public void setInputView(View view) {
        if (view == null || view == outerRoot) {
            super.setInputView(view);
            return;
        }
        // KeyboardSwitcher may hand us the same original view again. Never
        // detach and re-wrap it: doing so causes flicker and lost handlers.
        if (view == originalKeyboard && outerRoot != null) {
            super.setInputView(outerRoot);
            return;
        }
        View wrapped = wrapOriginal(view);
        super.setInputView(wrapped);
    }

    private View wrapOriginal(View view) {
        if (view == outerRoot) return view;
        if (view == originalKeyboard && outerRoot != null) return outerRoot;
        closeEmoji();
        originalKeyboard = view;
        backgroundLayers.clear();
        cachedKeyboardViews.clear();
        appliedBackgroundAlpha = -1;

        // Move only the original root view, not any internal key views.
        ViewParent oldParent = view.getParent();
        if (oldParent instanceof ViewGroup) {
            ((ViewGroup) oldParent).removeView(view);
        }

        LinearLayout newOuter = new LinearLayout(this);
        newOuter.setOrientation(LinearLayout.VERTICAL);

        LinearLayout newToolbar = new LinearLayout(this);
        newToolbar.setGravity(Gravity.CENTER_VERTICAL | Gravity.END);
        newToolbar.setPadding(dp(3), 0, dp(3), 0);

        TextView newEmojiButton = new TextView(this);
        newEmojiButton.setText("☺ Emoji");
        newEmojiButton.setTextColor(Color.WHITE);
        // Keep the new Emoji control readable above light applications
        // even when the keyboard background is 100% transparent.
        // Original Xiaomi keys/borders/labels are never changed.
        android.graphics.drawable.GradientDrawable emojiChip =
                new android.graphics.drawable.GradientDrawable();
        emojiChip.setColor(Color.argb(220, 35, 43, 58));
        emojiChip.setCornerRadius(dp(9));
        newEmojiButton.setBackground(emojiChip);
        newEmojiButton.setTextSize(15);
        newEmojiButton.setGravity(Gravity.CENTER);
        newEmojiButton.setContentDescription("Emoji avansate, apasare lunga pentru setari Glass");
        newToolbar.addView(newEmojiButton, new LinearLayout.LayoutParams(dp(88), dp(34)));
        // Samsung-style settings control, independent of One UI's optional
        // system settings gear. This is an additive toolbar control only:
        // original Xiaomi key geometry, legends and themes remain untouched.
        TextView newSettingsButton = new TextView(this);
        newSettingsButton.setText("\u2699\uFE0E");
        newSettingsButton.setTextColor(Color.WHITE);
        newSettingsButton.setTextSize(23);
        newSettingsButton.setGravity(Gravity.CENTER);
        newSettingsButton.setContentDescription("Setări tastatură Glass");
        android.graphics.drawable.GradientDrawable settingsChip =
                new android.graphics.drawable.GradientDrawable();
        settingsChip.setColor(Color.argb(220, 35, 43, 58));
        settingsChip.setCornerRadius(dp(9));
        newSettingsButton.setBackground(settingsChip);
        LinearLayout.LayoutParams settingsParams =
                new LinearLayout.LayoutParams(dp(42), dp(34));
        settingsParams.leftMargin = dp(4);
        newToolbar.addView(newSettingsButton, settingsParams);
        newSettingsButton.setOnClickListener(v -> openGlassSettings());
        newOuter.addView(newToolbar, new LinearLayout.LayoutParams(-1, dp(34)));

        FrameLayout newGlassRoot = new FrameLayout(this);
        newGlassRoot.addView(view, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        newOuter.addView(newGlassRoot, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        outerRoot = newOuter;
        glassRoot = newGlassRoot;
        toolbar = newToolbar;
        emojiButton = newEmojiButton;
        settingsButton = newSettingsButton;

        newEmojiButton.setOnClickListener(v -> {
            if (emojiPane == null) showEmoji();
            else closeEmoji();
        });
        newEmojiButton.setOnLongClickListener(v -> {
            openGlassSettings();
            return true;
        });

        // Discover background drawables once per original keyboard root.
        // Re-applying opacity is O(number of backgrounds), not O(all keys).
        collectBackgrounds(view, true);
        updateGlassBackground();
        return newOuter;
    }

    private void openGlassSettings() {
        Intent settings = new Intent();
        settings.setClassName(getPackageName(),
                "com.android.inputmethod.latin.setup.GlassActivity");
        settings.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(settings);
        } catch (RuntimeException ignored) {
            // Never interrupt input when an OEM restricts IME activity launch.
        }
    }

    @Override
    public void onStartInputView(EditorInfo attribute, boolean restarting) {
        super.onStartInputView(attribute, restarting);
        closeEmoji();
        updateGlassBackground();
    }

    @Override
    public void onFinishInputView(boolean finishingInput) {
        closeEmoji();
        super.onFinishInputView(finishingInput);
    }

    private void collectBackgrounds(View view, boolean root) {
        String name = view.getClass().getName();
        if (name.equals("com.android.inputmethod.keyboard.MainKeyboardView")
                || name.equals("com.android.inputmethod.keyboard.KeyboardView")) {
            cachedKeyboardViews.add(view);
        }
        boolean container = root
                || name.contains("InputView")
                || name.contains("MainKeyboardFrame")
                || name.contains("KeyboardLayout")
                || name.contains("MainKeyboardView")
                || name.contains("SuggestionStripView");
        if (container) {
            Drawable background = view.getBackground();
            if (background != null) {
                Drawable.ConstantState state = background.getConstantState();
                Drawable clone = state == null
                        ? background.mutate()
                        : state.newDrawable(getResources()).mutate();
                view.setBackground(clone);
                backgroundLayers.add(clone);
            }
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                collectBackgrounds(group.getChildAt(i), false);
            }
        }
    }

    private void updateGlassBackground() {
        int alpha = Math.round(Math.max(0, Math.min(100, prefOpacity())) * 2.55f);
        if (alpha != appliedBackgroundAlpha) {
            for (Drawable background : backgroundLayers) {
                background.setAlpha(alpha);
            }
            // The original Xiaomi KeyboardView renders into a private cache.
            // Its public invalidateAllKeys() marks that cache dirty; View
            // invalidate() alone may merely replay the old bitmap.
            for (View keyboard : cachedKeyboardViews) {
                try {
                    keyboard.getClass().getMethod("invalidateAllKeys").invoke(keyboard);
                } catch (ReflectiveOperationException | RuntimeException ignored) {
                    keyboard.invalidate();
                }
            }
            appliedBackgroundAlpha = alpha;
        }
        if (toolbar != null) {
            toolbar.setBackgroundColor(Color.argb(alpha, 36, 42, 55));
        }
        if (emojiButton != null) {
            boolean enabled = getSharedPreferences("s24_glass", Context.MODE_PRIVATE)
                    .getBoolean("advanced_emoji", true);
            emojiButton.setVisibility(enabled ? View.VISIBLE : View.GONE);
        }
        try {
            Window window = getWindow().getWindow();
            if (window != null) {
                if (!windowConfigured) {
                    window.setFormat(PixelFormat.TRANSLUCENT);
                    window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
                    windowConfigured = true;
                }
                if (Build.VERSION.SDK_INT >= 31) {
                    boolean blur = getSharedPreferences("s24_glass", Context.MODE_PRIVATE)
                            .getBoolean("blur", false);
                    if (previousBlur == null || previousBlur.booleanValue() != blur) {
                        if (blur) {
                            WindowManager.LayoutParams params = window.getAttributes();
                            params.flags |= WindowManager.LayoutParams.FLAG_BLUR_BEHIND;
                            params.setBlurBehindRadius(dp(12));
                            window.setAttributes(params);
                        } else {
                            window.clearFlags(WindowManager.LayoutParams.FLAG_BLUR_BEHIND);
                        }
                        previousBlur = blur;
                    }
                }
            }
        } catch (RuntimeException ignored) {
            // Blur is optional; must never interrupt input.
        }
    }

    private void showEmoji() {
        if (glassRoot == null || emojiPane != null) return;
        // The previous MATCH_PARENT overlay enlarged a WRAP_CONTENT IME root
        // to almost the entire screen. Keep the emoji panel at keyboard height.
        int actualKeyboardHeight = originalKeyboard == null ? 0 : originalKeyboard.getHeight();
        int screenHeight = getResources().getDisplayMetrics().heightPixels;
        int maxEmojiHeight = Math.round(screenHeight * 0.46f);
        int panelHeight = Math.min(maxEmojiHeight, Math.max(dp(245), actualKeyboardHeight));
        picker = new GlassEmojiPanel(this, this::closeEmoji);
        emojiPane = picker.makeView();
        if (originalKeyboard != null) originalKeyboard.setVisibility(View.INVISIBLE);
        glassRoot.addView(emojiPane, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, panelHeight, Gravity.BOTTOM));
        if (emojiButton != null) emojiButton.setText("✕ Închide");
    }

    private void closeEmoji() {
        if (glassRoot != null && emojiPane != null) glassRoot.removeView(emojiPane);
        emojiPane = null;
        picker = null;
        if (originalKeyboard != null) originalKeyboard.setVisibility(View.VISIBLE);
        if (emojiButton != null) emojiButton.setText("☺ Emoji");
    }
}
