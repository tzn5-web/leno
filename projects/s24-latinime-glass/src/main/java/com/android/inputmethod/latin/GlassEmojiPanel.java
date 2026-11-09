package com.android.inputmethod.latin;

import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputConnection;
import android.widget.BaseAdapter;
import android.widget.GridView;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.Locale;
import java.util.ArrayList;
import java.util.List;

/**
 * Entirely local emoji browser. Search is typed with an embedded search pad;
 * it never goes through the app's focused InputConnection.
 * Zero favourites, zero usage history, no retained typing data.
 */
public final class GlassEmojiPanel {
    private final GlassIME host;
    private final Runnable exit;
    private LinearLayout body;
    private GridView grid;
    private BaseAdapter adapter;
    private final List<EmojiEntry> all = new ArrayList<>();
    private final List<EmojiEntry> filtered = new ArrayList<>();

    private static final class EmojiEntry {
        final String emoji;
        final String name;
        final int group;
        EmojiEntry(String emoji, String name, int group) {
            this.emoji = emoji;
            this.name = name.toLowerCase(Locale.ROOT);
            this.group = group;
        }
    }
    private TextView queryLabel;
    private LinearLayout searchPad;
    private int category = 0;
    private String query = "";

    private static final String[] CATEGORIES = {
        "Toate", "Fețe", "Oameni", "Animale", "Mâncare",
        "Călătorii", "Simboluri", "Steaguri"
    };

