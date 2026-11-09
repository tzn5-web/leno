package dev.tzn5.glass;

import com.android.inputmethod.latin.LatinIME;

import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.GridLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Extends the real LatinIME, preserving its key rendering and the original assets. */
public final class GlassLatinIME extends LatinIME {
    private FrameLayout glassRoot;
    private View latinView;
    private LinearLayout emojiPicker;
    private GridLayout emojiGrid;
    private int category;
    private int tone;

    private static final String[][] EMOJI = new String[][] {
        {"😀","😃","😄","😁","😆","😅","🤣","😂","🙂","🙃","😉","😊","😇","🥰","😍","🤩","😘","😗","😙","😚","😋","😛","😜","🤪","😝","🤑","🤗","🤭","🫢","🫣","🤫","🤔","🫡","🤐","🤨","😐","😑","😶","😏","😒","🙄","😬","😮‍💨","🤥","🫨","😌","😔","😪","🤤","😴","🥱","😷","🤒","🤕","🤢","🤮","🤧","🥵","🥶","🥴","😵","🤯","🥳","🥸","😎","🤓","🧐","😕","🫤","😟","🙁","☹️","😮","😯","😲","😳","🥺","🥹","😦","😧","😨","😰","😥","😢","😭","😱","😖","😣","😞","😓","😩","😫","😤","😡","😠","🤬","😈","👿","💀","👻","👽","🤖","💩"},
        {"👋","🤚","🖐","✋","🖖","🫱","🫲","🫳","🫴","👌","🤌","🤏","✌","🤞","🫰","🤟","🤘","🤙","👈","👉","👆","👇","☝","🫵","👍","👎","✊","👊","🤛","🤜","👏","🙌","🫶","👐","🤲","🤝","🙏","💪","🦾","🖕","🦶","🦵","👀","👁","👄","🫦","👶","🧒","👧","👨","👩","🧑","👴","👵","👨‍💻","👩‍💻","👨‍👩‍👧","🧑‍🚀","🧑‍🎨"},
        {"🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐻‍❄️","🐨","🐯","🦁","🐮","🐷","🐸","🐵","🙈","🙉","🙊","🐒","🐔","🐧","🐦","🐤","🦆","🦅","🦉","🦇","🐺","🐗","🐴","🦄","🐝","🦋","🐌","🐞","🐜","🦟","🦗","🕷","🦂","🐢","🐍","🦎","🦖","🦕","🐙","🦑","🦐","🦞","🦀","🐡","🐠","🐟","🐬","🐳","🦈","🐊","🐘","🦒","🦘","🦥","🌸","🌺","🌻","🌷","🌹","🍀","🌲","🌴","🍄"},
        {"🍎","🍐","🍊","🍋","🍌","🍉","🍇","🍓","🫐","🍈","🍒","🍑","🥭","🍍","🥥","🥝","🍅","🍆","🥑","🥦","🥬","🥒","🌶","🫑","🌽","🥕","🧄","🧅","🥔","🍠","🥐","🥯","🍞","🥖","🥨","🧀","🥚","🍳","🥞","🧇","🥓","🥩","🍗","🍖","🌭","🍔","🍟","🍕","🥪","🥙","🧆","🌮","🌯","🥗","🍝","🍜","🍲","🍣","🍱","🍤","🍙","🍚","🍛","🍦","🍩","🍪","🎂","🍰","🍫","🍬","☕","🧋","🍹"},
        {"🚗","🚕","🚙","🚌","🚎","🏎","🚓","🚑","🚒","🚚","🚛","🚜","🛵","🏍","🚲","🛴","🚆","🚄","🚅","🚈","🚇","🚉","✈️","🚀","🛸","🚁","🚢","⛵","🏠","🏡","🏢","🏥","🏫","🏰","🗽","🗼","🌍","🌎","🌏","🌙","🌟","⭐","☀️","🌤","🌧","⛈","🌈","❄️","🌊","🔥","🎡","🎢","🏖","🏕","⛰","🗻","🏟"},
        {"💡","📱","💻","🖥","⌨️","🖱","🖨","📷","📸","📺","📻","🎙","🎧","🎤","🎼","🎵","🎶","🎸","🎹","🥁","📞","☎️","📲","🔋","🪫","🔌","💽","💾","💿","📀","💡","🔦","🕯","🪔","📚","📖","📕","📗","📘","📙","📓","📔","📝","✏️","🖊","🖋","📎","📌","📍","📏","📐","🔒","🔓","🔑","🗝","🛠","⚙️","🔧","🪛","🔨","🧲","🔬","🧬","💊","🩺","🧪","💰","💳","🪙","🎁","🎈","🎉"},
        {"❤️","🧡","💛","💚","💙","💜","🖤","🤍","🤎","🩷","🩵","🩶","💔","❤️‍🔥","💕","💞","💓","💗","💖","💘","💝","💟","☮️","✝️","☪️","☯️","☸️","✡️","🕉","🔯","♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓","✅","❌","❎","✔️","✖️","➕","➖","➗","‼️","⁉️","❗","❓","💯","♻️","🔴","🟠","🟡","🟢","🔵","🟣","⚫","⚪","🟤"},
        {"🇷🇴","🇲🇩","🇪🇺","🇬🇧","🇺🇸","🇫🇷","🇩🇪","🇮🇹","🇪🇸","🇵🇹","🇳🇱","🇧🇪","🇦🇹","🇨🇭","🇵🇱","🇨🇿","🇭🇺","🇬🇷","🇹🇷","🇺🇦","🇸🇪","🇳🇴","🇩🇰","🇫🇮","🇯🇵","🇰🇷","🇨🇳","🇮🇳","🇨🇦","🇧🇷","🇦🇺","🇿🇦","🏳️‍🌈","🏴‍☠️"}
    };

