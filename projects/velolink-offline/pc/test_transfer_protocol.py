#!/usr/bin/env python3
"""Offline receiver protocol integration tests (no Internet needed)."""
import importlib.util
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location("velolink_pc", Path(__file__).with_name("velolink_pc.py"))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class OfflineProtocolTests(unittest.TestCase):
    def transmit(self, secret, received, payload=b"binary payload", name="test.bin"):
        a, b = socket.socketpair()
        report = []
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            def receiver():
                try:
                    v.accept_one(b, ("127.0.0.1", 12345), secret, folder)
                except Exception as ex:
                    report.append(ex)
            th = threading.Thread(target=receiver)
            th.start()
            try:
                v.utf_send(a, "VL1")
                v.utf_send(a, received)
                state = v.utf_read(a)
                if state == "READY":
                    a.sendall(struct.pack("!I", 1))
                    v.utf_send(a, name)
                    a.sendall(struct.pack("!q", len(payload)))
                    a.sendall(payload)
                    self.assertEqual(v.utf_read(a), "OK")
                actual = (folder / v.safe_name(name)).read_bytes() if state == "READY" else None
            finally:
                a.close()
                th.join(5)
            self.assertFalse(th.is_alive())
            self.assertEqual(report, [])
            return state, actual

    def test_receiver_generates_token_authorized_transfer(self):
        data = bytes(range(256)) * 64
        state, received = self.transmit("one-time-QR-token-123456", "one-time-QR-token-123456", data)
        self.assertEqual(state, "READY")
        self.assertEqual(received, data)

    def test_receiver_denies_invalid_qr_token(self):
        state, received = self.transmit("one-time-QR-token-123456", "wrong-token")
        self.assertEqual(state, "DENIED")
        self.assertIsNone(received)

    def test_path_is_not_traversed(self):
        state, received = self.transmit("one-time-QR-token-123456", "one-time-QR-token-123456", b"data", "../../safety.txt")
        self.assertEqual((state, received), ("READY", b"data"))

if __name__ == "__main__":
    unittest.main()