    // Display values and search labels. All are fixed Unicode literals, not remotely loaded.
    private static final String[] CATALOG = {
        "😀=zambet smile fericit;😃=zambet vesel;😄=fericit happy;😁=dinti grin;😆=ras laugh;😅=ras sudoare;🤣=hohote rofl;😂=lacrimi ras;🙂=zambet bland;🙃=invers upside;😉=wink cu ochiul;😊=timid blush;😇=inger angel;🥰=iubire love;😍=inimioare eyes;🤩=star struck;😘=pupic kiss;😗=kiss;😚=pupic;😋=gustos yummy;😛=limba tongue;😜=nebun wink;🤪=crazy;🤨=spranceana;🧐=monoclu;🤓=tocilar nerd;😎=ochelari soare cool;🥸=deghizat;🥳=petrecere party;😏=ironic smirk;😒=dezamagit;😞=trist sad;😔=trist;😢=plange cry;😭=plans crying;😤=furios;😠=nervos angry;😡=rosu furie;🤬=injura;😱=speriat;😨=frica;😰=panicat;😥=trist sudoare;😓=obosit;🤗=imbratisare;🤔=gandire think;🤭=mana la gura;🤫=liniste shush;🤥=mincinos;😶=fara gura;😐=neutru;😑=lipsit expresie;😬=grimasa;🙄=ochi rotiti;😴=somn sleep;🤤=saliva;😷=masca;🤒=bolnav;🤕=ranit;🤢=greata;🤮=vomita;🥶=frig;🥵=cald;🤯=explozie cap;😵=ameteli;🥹=emotionat;🫠=topire;🫶=inima maini",
        "👋=salut wave;👋🏻=salut deschis light;👋🏼=salut piele;👋🏽=salut mediu;👋🏾=salut inchis;👋🏿=salut dark;🤚=mana;🖐️=cinci palma;✋=stop palma;🖖=vulcan;👌=ok;🤌=pinched;🤏=putin;✌️=pace peace;🤞=noroc fingers;🤟=love u;🤘=rock;🤙=telefon call;👈=stanga;👉=dreapta;👆=sus;👇=jos;👍=like;👍🏻=like piele deschis;👍🏼=like piele;👍🏽=like mediu;👍🏾=like inchis;👍🏿=like foarte inchis;👎=dislike;✊=pumn;👊=fist;🤛=pumn stanga;🤜=pumn dreapta;👏=aplauze clap;🙌=ura hooray;👐=maini;🤲=rugaciune;🙏=multumesc please;🤝=strangere mana;💪=muschi putere;🦾=brat robot;🖕=middle finger;✍️=scrie;💅=unghii;🤳=selfie;👶=bebelus baby;🧒=copil;👩=femeie;👨=barbat;🧑=persoana;👵=bunica;👴=bunic;👮=politist;👩‍⚕️=doctor;👨‍💻=programator;🧑‍🚀=astronaut;👑=coroana",
        "🐶=caine dog;🐱=pisica cat;🐭=soarece mouse;🐹=hamster;🐰=iepure rabbit;🦊=vulpe fox;🐻=urs bear;🐼=panda;🐻‍❄️=polar bear;🐨=koala;🐯=tigru tiger;🦁=leu lion;🐮=vaca cow;🐷=porc pig;🐸=broasca frog;🐵=maimuta monkey;🙈=nu vad;🙉=nu aud;🙊=nu vorbesc;🐒=monkey;🐔=gaina hen;🐧=pinguin penguin;🐦=pasare bird;🐤=pui chick;🦆=rata duck;🦅=vultur;🦉=bufnita owl;🦇=liliac bat;🐺=lup wolf;🐗=mistret;🐴=cal horse;🦄=unicorn;🐝=albina bee;🪲=gandac;🦋=fluture butterfly;🐌=melc snail;🐞=buburuza;🐢=broasca testoasa;🐍=sarpe snake;🦎=soparla;🦖=dinozaur;🐙=caracatita;🦑=calamar;🦐=crevete;🦀=crab;🐠=peste fish;🐬=delfin;🐳=balena whale;🦈=rechin shark;🦭=foca;🦜=papagal;🪿=gasca goose;🌷=floare;🌹=trandafir rose;🌻=floarea soarelui;🌵=cactus;🌴=palmier;🌳=copac;🍀=trifoi noroc",
        "🍎=mar apple;🍏=mar verde;🍐=para pear;🍊=portocala orange;🍋=lamaie lemon;🍌=banana;🍉=pepene watermelon;🍇=struguri grapes;🍓=capsuni strawberry;🫐=afine;🍒=cirese cherry;🍑=piersica peach;🥭=mango;🍍=ananas pineapple;🥥=cocos coconut;🥝=kiwi;🍅=rosie tomato;🥑=avocado;🍆=vanata;🥔=cartof potato;🥕=morcov carrot;🌽=porumb corn;🌶️=ardei iute;🥒=castravete;🥦=broccoli;🧄=usturoi;🧅=ceapa;🍄=ciuperca;🥜=arahide;🍞=paine bread;🥐=croissant;🥖=bagheta;🧀=branza cheese;🥚=ou egg;🍳=omleta;🥓=bacon;🥩=carne steak;🍗=pulpa chicken;🍖=carne os;🌭=hot dog;🍔=burger;🍟=cartofi prajiti;🍕=pizza;🥪=sandvis sandwich;🌮=taco;🌯=burrito;🥗=salata salad;🍝=paste pasta;🍜=supa noodles;🍣=sushi;🍚=orez rice;🍱=bento;🍦=inghetata icecream;🎂=tort cake;🍰=prajitura;🍪=biscuit;🍫=ciocolata chocolate;🍬=bomboane;☕=cafea coffee;🍵=ceai tea;🧋=bubble tea;🥤=suc drink;🍺=bere beer",
        "🚗=masina car;🚕=taxi;🚙=suv;🚌=autobuz bus;🚎=troleibuz;🏎️=formula1 race;🚓=politie;🚑=ambulanta;🚒=pompieri;🚐=microbuz;🚚=camion truck;🚜=tractor;🏍️=motocicleta;🚲=bicicleta bike;🛴=trotineta scooter;🚂=tren train;🚆=tren electric;🚇=metrou subway;🚝=monorail;🚠=telecabina;✈️=avion plane;🛫=decolare;🛬=aterizare;🚀=racheta rocket;🛸=ozn ufo;⛵=barca boat;🚢=vapor ship;🏖️=plaja beach;🏝️=insula island;🏔️=munte mountain;🌋=vulcan volcano;🏕️=camping;🏙️=oras city;🌇=apus sunset;🌆=seara;🌃=noapte;🌌=galaxie galaxy;🌍=pamant earth europa;🌎=pamant americi;🌏=pamant asia;🌕=luna plina moon;🌙=luna;☀️=soare sun;🌧️=ploaie rain;⛈️=furtuna storm;❄️=zapada snow;🌈=curcubeu rainbow",
        "❤️=inima rosie love;🧡=inima portocalie;💛=inima galbena;💚=inima verde;💙=inima albastra;💜=inima mov;🖤=inima neagra;🤍=inima alba;🤎=inima maro;💖=inima sclipici;💕=doua inimi;💞=inimi rotite;💘=inima sageata;💝=inima cadou;💔=inima rupta;❤️‍🔥=inima foc;❤️‍🩹=inima vindecata;💯=suta;✅=bifat check;☑️=check box;✔️=corect;❌=x gresit;❎=x verde;⚠️=avertizare warning;⛔=interzis stop;🚫=nu;‼️=semne exclamare;❗=exclamare;❓=intrebare question;💬=mesaj chat;🗨️=mesaj;💭=gand;💤=somn;💥=explozie;🔥=foc fire;✨=sclipici sparkles;⭐=stea star;🌟=stea stralucitoare;🎉=party confetti;🎊=petrecere;🎁=cadou gift;🎈=balon;🔔=clopot bell;🔒=lacat lock;🔓=deblocat;🔑=cheie key;🛡️=scut shield;⚙️=setari settings;🔧=cheie scule;💡=bec idea;💻=laptop;📱=telefon phone;📸=camera foto;🎧=casti headphones;🎵=muzica music;🎶=note music;▶️=play;⏸️=pauza;⏭️=next;🔋=baterie;🔌=priza;📶=semnal;📡=antena;💸=bani money;💰=sac bani",
        "🇷🇴=romania romanian;🇲🇩=moldova;🇪🇺=europa european union;🇬🇧=marea britanie uk;🇺🇸=statele unite usa;🇩🇪=germania germany;🇫🇷=franta france;🇮🇹=italia italy;🇪🇸=spania spain;🇵🇹=portugalia;🇳🇱=olanda netherlands;🇧🇪=belgia belgium;🇨🇭=elvetia switzerland;🇦🇹=austria;🇵🇱=polonia poland;🇨🇿=cehia czech;🇬🇷=grecia greece;🇹🇷=turcia turkey;🇺🇦=ucraina ukraine;🇯🇵=japonia japan;🇨🇳=china;🇰🇷=coreea korea;🇮🇳=india;🇧🇷=brazilia;🇨🇦=canada;🇦🇺=australia;🇲🇽=mexic mexico"
    };

