package dev.velolink.offline;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.RouteInfo;
import android.net.Uri;
import android.net.wifi.SoftApConfiguration;
import android.net.wifi.WifiConfiguration;
import android.net.wifi.WifiManager;
import android.net.wifi.WifiNetworkSpecifier;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.content.ContentValues;
import android.content.Context;
import android.content.res.ColorStateList;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.MultiFormatWriter;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Enumeration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Offline peer-to-peer transfer MVP.
 * RECEIVER generates the QR, SENDER scans it.
 * Android LocalOnlyHotspot needs no internet nor router.
 *
 * NOTE: WPA2 protects the radio hop, one-time QR token authorizes uploads.
 * Foreground-only transfer; keep display awake during the operation.
 */
public final class MainActivity extends Activity {
    private static final int PORT = 47882;
    private static final int REQ_PERM_RECEIVE = 21;
    private static final int REQ_PERM_CAMERA = 22;
    private static final int REQ_FILES = 23;
    private static final int BG = 0xFF091322, PANEL = 0xFF172638;
    private static final int CYAN = 0xFF55EAEE, WHITE = 0xFFF3F7FA;
    private static final int MUTED = 0xFF9DB3C9;
    private final ExecutorService worker = Executors.newFixedThreadPool(3);
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final SecureRandom random = new SecureRandom();
    private final AtomicBoolean receiving = new AtomicBoolean(false);
    private WifiManager.LocalOnlyHotspotReservation reservation;
    private ServerSocket server;
    private ConnectivityManager connectivity;
    private ConnectivityManager.NetworkCallback networkCallback;
    private JSONObject qrData;
    private String receiveToken;
    private final List<Uri> selected = new ArrayList<>();
    private TextView status, speed, intro;
    private ImageView qrView;
    private LinearLayout qrPanel;
    private Button receiveButton, sendButton;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        connectivity = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        drawHome();
    }

    private GradientDrawable background(int color, int border) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(19));
        d.setStroke(dp(1), border);
        return d;
    }

    private int dp(float value) {
        return (int) (value * getResources().getDisplayMetrics().density + .5f);
    }

    private TextView label(String txt, int size, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(txt);
        t.setTextSize(size);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return t;
    }

    private void drawHome() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(22), dp(28), dp(22), dp(28));
        scroll.addView(root);
        setContentView(scroll);

        TextView logo = label("VELOLINK", 32, CYAN, true);
        logo.setLetterSpacing(.1f);
        root.addView(logo);
        TextView subtitle = label("OFFLINE  •  DIRECT  •  NO ADS", 12, MUTED, true);
        subtitle.setPadding(0, dp(4), 0, dp(26));
        root.addView(subtitle);
        intro = label("Transfer rapid prin Wi‑Fi local.\nFără internet, cont sau server extern.", 18, WHITE, false);
        intro.setLineSpacing(dp(4), 1);
        root.addView(intro);

        receiveButton = button("PRIMEȘTE  •  GENEREAZĂ QR");
        LinearLayout.LayoutParams p1 = new LinearLayout.LayoutParams(-1, dp(62));
        p1.topMargin = dp(28);
        root.addView(receiveButton, p1);
        receiveButton.setOnClickListener(v -> requestReceive());

        sendButton = button("TRIMITE  •  SCANEAZĂ QR");
        LinearLayout.LayoutParams p2 = new LinearLayout.LayoutParams(-1, dp(62));
        p2.topMargin = dp(12);
        root.addView(sendButton, p2);
        sendButton.setOnClickListener(v -> requestScan());

        qrPanel = new LinearLayout(this);
        qrPanel.setPadding(dp(15), dp(18), dp(15), dp(18));
        qrPanel.setOrientation(LinearLayout.VERTICAL);
        qrPanel.setGravity(Gravity.CENTER_HORIZONTAL);
        qrPanel.setBackground(background(PANEL, 0xFF284358));
        qrPanel.setVisibility(View.GONE);
        LinearLayout.LayoutParams qp = new LinearLayout.LayoutParams(-1, -2);
        qp.topMargin = dp(22);
        root.addView(qrPanel, qp);
        TextView qrCaption = label("DESTINATAR • SCANEAZĂ-MĂ", 15, CYAN, true);
        qrPanel.addView(qrCaption);
        qrView = new ImageView(this);
        LinearLayout.LayoutParams im = new LinearLayout.LayoutParams(dp(285), dp(285));
        im.topMargin = dp(14);
        qrPanel.addView(qrView, im);

        status = label("Pregătit. Pe telefonul care primește, apasă PRIMEȘTE.", 14, MUTED, false);
        status.setLineSpacing(dp(3), 1);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1, -2);
        sp.topMargin = dp(25);
        root.addView(status, sp);
        speed = label("", 13, CYAN, true);
        LinearLayout.LayoutParams speedP = new LinearLayout.LayoutParams(-1, -2);
        speedP.topMargin = dp(9);
        root.addView(speed, speedP);

        TextView foot = label("Un singur scan • Direct între dispozitive • Salvare în Downloads", 12, MUTED, false);
        LinearLayout.LayoutParams fp = new LinearLayout.LayoutParams(-1, -2);
        fp.topMargin = dp(38);
        root.addView(foot, fp);
    }

    private Button button(String title) {
        Button b = new Button(this);
        b.setText(title);
        b.setTextSize(13);
        b.setAllCaps(false);
        b.setTextColor(BG);
        b.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        b.setBackground(background(CYAN, CYAN));
        return b;
    }

    private void note(String value) {
        ui.post(() -> { if (status != null) status.setText(value); });
    }

    private void progress(long bytes, long total, long start) {
        long ms = Math.max(1, System.currentTimeMillis() - start);
        double mbps = bytes * 8d / (ms / 1000d) / 1_000_000d;
        ui.post(() -> speed.setText(String.format(Locale.US,
            "Transferat %.1f / %.1f MB  •  %.1f Mbps",
            bytes / 1048576d, total / 1048576d, mbps)));
    }

    private String[] receivePermissions() {
        if (Build.VERSION.SDK_INT >= 33)
            return new String[]{Manifest.permission.NEARBY_WIFI_DEVICES};
        return new String[]{Manifest.permission.ACCESS_FINE_LOCATION};
    }

    private void requestReceive() {
        String[] perms = receivePermissions();
        for (String p : perms) {
            if (checkSelfPermission(p) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(perms, REQ_PERM_RECEIVE);
                return;
            }
        }
        openReceiver();
    }

    @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (results.length == 0 || results[0] != PackageManager.PERMISSION_GRANTED) {
            note("Permisiune necesară. Fără aceasta Android nu permite conexiunea.");
            return;
        }
        if (code == REQ_PERM_RECEIVE) openReceiver();
        else if (code == REQ_PERM_CAMERA) openScanner();
    }

    private void openReceiver() {
        if (receiving.get()) {
            note("Recepția este deja pornită. Expeditorul poate scana codul QR.");
            return;
        }
        stopReceiver();
        byte[] secret = new byte[24];
        random.nextBytes(secret);
        receiveToken = Base64.getUrlEncoder().withoutPadding().encodeToString(secret);
        WifiManager wifi = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        note("Pornesc o rețea Wi‑Fi locală fără internet…");
        try {
            wifi.startLocalOnlyHotspot(new WifiManager.LocalOnlyHotspotCallback() {
                @Override public void onStarted(WifiManager.LocalOnlyHotspotReservation r) {
                    reservation = r;
                    String ssid, pass;
                    if (Build.VERSION.SDK_INT >= 30) {
                        SoftApConfiguration ap = r.getSoftApConfiguration();
                        ssid = ap.getSsid();
                        pass = ap.getPassphrase();
                    } else {
                        WifiConfiguration ap = r.getWifiConfiguration();
                        ssid = ap.SSID;
                        pass = ap.preSharedKey;
                    }
                    try {
                        JSONObject obj = new JSONObject();
                        obj.put("v", 1);
                        obj.put("mode", "hotspot");
                        obj.put("ssid", ssid);
                        obj.put("pass", pass);
                        obj.put("token", receiveToken);
                        obj.put("port", PORT);
                        qrData = obj;
                        receiving.set(true);
                        startServer();
                        // AP IPv4 often appears a little after onStarted; network routes on sender are fallback.
                        ui.postDelayed(() -> showReceiverQr(), 1200);
                    } catch (Exception ex) {
                        note("Nu pot genera codul QR: " + ex.getMessage());
                        stopReceiver();
                    }
                }
                @Override public void onFailed(int reason) {
                    note("Hotspot local indisponibil (cod " + reason + "). Activează Wi‑Fi și locația din setările Android.");
                    stopReceiver();
                }
                @Override public void onStopped() {
                    receiving.set(false);
                    note("Rețeaua locală a fost închisă.");
                }
            }, ui);
        } catch (Exception ex) {
            note("Android nu permite hotspot local: " + ex.getMessage());
        }
    }

    private String discoverHotspotIpv4() {
        try {
            Enumeration<NetworkInterface> nets = NetworkInterface.getNetworkInterfaces();
            while (nets.hasMoreElements()) {
                NetworkInterface n = nets.nextElement();
                if (!n.isUp() || n.isLoopback()) continue;
                String name = n.getName().toLowerCase(Locale.US);
                if (!(name.startsWith("wlan") || name.startsWith("ap") ||
                    name.startsWith("swlan") || name.startsWith("wifi"))) continue;
                Enumeration<InetAddress> ips = n.getInetAddresses();
                while (ips.hasMoreElements()) {
                    InetAddress ip = ips.nextElement();
                    if (ip instanceof Inet4Address && ip.isSiteLocalAddress()) {
                        return ip.getHostAddress();
                    }
                }
            }
        } catch (Exception ignored) { }
        return "";
    }

    private void showReceiverQr() {
        if (!receiving.get() || qrData == null) return;
        try {
            // Receiver's address is advisory; sender also checks Wi-Fi gateway.
            String ip = discoverHotspotIpv4();
            qrData.put("host", ip);
            String payload = "VL1:" + Base64.getUrlEncoder().withoutPadding().encodeToString(
                qrData.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
            BitMatrix matrix = new MultiFormatWriter().encode(payload, BarcodeFormat.QR_CODE, 800, 800);
            Bitmap bitmap = Bitmap.createBitmap(800, 800, Bitmap.Config.RGB_565);
            for (int y = 0; y < 800; y++)
                for (int x = 0; x < 800; x++)
                    bitmap.setPixel(x, y, matrix.get(x, y) ? Color.BLACK : Color.WHITE);
            qrView.setImageBitmap(bitmap);
            qrPanel.setVisibility(View.VISIBLE);
            note("QR pregătit. Expeditorul apasă TRIMITE și scanează acest cod.\nInternetul și routerul nu sunt necesare.");
        } catch (Exception ex) {
            note("Generarea QR a eșuat: " + ex.getMessage());
        }
    }

    private void startServer() {
        worker.execute(() -> {
            try (ServerSocket serverSocket = new ServerSocket(PORT, 8)) {
                server = serverSocket;
                serverSocket.setSoTimeout(2000);
                while (receiving.get()) {
                    try {
                        Socket sock = serverSocket.accept();
                        worker.execute(() -> receiveOne(sock));
                    } catch (SocketTimeoutException ignored) { }
                }
            } catch (Exception ex) {
                if (receiving.get()) note("Recepția s-a întrerupt: " + ex.getMessage());
            }
        });
    }

    private void receiveOne(Socket sock) {
        try (Socket socket = sock;
             DataInputStream in = new DataInputStream(new BufferedInputStream(socket.getInputStream(), 1024*1024));
             DataOutputStream out = new DataOutputStream(new BufferedOutputStream(socket.getOutputStream(), 32768))) {
            socket.setSoTimeout(30000);
            socket.setReceiveBufferSize(1024*1024);
            if (!"VL1".equals(in.readUTF()) || !receiveToken.equals(in.readUTF())) {
                out.writeUTF("DENIED");
                out.flush();
                return;
            }
            out.writeUTF("READY");
            out.flush();
            int count = in.readInt();
            if (count < 1 || count > 2000) throw new IllegalArgumentException("Număr de fișiere invalid");
            for (int i = 0; i < count; i++) {
                String name = sanitize(in.readUTF());
                long length = in.readLong();
                if (length < 0 || length > 1_000_000_000_000L)
                    throw new IllegalArgumentException("Dimensiune fișier invalidă");
                note("Primesc " + name + " (" + (i+1) + "/" + count + ")");
                // Transactional MediaStore: incomplete transfers remain hidden until committed.
                ContentValues cv = new ContentValues();
                cv.put(MediaStore.Downloads.DISPLAY_NAME, name);
                cv.put(MediaStore.Downloads.MIME_TYPE, "application/octet-stream");
                cv.put(MediaStore.Downloads.RELATIVE_PATH, "Download/VeloLink");
                cv.put(MediaStore.Downloads.IS_PENDING, 1);
                Uri target = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                if (target == null) throw new IllegalStateException("Downloads unavailable");
                boolean committed = false;
                try (OutputStream file = new BufferedOutputStream(
                    getContentResolver().openOutputStream(target), 1024*1024)) {
                    long left = length, sent = 0;
                    byte[] buffer = new byte[1024*1024];
                    long start = System.currentTimeMillis(), last = 0;
                    while (left > 0) {
                        int n = in.read(buffer, 0, (int)Math.min(left, buffer.length));
                        if (n < 0) throw new java.io.EOFException("Sender disconnected");
                        file.write(buffer, 0, n);
                        sent += n;
                        left -= n;
                        if (System.currentTimeMillis() - last > 450) {
                            progress(sent, length, start);
                            last = System.currentTimeMillis();
                        }
                    }
                    file.flush();
                    cv.clear();
                    cv.put(MediaStore.Downloads.IS_PENDING, 0);
                    committed = getContentResolver().update(target, cv, null, null) > 0;
                } finally {
                    if (!committed) getContentResolver().delete(target, null, null);
                }
                out.writeUTF("OK");
                out.flush();
            }
            note("Transfer finalizat. Fișierele sunt în Downloads/VeloLink.");
        } catch (Exception ex) {
            note("Recepția a eșuat: " + ex.getMessage());
        }
    }

    private String sanitize(String input) {
        String s = input.replace('\\','_').replace('/','_')
            .replace('\n','_').replace('\r','_').replace('\0','_').trim();
        if (s.isEmpty() || s.equals(".") || s.equals("..")) s = "received.bin";
        return s.length() > 175 ? s.substring(s.length() - 175) : s;
    }

    private void requestScan() {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_PERM_CAMERA);
            return;
        }
        openScanner();
    }

    private void openScanner() {
        new IntentIntegrator(this)
            .setDesiredBarcodeFormats(IntentIntegrator.QR_CODE)
            .setPrompt("Scanează codul QR de pe telefonul care primește")
            .setOrientationLocked(false)
            .setBeepEnabled(false)
            .initiateScan();
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        IntentResult scanned = IntentIntegrator.parseActivityResult(request, result, data);
        if (scanned != null) {
            if (scanned.getContents() == null) { note("Scanare anulată."); return; }
            try {
                String qr = scanned.getContents();
                if (!qr.startsWith("VL1:")) throw new IllegalArgumentException("Acesta nu este un cod VeloLink.");
                byte[] decoded = Base64.getUrlDecoder().decode(qr.substring(4));
                qrData = new JSONObject(new String(decoded, java.nio.charset.StandardCharsets.UTF_8));
                if (qrData.getInt("v") != 1 || qrData.getString("token").length() < 12)
                    throw new IllegalArgumentException("Sesiune QR invalidă");
                note("Dispozitivul destinatar a fost identificat. Alege fișierele.");
                Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                picker.setType("*/*");
                picker.addCategory(Intent.CATEGORY_OPENABLE);
                picker.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                startActivityForResult(picker, REQ_FILES);
            } catch (Exception ex) {
                note("QR invalid: " + ex.getMessage());
            }
            return;
        }
        super.onActivityResult(request, result, data);
        if (request == REQ_FILES && result == RESULT_OK && data != null) {
            selected.clear();
            if (data.getClipData() != null) {
                ClipData clip = data.getClipData();
                for (int i = 0; i < clip.getItemCount(); i++) selected.add(clip.getItemAt(i).getUri());
            } else if (data.getData() != null) {
                selected.add(data.getData());
            }
            if (selected.isEmpty()) { note("Nu ai selectat niciun fișier."); return; }
            connectAndSend();
        }
    }

    private void connectAndSend() {
        try {
            String mode = qrData.getString("mode");
            if ("lan".equals(mode)) {
                note("Trimit către PC prin Wi‑Fi local...");
                worker.execute(() -> transferTo(null));
                return;
            }
            if (!"hotspot".equals(mode))
                throw new IllegalArgumentException("Mod de conectare necunoscut");
            WifiNetworkSpecifier.Builder wb = new WifiNetworkSpecifier.Builder()
                .setSsid(qrData.getString("ssid"))
                .setWpa2Passphrase(qrData.getString("pass"));
            NetworkRequest request = new NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .setNetworkSpecifier(wb.build()).build();
            if (networkCallback != null) {
                try { connectivity.unregisterNetworkCallback(networkCallback); }
                catch (Exception ignored) { }
            }
            note("Android va solicita aprobarea conexiunii Wi‑Fi cu destinatarul.");
            networkCallback = new ConnectivityManager.NetworkCallback() {
                @Override public void onAvailable(Network network) {
                    note("Conectat la destinatar. Încep transferul…");
                    worker.execute(() -> transferTo(network));
                }
                @Override public void onUnavailable() {
                    note("Conectarea a expirat. Destinatarul trebuie să păstreze QR-ul deschis.");
                }
                @Override public void onLost(Network network) {
                    note("Conexiunea locală a fost închisă.");
                }
            };
            connectivity.requestNetwork(request, networkCallback, 60000);
        } catch (Exception ex) {
            note("Conectare eșuată: " + ex.getMessage());
        }
    }

    private List<String> destinationCandidates(Network network) {
        LinkedHashSet<String> ips = new LinkedHashSet<>();
        if (network != null) {
            LinkProperties props = connectivity.getLinkProperties(network);
            if (props != null) {
                for (RouteInfo route : props.getRoutes()) {
                    InetAddress gateway = route.getGateway();
                    if (gateway instanceof Inet4Address && !gateway.isAnyLocalAddress())
                        ips.add(gateway.getHostAddress());
                }
            }
        }
        String host = qrData.optString("host", "");
        if (host.matches("\\d{1,3}(\\.\\d{1,3}){3}")) ips.add(host);
        // Manufacturer-specific Android hotspot defaults, only tried if needed.
        ips.add("192.168.43.1");
        ips.add("192.168.49.1");
        ips.add("192.168.45.1");
        return new ArrayList<>(ips);
    }

    private static final class FileInfo {
        Uri uri;
        String name;
        long bytes;
        FileInfo(Uri uri, String name, long bytes) {
            this.uri = uri; this.name = name; this.bytes = bytes;
        }
    }

    private List<FileInfo> prepareFiles() throws Exception {
        List<FileInfo> files = new ArrayList<>();
        for (Uri uri : selected) {
            String name = "file.bin";
            long size = -1;
            try (Cursor cur = getContentResolver().query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}, null, null, null)) {
                if (cur != null && cur.moveToFirst()) {
                    name = cur.getString(0);
                    if (!cur.isNull(1)) size = cur.getLong(1);
                }
            }
            if (size < 0) {
                try (ParcelFileDescriptor fd = getContentResolver().openFileDescriptor(uri, "r")) {
                    if (fd != null) size = fd.getStatSize();
                }
            }
            if (size < 0) throw new IllegalStateException("Dimensiune necunoscută pentru " + name);
            files.add(new FileInfo(uri, sanitize(name), size));
        }
        return files;
    }

    private void transferTo(Network network) {
        try {
            List<FileInfo> files = prepareFiles();
            if (files.isEmpty()) throw new IllegalStateException("Nu ai ales fișiere.");
            int port = qrData.optInt("port", PORT);
            if (port < 1024 || port > 65535) throw new IllegalArgumentException("Port invalid");
            Exception last = null;
            for (String host : destinationCandidates(network)) {
                try {
                    Socket sock = network == null ? new Socket() : network.getSocketFactory().createSocket();
                    sock.connect(new java.net.InetSocketAddress(host, port), 1800);
                    try (Socket socket = sock;
                         DataOutputStream out = new DataOutputStream(
                             new BufferedOutputStream(socket.getOutputStream(), 1024*1024));
                         DataInputStream in = new DataInputStream(
                             new BufferedInputStream(socket.getInputStream(), 32768))) {
                        socket.setSoTimeout(30000);
                        socket.setSendBufferSize(1024*1024);
                        out.writeUTF("VL1");
                        out.writeUTF(qrData.getString("token"));
                        out.flush();
                        if (!"READY".equals(in.readUTF()))
                            throw new SecurityException("Receiver did not accept QR token");
                        out.writeInt(files.size());
                        long overall = 0;
                        for (FileInfo file : files) {
                            note("Trimit " + file.name + "…");
                            out.writeUTF(file.name);
                            out.writeLong(file.bytes);
                            try (InputStream source = new BufferedInputStream(
                                    getContentResolver().openInputStream(file.uri), 1024*1024)) {
                                long left = file.bytes, sent = 0, start = System.currentTimeMillis();
                                long lastProgress = 0;
                                byte[] buffer = new byte[1024*1024];
                                while (left > 0) {
                                    int n = source.read(buffer, 0, (int)Math.min(left, buffer.length));
                                    if (n < 0) throw new java.io.EOFException("Fișierul sursă s-a modificat");
                                    out.write(buffer, 0, n);
                                    left -= n;
                                    sent += n;
                                    if (System.currentTimeMillis() - lastProgress > 450) {
                                        progress(sent, file.bytes, start);
                                        lastProgress = System.currentTimeMillis();
                                    }
                                }
                            }
                            out.flush();
                            if (!"OK".equals(in.readUTF()))
                                throw new IllegalStateException("Destinatarul nu a confirmat " + file.name);
                            overall += file.bytes;
                        }
                        note("Transfer reușit: " + files.size() + " fișiere, " +
                            String.format(Locale.US, "%.1f MB", overall / 1048576d));
                        return;
                    }
                } catch (Exception ex) { last = ex; }
            }
            throw new IllegalStateException("Nu găsesc dispozitivul. " +
                (last == null ? "" : last.getMessage()));
        } catch (Exception ex) {
            note("Transfer eșuat: " + ex.getMessage());
        }
    }

    private void stopReceiver() {
        receiving.set(false);
        if (server != null) {
            try { server.close(); } catch (Exception ignored) { }
            server = null;
        }
        if (reservation != null) {
            try { reservation.close(); } catch (Exception ignored) { }
            reservation = null;
        }
        if (qrPanel != null) qrPanel.setVisibility(View.GONE);
    }

    @Override protected void onDestroy() {
        stopReceiver();
        if (networkCallback != null) {
            try { connectivity.unregisterNetworkCallback(networkCallback); }
            catch (Exception ignored) { }
        }
        worker.shutdownNow();
        super.onDestroy();
    }
}
