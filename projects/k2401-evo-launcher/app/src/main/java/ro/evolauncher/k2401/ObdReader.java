package ro.evolauncher.k2401;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.os.Process;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

/**
 * Read-only ELM327 / OBD-II telemetry for an already paired Bluetooth SPP dongle.
 * No ECU writes, adaptation, clearing DTCs, CAN raw commands or permanent service.
 * Runs only while the launcher is in the foreground.
 */
final class ObdReader {
    private static final UUID SERIAL_PORT = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");
    private static final String[] ADAPTER_NAMES = {"OBD", "ELM", "V-LINK", "VEEPEAK", "KONNWEI"};
    private final Runnable onUpdate;
    private volatile boolean running;
    private volatile Reading current = Reading.empty();
    private volatile String state = "OBD NECONECTAT";
    private Thread worker;
    private volatile BluetoothSocket socket;

    static final class Reading {
        final float rpm, coolantC, mapBar, batteryV;
        final boolean live;
        Reading(float rpm, float coolantC, float mapBar, float batteryV, boolean live) {
            this.rpm = rpm;
            this.coolantC = coolantC;
            this.mapBar = mapBar;
            this.batteryV = batteryV;
            this.live = live;
        }
        static Reading empty() {
            return new Reading(Float.NaN, Float.NaN, Float.NaN, Float.NaN, false);
        }
    }

    ObdReader(Runnable onUpdate) { this.onUpdate = onUpdate; }
    Reading current() { return current; }
    String status() { return state; }

    synchronized void start() {
        if (running) return;
        running = true;
        worker = new Thread(this::poll, "evo-obd-reader");
        worker.setDaemon(true);
        worker.start();
    }

    synchronized void stop() {
        running = false;
        BluetoothSocket old = socket;
        socket = null;
        if (old != null) {
            try { old.close(); } catch (Exception ignored) {}
        }
        if (worker != null) worker.interrupt();
        worker = null;
        current = Reading.empty();
        state = "OBD NECONECTAT";
    }

    private void notifyUi() {
        if (onUpdate != null) onUpdate.run();
    }

    private BluetoothDevice findPairedAdapter(BluetoothAdapter adapter) {
        Set<BluetoothDevice> bonded = adapter.getBondedDevices();
        if (bonded == null) return null;
        for (BluetoothDevice device : bonded) {
            String name = device.getName();
            if (name == null) continue;
            String upper = name.toUpperCase(Locale.US);
            for (String key : ADAPTER_NAMES) if (upper.contains(key)) return device;
        }
        return null;
    }

    private void poll() {
        Process.setThreadPriority(Process.THREAD_PRIORITY_BACKGROUND);
        try {
            while (running) {
                BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
                if (adapter == null || !adapter.isEnabled()) {
                    state = "ACTIVAZĂ BLUETOOTH"; notifyUi();
                    return;
                }
                BluetoothDevice device = findPairedAdapter(adapter);
                if (device == null) {
                    state = "ÎMPERECHEAZĂ ELM327"; notifyUi();
                    return;
                }
                state = "OBD SE CONECTEAZĂ"; notifyUi();
                try {
                    adapter.cancelDiscovery();
                    BluetoothSocket candidate = device.createRfcommSocketToServiceRecord(SERIAL_PORT);
                    socket = candidate;
                    candidate.connect();
                    if (!running) break;
                    InputStream in = candidate.getInputStream();
                    OutputStream out = candidate.getOutputStream();
                    command(in, out, "ATZ", 8000);
                    command(in, out, "ATE0", 4000);
                    command(in, out, "ATL0", 4000);
                    command(in, out, "ATS0", 4000);
                    command(in, out, "ATH0", 4000);
                    command(in, out, "ATSP0", 8000);
                    while (running) {
                        float rpm = obdPid(in, out, "0C", 2);
                        float coolant = obdPid(in, out, "05", 1);
                        float map = obdPid(in, out, "0B", 1);
                        float volt = adapterVoltage(in, out);
                        boolean live = Float.isFinite(rpm) || Float.isFinite(coolant) || Float.isFinite(map);
                        current = new Reading(
                            Float.isFinite(rpm) ? rpm / 4f / 1000f : Float.NaN,
                            Float.isFinite(coolant) ? coolant - 40f : Float.NaN,
                            Float.isFinite(map) ? map / 100f : Float.NaN,
                            volt, live);
                        state = live ? "OBD LIVE" : "ELM327 • FĂRĂ DATE ECU";
                        notifyUi();
                        Thread.sleep(850);
                    }
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    break;
                } catch (SecurityException denied) {
                    state = "ACORDĂ ACCES BLUETOOTH"; notifyUi();
                    break;
                } catch (Exception failed) {
                    if (running) {
                        current = Reading.empty();
                        state = "OBD DECONECTAT"; notifyUi();
                        Thread.sleep(4500);
                    }
                } finally {
                    BluetoothSocket old = socket;
                    socket = null;
                    if (old != null) try { old.close(); } catch (Exception ignored) {}
                }
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        } catch (SecurityException denied) {
            state = "ACORDĂ ACCES BLUETOOTH";
            notifyUi();
        } finally {
            current = Reading.empty();
            notifyUi();
        }
    }

    private static String command(InputStream in, OutputStream out, String cmd, long timeoutMs)
        throws Exception {
        while (in.available() > 0) in.read();
        out.write((cmd + "\r").getBytes(StandardCharsets.US_ASCII));
        out.flush();
        long deadline = android.os.SystemClock.elapsedRealtime() + timeoutMs;
        StringBuilder response = new StringBuilder();
        while (android.os.SystemClock.elapsedRealtime() < deadline) {
            if (Thread.currentThread().isInterrupted()) throw new InterruptedException();
            int ready = in.available();
            if (ready <= 0) {
                Thread.sleep(20);
                continue;
            }
            for (int i = 0; i < ready; i++) {
                int c = in.read();
                if (c < 0) throw new java.io.EOFException();
                if (c == '>') return response.toString();
                if (response.length() < 4096) response.append((char)c);
            }
        }
        throw new java.io.IOException("ELM327 response timeout: " + cmd);
    }

    // Request only OBD Mode 01 PIDs, without clearing DTCs or modifying the ECU.
    // For a 2-byte response, return the raw combined 16-bit value.
    private static float obdPid(InputStream in, OutputStream out, String pid, int bytes)
        throws Exception {
        String response = command(in, out, "01" + pid, 6000);
        String raw = response.toUpperCase(Locale.US).replaceAll("[^0-9A-F]", "");
        int start = raw.indexOf("41" + pid);
        int hexStart = start + 4;
        if (start < 0 || raw.length() < hexStart + bytes * 2) return Float.NaN;
        try {
            return Integer.parseInt(raw.substring(hexStart, hexStart + bytes * 2), 16);
        } catch (NumberFormatException invalid) {
            return Float.NaN;
        }
    }

    // ELM327 ATRV reports the adapter's observed supply voltage, not PID 0142.
    private static float adapterVoltage(InputStream in, OutputStream out) throws Exception {
        String text = command(in, out, "ATRV", 3500).toUpperCase(Locale.US);
        java.util.regex.Matcher m = java.util.regex.Pattern
            .compile("([0-9]{1,2}(?:\\.[0-9]{1,2})?)\\s*V")
            .matcher(text);
        if (!m.find()) return Float.NaN;
        float v = Float.parseFloat(m.group(1));
        return v >= 6f && v <= 28f ? v : Float.NaN;
    }
}