    public GlassEmojiPanel(GlassIME host, Runnable exit) {
        this.host = host;
        this.exit = exit;
        for (int group = 0; group < CATALOG.length; group++) {
            for (String item : CATALOG[group].split(";")) {
                int eq = item.indexOf('=');
                if (eq > 0) all.add(new EmojiEntry(
                        item.substring(0, eq), item.substring(eq + 1), group + 1));
            }
        }
    }

    private int dp(int n) {
        return Math.round(n * host.getResources().getDisplayMetrics().density);
    }

    private TextView chip(String text, int size) {
        TextView view = new TextView(host);
        view.setText(text);
        view.setTextColor(Color.WHITE);
        view.setTextSize(size);
        view.setGravity(Gravity.CENTER);
        view.setPadding(dp(7), dp(3), dp(7), dp(3));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.argb(200, 68, 75, 93));
        bg.setCornerRadius(dp(9));
        view.setBackground(bg);
        return view;
    }

    public View makeView() {
        body = new LinearLayout(host);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(dp(3), dp(5), dp(3), dp(5));
        body.setBackgroundColor(Color.argb(238, 24, 29, 42));

        LinearLayout header = new LinearLayout(host);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView search = chip("⌕  Caută emoji", 15);
        queryLabel = search;
        header.addView(search, new LinearLayout.LayoutParams(0, dp(36), 1));
        search.setOnClickListener(v -> {
            searchPad.setVisibility(searchPad.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
        });
        TextView clear = chip("⌫", 20);
        header.addView(clear, new LinearLayout.LayoutParams(dp(40), dp(36)));
        clear.setOnClickListener(v -> {
            if (!query.isEmpty()) query = query.substring(0, query.length() - 1);
            showQuery();
        });
        TextView done = chip("✕", 20);
        header.addView(done, new LinearLayout.LayoutParams(dp(40), dp(36)));
        done.setOnClickListener(v -> exit.run());
        body.addView(header);

        HorizontalScrollView scrollCategories = new HorizontalScrollView(host);
        scrollCategories.setHorizontalScrollBarEnabled(false);
        LinearLayout tabs = new LinearLayout(host);
        tabs.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i < CATEGORIES.length; i++) {
            int selected = i;
            TextView tab = chip(CATEGORIES[i], 12);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, dp(35));
            lp.setMargins(dp(2), dp(3), dp(2), dp(2));
            tabs.addView(tab, lp);
            tab.setOnClickListener(v -> {
                category = selected;
                displayEmojis();
            });
        }
        scrollCategories.addView(tabs);
        body.addView(scrollCategories);

        // Virtualized grid: reuses only visible emoji cells while scrolling.
        grid = new GridView(host);
        grid.setNumColumns(7);
        grid.setColumnWidth(dp(43));
        grid.setHorizontalSpacing(dp(2));
        grid.setVerticalSpacing(dp(1));
        grid.setStretchMode(GridView.STRETCH_COLUMN_WIDTH);
        grid.setSmoothScrollbarEnabled(false);
        grid.setCacheColorHint(Color.TRANSPARENT);
        adapter = new BaseAdapter() {
            @Override public int getCount() { return filtered.size(); }
            @Override public Object getItem(int position) { return filtered.get(position); }
            @Override public long getItemId(int position) { return position; }
            @Override public View getView(int position, View reused, ViewGroup parent) {
                TextView icon = reused instanceof TextView ? (TextView) reused : new TextView(host);
                if (reused == null) {
                    icon.setTextSize(25);
                    icon.setGravity(Gravity.CENTER);
                    icon.setLayoutParams(new android.widget.AbsListView.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT, dp(44)));
                }
                EmojiEntry entry = filtered.get(position);
                icon.setText(entry.emoji);
                icon.setContentDescription(entry.name);
                return icon;
            }
        };
        grid.setAdapter(adapter);
        grid.setOnItemClickListener((parent, view, position, id) -> {
            if (position >= filtered.size()) return;
            InputConnection connection = host.getCurrentInputConnection();
            if (connection != null) connection.commitText(filtered.get(position).emoji, 1);
        });
        body.addView(grid, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        searchPad = new LinearLayout(host);
        searchPad.setOrientation(LinearLayout.VERTICAL);
        searchPad.setVisibility(View.GONE);
        addSearchRow("qwertyuiop");
        addSearchRow("asdfghjkl");
        addSearchRow("zxcvbnm");
        body.addView(searchPad);

        showQuery();
        return body;
    }

    private void addSearchRow(String chars) {
        LinearLayout row = new LinearLayout(host);
        row.setGravity(Gravity.CENTER);
        for (int i = 0; i < chars.length(); i++) {
            final String c = chars.substring(i, i + 1);
            TextView k = chip(c, 14);
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(32), 1);
            p.setMargins(dp(1), dp(1), dp(1), dp(1));
            row.addView(k, p);
            k.setOnClickListener(v -> {
                if (query.length() < 30) query += c;
                showQuery();
            });
        }
        searchPad.addView(row);
    }

    private void showQuery() {
        if (queryLabel != null) queryLabel.setText(query.isEmpty()
                ? "⌕  Caută emoji (local)" : "⌕  " + query);
        displayEmojis();
    }

    private void displayEmojis() {
        if (grid == null) return;
        String needle = query.toLowerCase(Locale.ROOT);
        filtered.clear();
        for (EmojiEntry entry : all) {
            if (category != 0 && category != entry.group) continue;
            if (!needle.isEmpty() && !entry.name.contains(needle)
                    && !entry.emoji.contains(needle)) continue;
            filtered.add(entry);
        }
        adapter.notifyDataSetChanged();
        grid.setSelection(0);
    }
}
