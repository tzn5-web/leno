package dev.tzn5.privatekeyboard;

import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.inputmethodservice.InputMethodService;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.Window;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.PopupWindow;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Fully offline IME. Preferences contain appearance only; no input text or emoji history. */
public final class KeyboardService extends InputMethodService implements SharedPreferences.OnSharedPreferenceChangeListener {
    private static final String PREFS = "appearance";
    private static final String[] CATEGORIES = {"☺", "♟", "✿", "♨", "★", "✈", "✎", "♥"};
    private static final String[][] EMOJIS = {
        {"😀","😃","😄","😁","😆","😅","🤣","😂","🙂","🙃","😉","😊","😇","🥰","😍","🤩","😘","😗","😚","😋","😛","😜","🤪","😝","🤗","🤭","🫢","🤫","🤔","🫡","🤐","🤨","😐","😑","😶","😏","😒","🙄","😬","😮‍💨","😌","😔","😪","🤤","😴","🥱","😷","🤒","🤕","🤢","🤮","🥵","🥶","🥴","😵‍💫","🤯","🥳","🥹","😎","🤓","🧐","😕","🙁","☹️","😮","😲","😳","🥺","😢","😭","😱","😖","😣","😞","😓","😤","😡","🤬","👻","💀","🤖","👽"},
        {"👋","🤚","🖐️","✋","🖖","🫱","🫲","👌","🤌","🤏","✌️","🤞","🫰","🤟","🤘","🤙","👈","👉","👆","👇","☝️","👍","👎","✊","👊","🤛","🤜","👏","🙌","🫶","🤲","🙏","✍️","💪","🦾","🦵","🦶","👂","👃","🧠","🫀","👀","👅","👶","🧒","👦","👧","🧑","👨","👩","🧓","👴","👵","👮","👷","🧑‍💻","🧑‍🔬","🧑‍🚀","🧑‍🍳","🧑‍⚕️","🧑‍🎓","👨‍👩‍👧","🫂"},
        {"🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐨","🐯","🦁","🐮","🐷","🐸","🐵","🐔","🐧","🐦","🦆","🦉","🦅","🦋","🐛","🐝","🐞","🦄","🐴","🐢","🐍","🦎","🦖","🐙","🦀","🐬","🐳","🦈","🐊","🐘","🦒","🦘","🐿️","🌹","🌷","🌻","🌼","🪻","🌸","🌺","🌱","🌲","🌴","🍀","🍁","🍂","🔥","🌈","☀️","🌙","⭐","✨","⚡","❄️","🌊"},
        {"🍎","🍐","🍊","🍋","🍌","🍉","🍇","🍓","🫐","🍒","🍑","🥭","🍍","🥥","🥝","🍅","🥑","🥦","🥒","🌶️","🌽","🥕","🥐","🥖","🍞","🧀","🥚","🍳","🥞","🥓","🍔","🍟","🍕","🌭","🥪","🌮","🌯","🥗","🍝","🍜","🍣","🍤","🍱","🍙","🍚","🍘","🍡","🥟","🍦","🍨","🍩","🍪","🎂","🍰","🍫","🍬","🍿","☕","🧋","🥤","🍵","🧃","🍹","🍺"},
        {"⚽","🏀","🏈","⚾","🎾","🏐","🏉","🎱","🏓","🏸","🥅","🏒","🏏","🥊","🥋","⛳","🛹","🛼","🛷","⛸️","🎿","🏂","🏋️","🚴","🏊","🧘","🎯","🎮","🕹️","🎲","🧩","🎸","🎹","🥁","🎺","🎷","🎻","🎤","🎧","🎬","🎨","🎭","🎟️","🎫","🏆","🥇","🥈","🥉","🎉","🎊","🎈","🎁","🎀","🎃","🎄"},
        {"🚗","🚕","🚙","🚌","🚎","🏎️","🚓","🚑","🚒","🚐","🛻","🚚","🚜","🏍️","🛵","🚲","🛴","🚨","🚦","🚥","⛽","🛞","✈️","🛫","🛬","🚀","🛸","🚁","🚂","🚆","🚇","🚊","🚢","⛵","🛥️","🛶","🏠","🏡","🏢","🏰","🏯","🗼","🗽","🌋","🏝️","🏔️","🌍","🌎","🌏","🧭","🗺️","⛺","🌅","🌃","🌉"},
        {"📱","💻","🖥️","⌨️","🖱️","🖨️","📷","📸","📹","🎥","📺","📻","🎙️","⏰","⌚","🔋","🪫","💡","🔦","🕯️","📞","☎️","📟","📠","💾","💿","📀","🧮","📚","📖","📝","✏️","📏","📐","📎","🔗","📌","📍","✂️","🔒","🔓","🔑","🗝️","🔨","🪛","🔧","⚙️","🧲","🧪","🧬","🔬","🔭","💊","🩺","💰","💳"},
        {"❤️","🩷","🧡","💛","💚","💙","🩵","💜","🤎","🖤","🩶","🤍","💔","❣️","💕","💞","💓","💗","💖","💘","💝","✅","❌","⚠️","❗","❓","‼️","⁉️","💯","🔥","💫","💥","💬","🗯️","💭","💤","♻️","🔞","🚫","🚭","🔕","🔔","🔊","🔇","🔍","🔎","🔴","🟠","🟡","🟢","🔵","🟣","⚫","⚪","🟤","▪️","▫️","◼️","◻️","▶️","⏸️","⏹️","⏭️","⬆️","⬇️","⬅️","➡️","↩️","↪️","🔄","🔁","🔀","➕","➖","➗","✖️"}
    };
    private SharedPreferences prefs;
    private LinearLayout root;
    private LinearLayout keyArea;
    private TextView shiftKey;
    private final List<TextView> letters = new ArrayList<>();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable repeatTask;
    private PopupWindow accentPopup;
    private boolean shift, caps, symbols, emoji;
    private int category;
    private int accent = Color.rgb(174, 191, 212);
    private int rowHeight = 51;

