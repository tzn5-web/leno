#!/usr/bin/env python3
"""VeloLink Offline receiver for Windows/Linux/macOS.
Generate RECEIVER QR on computer; Android SENDER scans QR and sends files over LAN.
No internet, cloud, login, ads, or relay used in any transfer.
Setup once: python -m pip install qrcode[pil]
Run: python velolink_pc.py receive --output ~/Downloads/VeloLink
Use --host 192.168.x.x if auto-selected local interface is wrong.
"""
import argparse
import base64
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import time


def read_exact(s, size):
    pieces = []
    while size:
        chunk = s.recv(min(size, 1024 * 1024))
        if not chunk:
            raise EOFError("Connection closed during transfer")
        pieces.append(chunk)
        size -= len(chunk)
    return b"".join(pieces)


def utf_read(s):
    length = struct.unpack("!H", read_exact(s, 2))[0]
    return read_exact(s, length).decode("utf-8", errors="replace")


def utf_send(s, value):
    raw = value.encode("utf-8")
    if len(raw) >= 65536:
        raise ValueError("Message too long")
    s.sendall(struct.pack("!H", len(raw)) + raw)


def local_ip():
    # UDP connect does not send a packet; works without external internet.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 80))
            ip = s.getsockname()[0]
            if ip and ip != "0.0.0.0":
                return ip
        except OSError:
            pass
    return "127.0.0.1"


def display_qr(text, output):
    try:
        import qrcode
    except ImportError as exc:
        raise SystemExit("Install once: python -m pip install qrcode[pil]") from exc
    image = qrcode.make(text)
    image.save(output)
    print("QR IMAGE:", output)
    # Terminal-friendly code; scanning on phone is usually easier from the PNG.
    qr = qrcode.QRCode(border=1, box_size=1)
    qr.add_data(text)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


def safe_name(value):
    name = str(value).replace("\\", "_").replace("/", "_").replace("\x00", "_")
    return (name.strip(" .") or "received.bin")[-175:]


def unique_path(folder, name):
    stem, ext = os.path.splitext(name)
    p = folder / name
    n = 1
    while p.exists() or p.with_name(p.name + ".part").exists():
        p = folder / f"{stem} ({n}){ext}"
        n += 1
    return p


def accept_one(sock, addr, token, folder):
    sock.settimeout(40)
    with sock:
        if utf_read(sock) != "VL1" or not hmac.compare_digest(utf_read(sock), token):
            utf_send(sock, "DENIED")
            return
        utf_send(sock, "READY")
        count = struct.unpack("!I", read_exact(sock, 4))[0]
        if not (1 <= count <= 2000):
            raise ValueError("Invalid file count")
        for i in range(count):
            name = safe_name(utf_read(sock))
            length = struct.unpack("!q", read_exact(sock, 8))[0]
            if not (0 <= length <= 1_000_000_000_000):
                raise ValueError("Invalid size")
            path = unique_path(folder, name)
            temporary = path.with_name(path.name + ".part")
            start = time.monotonic()
            left = length
            try:
                with temporary.open("xb") as f:
                    while left:
                        block = read_exact(sock, min(left, 1024 * 1024))
                        f.write(block)
                        left -= len(block)
                temporary.replace(path)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
            mbps = (length * 8 / max(.001, time.monotonic() - start)) / 1_000_000
            print(f"[{i + 1}/{count}] {path.name}: {length:,} bytes, {mbps:.1f} Mbps")
            utf_send(sock, "OK")


def receiver(args):
    ip = args.host or local_ip()
    if ip.startswith("127."):
        raise SystemExit("No LAN address found. Use --host YOUR_COMPUTER_LAN_IPV4")
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    data = {"v": 1, "mode": "lan", "host": ip, "token": token, "port": args.port}
    payload = "VL1:" + base64.urlsafe_b64encode(
        json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
    png = output / "VeloLink_receiver_QR.png"
    display_qr(payload, png)
    print(f"Receiving at {ip}:{args.port}; saving files in {output}")
    print("Your phone must be connected to the same local Wi-Fi or your computer's hotspot.")
    print("No Internet connection is needed. Keep the receiver terminal running.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", args.port))
        listener.listen(6)
        while True:
            sock, addr = listener.accept()
            print("Connection from", addr[0])
            try:
                accept_one(sock, addr, token, output)
            except (ValueError, OSError, EOFError) as error:
                print("Transfer error:", error)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("receive", help="Generate recipient QR and accept phone transfers")
    s.add_argument("--host", help="Your LAN IPv4 (required if automatic detection fails)")
    s.add_argument("--port", type=int, default=47882)
    s.add_argument("--output", default=str(Path.home() / "Downloads" / "VeloLink"))
    args = p.parse_args()
    if args.cmd == "receive":
        receiver(args)


if __name__ == "__main__":
    main()