    private static final String[] TONES = {"", "🏻", "🏼", "🏽", "🏾", "🏿"};
    private static final String[][] ICONS = {{"☺","Fețe"},{"✋","Gesturi"},{"🐾","Animale"},{"🍕","Mâncare"},{"🚗","Locuri"},{"💡","Obiecte"},{"♥","Simboluri"},{"⚑","Steaguri"}};
    private static final String TONEABLE = "👋🤚🖐✋🖖🫱🫲🫳🫴👌🤌🤏✌🤞🫰🤟🤘🤙👈👉👆👇☝🫵👍👎✊👊🤛🤜👏🙌🫶👐🤲🙏💪🖕";

    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }

    private Button button(String text, int size) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(size);
        b.setPadding(0, 0, 0, 0);
        b.setMinWidth(0);
        b.setMinimumWidth(0);
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        GradientDrawable bg = new GradientDrawable();
        bg.setCornerRadius(dp(9));
        bg.setColor(Color.rgb(57, 67, 82));
        b.setBackground(bg);
        return b;
    }

    @Override public void onCreate() {
        // Disable original LatinIME's configurable personalization before initialization.
        // This does not remove all original dictionary code, so no zero-retention claim.
        android.content.SharedPreferences prefs =
                android.preference.PreferenceManager.getDefaultSharedPreferences(this);
        android.content.SharedPreferences.Editor editor = prefs.edit();
        editor.putBoolean("pref_key_use_personalized_dicts", false);
        editor.putBoolean("pref_key_use_contacts_dict", false);
        int personalId = getResources().getIdentifier(
                "pref_key_use_personalized_dicts", "string", getPackageName());
        if (personalId != 0) editor.putBoolean(getString(personalId), false);
        int contactsId = getResources().getIdentifier(
                "pref_key_use_contacts_dict", "string", getPackageName());
        if (contactsId != 0) editor.putBoolean(getString(contactsId), false);
        editor.apply();
        super.onCreate();
    }

    @Override public View onCreateInputView() {
        latinView = super.onCreateInputView();
        if (latinView == null) return null;
        glassRoot = new FrameLayout(this);
        glassRoot.addView(latinView, new FrameLayout.LayoutParams(-1, -2));
        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        FrameLayout.LayoutParams actionsParams = new FrameLayout.LayoutParams(dp(92), dp(42), Gravity.TOP | Gravity.RIGHT);
        actionsParams.rightMargin = dp(4);
        Button emojis = button("☺+", 15);
        actions.addView(emojis, new LinearLayout.LayoutParams(0, dp(38), 1));
        emojis.setOnClickListener(v -> toggleEmojis());
        Button settings = button("⚙", 17);
        actions.addView(settings, new LinearLayout.LayoutParams(0, dp(38), 1));
        settings.setOnClickListener(v -> {
            Intent intent = new Intent(this, GlassSettingsActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        });
        glassRoot.addView(actions, actionsParams);
        emojiPicker = new LinearLayout(this);
        emojiPicker.setOrientation(LinearLayout.VERTICAL);
        emojiPicker.setBackgroundColor(Color.rgb(26, 32, 42));
        emojiPicker.setVisibility(View.GONE);
        FrameLayout.LayoutParams pickParams = new FrameLayout.LayoutParams(-1, dp(253), Gravity.BOTTOM);
        glassRoot.addView(emojiPicker, pickParams);
        buildEmojiPicker();
        applyGlass();
        return glassRoot;
    }

    private void buildEmojiPicker() {
        if (emojiPicker == null) return;
        emojiPicker.removeAllViews();
        LinearLayout tabs = new LinearLayout(this);
        tabs.setOrientation(LinearLayout.HORIZONTAL);
        HorizontalScrollView scroller = new HorizontalScrollView(this);
        scroller.setHorizontalScrollBarEnabled(false);
        scroller.addView(tabs);
        emojiPicker.addView(scroller, new LinearLayout.LayoutParams(-1, dp(44)));
        for (int i = 0; i < ICONS.length; i++) {
            final int selected = i;
            Button tab = button(ICONS[i][0], 20);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(51), dp(40));
            lp.setMargins(dp(2), 0, dp(2), 0);
            tabs.addView(tab, lp);
            tab.setOnClickListener(v -> { category = selected; populateEmojiGrid(); });
        }
        Button toneButton = button("Ton piele " + (tone == 0 ? "auto" : TONES[tone]), 12);
        emojiPicker.addView(toneButton, new LinearLayout.LayoutParams(-1, dp(31)));
        toneButton.setOnClickListener(v -> { tone = (tone + 1) % TONES.length; buildEmojiPicker(); });
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        emojiPicker.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        emojiGrid = new GridLayout(this);
        emojiGrid.setColumnCount(8);
        scroll.addView(emojiGrid, new ScrollView.LayoutParams(-1, -2));
        populateEmojiGrid();
        Button close = button("Înapoi la litere", 14);
        emojiPicker.addView(close, new LinearLayout.LayoutParams(-1, dp(34)));
        close.setOnClickListener(v -> emojiPicker.setVisibility(View.GONE));
    }

    private void populateEmojiGrid() {
        if (emojiGrid == null) return;
        emojiGrid.removeAllViews();
        for (String base : EMOJI[category]) {
            String glyph = base;
            if (tone > 0 && TONEABLE.contains(base) && base.codePointCount(0, base.length()) == 1) {
                glyph = base + TONES[tone];
            }
            final String emoji = glyph;
            Button item = button(emoji, 23);
            item.setContentDescription(emoji);
            GridLayout.LayoutParams params = new GridLayout.LayoutParams();
            params.width = 0;
            params.height = dp(46);
            params.columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f);
            params.setMargins(dp(1), dp(1), dp(1), dp(1));
            emojiGrid.addView(item, params);
            item.setOnClickListener(v -> {
                InputConnection connection = getCurrentInputConnection();
                if (connection != null) connection.commitText(emoji, 1);
            });
        }
    }

    private void toggleEmojis() {
        if (emojiPicker != null) {
            emojiPicker.setVisibility(emojiPicker.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
        }
    }

    private void setBackgroundOfOriginal(View v) {
        if (v == null) return;
        String name = v.getClass().getSimpleName();
        if ("MainKeyboardView".equals(name) || "SuggestionStripView".equals(name)
                || "EmojiPalettesView".equals(name)) {
            v.setBackgroundColor(Color.TRANSPARENT);
        }
        if (v instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) v;
            for (int i = 0; i < group.getChildCount(); i++) setBackgroundOfOriginal(group.getChildAt(i));
        }
    }

    private void applyGlass() {
        if (glassRoot == null) return;
        int opacity = Math.max(0, Math.min(100, getSharedPreferences(GlassSettingsActivity.PREFS, MODE_PRIVATE)
                .getInt(GlassSettingsActivity.OPACITY, 38)));
        glassRoot.setBackgroundColor(Color.argb(Math.round(opacity * 2.55f), 27, 34, 46));
        setBackgroundOfOriginal(latinView);
        if (getWindow() != null) {
            Window window = getWindow().getWindow();
            if (window != null) {
                window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
                if (Build.VERSION.SDK_INT >= 31) {
                    int blur = getSharedPreferences(GlassSettingsActivity.PREFS, MODE_PRIVATE)
                            .getInt(GlassSettingsActivity.BLUR, 24);
                    WindowManager.LayoutParams attrs = window.getAttributes();
                    attrs.flags |= WindowManager.LayoutParams.FLAG_BLUR_BEHIND;
                    attrs.setBlurBehindRadius(dp(blur));
                    window.setAttributes(attrs);
                }
            }
        }
    }

    @Override public void onStartInputView(EditorInfo info, boolean restarting) {
        super.onStartInputView(info, restarting);
        if (emojiPicker != null) emojiPicker.setVisibility(View.GONE);
        applyGlass();
    }

    @Override public void onWindowShown() {
        super.onWindowShown();
        applyGlass();
    }

    @Override public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        applyGlass();
    }

    @Override public void onDestroy() {
        emojiGrid = null; emojiPicker = null; latinView = null; glassRoot = null;
        super.onDestroy();
    }
}