    @Override public void onCreate() {
        super.onCreate();
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        prefs.registerOnSharedPreferenceChangeListener(this);
    }

    private int dp(float n) { return Math.round(n * getResources().getDisplayMetrics().density); }

    @Override public boolean onEvaluateFullscreenMode() { return false; }

    @Override public View onCreateInputView() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(4), dp(3), dp(4), dp(8));
        root.setClipToPadding(false);
        applyAppearance();
        draw();
        return root;
    }

    @Override public void onStartInput(EditorInfo info, boolean restarting) {
        super.onStartInput(info, restarting);
        stopRepeat();
        shift = false; caps = false; emoji = false; category = 0;
        int kind = info == null ? 0 : (info.inputType & InputType.TYPE_MASK_CLASS);
        symbols = kind == InputType.TYPE_CLASS_NUMBER || kind == InputType.TYPE_CLASS_PHONE || kind == InputType.TYPE_CLASS_DATETIME;
        if (root != null) draw();
    }

    @Override public void onSharedPreferenceChanged(SharedPreferences p, String key) {
        if (root != null) { applyAppearance(); draw(); }
    }

    private void applyAppearance() {
        if (prefs == null || root == null) return;
        String theme = prefs.getString("theme", "smoke");
        if ("ruby".equals(theme)) accent = Color.rgb(255, 67, 85);
        else if ("ice".equals(theme)) accent = Color.rgb(116, 204, 255);
        else accent = Color.rgb(174, 191, 212);
        rowHeight = 43 + prefs.getInt("height", 8);
        int transparency = prefs.getInt("transparency", 38);
        int alpha = Math.round((100 - transparency) * 2.55f);
        GradientDrawable bg = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
            new int[] { Color.argb(alpha, 18, 21, 29), Color.argb(alpha, 34, 38, 47) });
        bg.setCornerRadius(dp(16));
        bg.setStroke(dp(1), Color.argb(90, Color.red(accent), Color.green(accent), Color.blue(accent)));
        root.setBackground(bg);
        try {
            Window w = getWindow() == null ? null : getWindow().getWindow();
            if (w != null) {
                w.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
                if (Build.VERSION.SDK_INT >= 31) {
                    // Optional system blur: automatically degrades to translucent colors when unsupported.
                    w.setBackgroundBlurRadius(prefs.getBoolean("blur", false) ? dp(18) : 0);
                }
            }
        } catch (RuntimeException ignored) { /* OEM may disable blur for IME windows. */ }
    }

    private GradientDrawable keyShape(boolean special) {
        int opacity = prefs.getInt("key_opacity", 84);
        int alpha = Math.round(opacity * 2.55f);
        GradientDrawable d = new GradientDrawable();
        if (special) d.setColor(Color.argb(alpha, 66, 73, 86));
        else d.setColor(Color.argb(alpha, 49, 55, 67));
        d.setCornerRadius(dp(3 + prefs.getInt("radius", 5)));
        int borderAlpha = "ruby".equals(prefs.getString("theme", "smoke")) ? 125 : 75;
        d.setStroke(dp(1), Color.argb(borderAlpha, Color.red(accent), Color.green(accent), Color.blue(accent)));
        return d;
    }

    private TextView control(String label, int textSize) {
        TextView v = new TextView(this);
        v.setGravity(Gravity.CENTER);
        v.setText(label);
        v.setTextColor(Color.WHITE);
        v.setTextSize(textSize);
        v.setFocusable(false);
        v.setFocusableInTouchMode(false);
        return v;
    }

    private void draw() {
        if (root == null) return;
        stopRepeat();
        dismissPopup();
        letters.clear();
        shiftKey=null;
        root.removeAllViews();
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        root.addView(toolbar, new LinearLayout.LayoutParams(-1, dp(42)));

        TextView title = control(emoji ? "Emoji" : (symbols ? "Simboluri" : "Română  ·  English"), 13);
        title.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
        title.setPadding(dp(12), 0, 0, 0);
        title.setTextColor(Color.rgb(211, 220, 232));
        toolbar.addView(title, new LinearLayout.LayoutParams(0, -1, 1f));

        TextView toggle = control(emoji ? "ABC" : "☺", emoji ? 15 : 27);
        toggle.setContentDescription(emoji ? "Revenire la litere" : "Emoji");
        toolbar.addView(toggle, new LinearLayout.LayoutParams(dp(52), -1));
        toggle.setOnClickListener(v -> { emoji = !emoji; draw(); });

        GearIcon settings = new GearIcon();
        settings.setContentDescription("Setări tastatură");
        toolbar.addView(settings, new LinearLayout.LayoutParams(dp(48), dp(42)));
        settings.setOnClickListener(v -> {
            Intent i = new Intent(this, SettingsActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        });

        keyArea = new LinearLayout(this);
        keyArea.setOrientation(LinearLayout.VERTICAL);
        root.addView(keyArea, new LinearLayout.LayoutParams(-1, -2));
        if (emoji) drawEmojis();
        else if (symbols) {
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

    private boolean special(String key) {
        return "shift".equals(key) || "del".equals(key) || "enter".equals(key) || "mode".equals(key) || "space".equals(key);
    }

    private String keyLabel(String key) {
        switch (key) {
            case "shift": return caps ? "⇪" : "⇧";
            case "del": return "⌫";
            case "enter": return "↵";
            case "mode": return symbols ? "ABC" : "?123";
            case "space": return "Română  ·  English";
            default: return (caps || shift) && !symbols ? key.toUpperCase(Locale.ROOT) : key;
        }
    }

    private float keyWeight(String key) {
        if ("space".equals(key)) return 4.0f;
        if ("enter".equals(key) || "mode".equals(key) || "shift".equals(key) || "del".equals(key)) return 1.5f;
        return 1f;
    }

    private void addRow(String... keys) {
        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.CENTER);
        row.setOrientation(LinearLayout.HORIZONTAL);
        keyArea.addView(row, new LinearLayout.LayoutParams(-1, dp(rowHeight)));
        for (String key : keys) {
            TextView b = control(keyLabel(key), "space".equals(key) ? 12 : (key.length() > 3 ? 15 : 19));
            b.setContentDescription(keyLabel(key));
            b.setTypeface(Typeface.DEFAULT, Typeface.NORMAL);
            b.setClickable(true);
            b.setLongClickable(true);
            b.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(85,255,255,255)), keyShape(special(key)), null));
            int margin = prefs.getInt("spacing", 2);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(rowHeight - 5), keyWeight(key));
            lp.setMargins(dp(margin),dp(2),dp(margin),dp(2));
            row.addView(b, lp);
            b.setOnClickListener(v -> {
                if(prefs.getBoolean("haptic",false)) v.performHapticFeedback(android.view.HapticFeedbackConstants.KEYBOARD_TAP);
                handle(key);
            });
            if("shift".equals(key)) shiftKey=b;
            if (!special(key) && key.codePointCount(0,key.length()) == 1) {
                letters.add(b);
                b.setTag(key);
                b.setOnLongClickListener(v -> showAccents(b, key));
            }
            if ("shift".equals(key)) b.setOnLongClickListener(v -> {
                caps = !caps; shift = false; updateLabels(); return true;
            });
            if ("del".equals(key)) {
                b.setOnTouchListener((v, ev) -> {
                    if (ev.getActionMasked() == MotionEvent.ACTION_DOWN) {
                        stopRepeat();
                        repeatTask = new Runnable() {
                            @Override public void run() { backspace(); handler.postDelayed(this, 62); }
                        };
                        handler.postDelayed(repeatTask, 390);
                    } else if (ev.getActionMasked() == MotionEvent.ACTION_UP ||
                               ev.getActionMasked() == MotionEvent.ACTION_CANCEL) stopRepeat();
                    return false;
                });
            }
        }
    }

    private void updateLabels() {
        for (TextView v : letters) {
            String key = (String) v.getTag();
            if (key != null) v.setText(keyLabel(key));
        }
        if(shiftKey!=null) shiftKey.setText(caps ? "⇪" : (shift ? "⬆" : "⇧"));
    }

    private void drawEmojis() {
        HorizontalScrollView strip = new HorizontalScrollView(this);
        strip.setHorizontalScrollBarEnabled(false);
        LinearLayout tabs = new LinearLayout(this);
        tabs.setGravity(Gravity.CENTER_VERTICAL);
        strip.addView(tabs);
        keyArea.addView(strip, new LinearLayout.LayoutParams(-1, dp(43)));
        for (int i=0; i<CATEGORIES.length; i++) {
            final int selected = i;
            TextView b = control(CATEGORIES[i], 23);
            b.setContentDescription("Categorie emoji " + (i+1));
            b.setTextColor(i == category ? accent : Color.WHITE);
            b.setBackground(keyShape(i == category));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(44), dp(37));
            lp.setMargins(dp(2),0,dp(2),0);
            tabs.addView(b,lp);
            b.setOnClickListener(v -> { category=selected; draw(); });
        }

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setVerticalScrollBarEnabled(false);
        LinearLayout rows = new LinearLayout(this);
        rows.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(rows);
        keyArea.addView(scroll, new LinearLayout.LayoutParams(-1, dp(rowHeight*5)));
        String[] items = EMOJIS[category];
        final int columns = 7;
        for(int offset=0; offset<items.length; offset+=columns) {
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER);
            rows.addView(row, new LinearLayout.LayoutParams(-1, dp(rowHeight)));
            for(int j=0;j<columns;j++) {
                int index=offset+j;
                if(index>=items.length) {
                    row.addView(new View(this), new LinearLayout.LayoutParams(0,dp(rowHeight-3),1));
                    continue;
                }
                String e=items[index];
                TextView key = control(e, 26);
                key.setContentDescription("Emoji " + e);
                LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(rowHeight-3),1);
                lp.setMargins(dp(1),dp(1),dp(1),dp(1));
                row.addView(key,lp);
                key.setOnClickListener(v -> { if(prefs.getBoolean("haptic",false)) v.performHapticFeedback(android.view.HapticFeedbackConstants.KEYBOARD_TAP); commit(e); });
                if (isSkinToneEmoji(e)) key.setOnLongClickListener(v -> showSkinTones(key,e));
            }
        }
        LinearLayout actions=new LinearLayout(this);
        actions.setGravity(Gravity.CENTER);
        keyArea.addView(actions,new LinearLayout.LayoutParams(-1,dp(rowHeight)));
        TextView abc=control("ABC",16);
        TextView del=control("⌫",24);
        TextView space=control("Spațiu",15);
        TextView enter=control("↵",23);
        for(TextView v : new TextView[]{abc,del,space,enter}) {
            v.setBackground(new RippleDrawable(ColorStateList.valueOf(0x44FFFFFF),keyShape(true),null));
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(rowHeight-5),v==space?2:1);
            lp.setMargins(dp(2),dp(2),dp(2),dp(2)); actions.addView(v,lp);
        }
        abc.setOnClickListener(v -> {emoji=false; draw();});
        del.setOnClickListener(v -> backspace());
        space.setOnClickListener(v -> commit(" "));
        enter.setOnClickListener(v -> handle("enter"));
    }

    private boolean isSkinToneEmoji(String e) {
        return "👍".equals(e)||"👎".equals(e)||"👋".equals(e)||"✋".equals(e)||"👌".equals(e)||"👏".equals(e)||"🙏".equals(e)||"💪".equals(e)||"👊".equals(e)||"🙌".equals(e)||"🤟".equals(e)||"🤙".equals(e);
    }

    private boolean showSkinTones(View anchor,String base) {
        showPopup(anchor,new String[]{base,base+"🏻",base+"🏼",base+"🏽",base+"🏾",base+"🏿"});
        return true;
    }

    private boolean showAccents(View anchor,String key) {
        String[] options;
        switch (key.toLowerCase(Locale.ROOT)) {
            case "a": options=new String[]{"ă","â","á","à","ä"}; break;
            case "i": options=new String[]{"î","í","ì","ï"}; break;
            case "s": options=new String[]{"ș","ş","ß"}; break;
            case "t": options=new String[]{"ț","ţ"}; break;
            case "e": options=new String[]{"é","è","ê","ë"}; break;
            case "o": options=new String[]{"ó","ò","ô","ö"}; break;
            case "u": options=new String[]{"ú","ù","û","ü"}; break;
            default: return false;
        }
        if (shift || caps) {
            for(int i=0;i<options.length;i++) options[i]=options[i].toUpperCase(Locale.ROOT);
        }
        showPopup(anchor,options); return true;
    }

    private void showPopup(View anchor,String[] options) {
        dismissPopup();
        LinearLayout row=new LinearLayout(this);
        row.setBackgroundColor(Color.rgb(33,38,48));
        for(String c : options) {
            TextView t=control(c,22);
            t.setBackground(keyShape(false));
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(dp(48),dp(48));
            lp.setMargins(dp(1),dp(1),dp(1),dp(1));
            row.addView(t,lp);
            t.setOnClickListener(v -> {
                commit(c);
                if(!caps) shift=false;
                updateLabels();
                dismissPopup();
            });
        }
        accentPopup=new PopupWindow(row,dp(50*options.length),dp(50),true);
        accentPopup.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        accentPopup.setOutsideTouchable(true);
        accentPopup.setElevation(dp(8));
        accentPopup.showAsDropDown(anchor,0,-dp(100));
    }

    private void dismissPopup() {
        if (accentPopup!=null) {
            if(accentPopup.isShowing()) accentPopup.dismiss();
            accentPopup=null;
        }
    }

    private void stopRepeat() {
        if(repeatTask!=null){handler.removeCallbacks(repeatTask);repeatTask=null;}
    }

    private void backspace() {
        InputConnection ic=getCurrentInputConnection();
        if(ic!=null && !ic.deleteSurroundingTextInCodePoints(1,0)) {
            ic.sendKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DEL));
            ic.sendKeyEvent(new KeyEvent(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DEL));
        }
    }

    private void commit(String s) {
        InputConnection ic=getCurrentInputConnection();
        if(ic!=null) ic.commitText(s,1);
    }

    private void handle(String key) {
        switch (key) {
            case "shift": shift=!shift; updateLabels(); return;
            case "mode": symbols=!symbols; shift=false; caps=false; draw(); return;
            case "del": backspace(); return;
            case "space": commit(" "); return;
            case "enter":
                InputConnection ic=getCurrentInputConnection();
                if(ic==null) return;
                EditorInfo info=getCurrentInputEditorInfo();
                int act=info==null ? EditorInfo.IME_ACTION_NONE : info.imeOptions&EditorInfo.IME_MASK_ACTION;
                if(act!=EditorInfo.IME_ACTION_NONE && act!=EditorInfo.IME_ACTION_UNSPECIFIED)
                    ic.performEditorAction(act);
                else commit("\n");
                return;
            default:
                commit((shift||caps) && !symbols ? key.toUpperCase(Locale.ROOT):key);
                if(shift){shift=false; updateLabels();}
        }
    }

    @Override public void onFinishInputView(boolean finishingInput) {
        stopRepeat(); dismissPopup(); super.onFinishInputView(finishingInput);
    }

    @Override public void onDestroy() {
        stopRepeat(); dismissPopup();
        if(prefs!=null) prefs.unregisterOnSharedPreferenceChangeListener(this);
        super.onDestroy();
    }

    private final class GearIcon extends View {
        private final Paint pen=new Paint(Paint.ANTI_ALIAS_FLAG);
        GearIcon(){super(KeyboardService.this);setClickable(true);setFocusable(true);}
        @Override protected void onDraw(Canvas c) {
            super.onDraw(c);
            float x=getWidth()/2f,y=getHeight()/2f;
            pen.setColor(Color.WHITE);pen.setStrokeWidth(dp(2));pen.setStyle(Paint.Style.STROKE);
            for(int i=0;i<8;i++){
                double a=i*Math.PI/4d;
                c.drawLine(x+(float)Math.cos(a)*dp(9),y+(float)Math.sin(a)*dp(9),
                    x+(float)Math.cos(a)*dp(13),y+(float)Math.sin(a)*dp(13),pen);
            }
            c.drawCircle(x,y,dp(9),pen);c.drawCircle(x,y,dp(3),pen);
        }
    }
}
