"""Offline tests: native watchface validation, BLE status and ACK-driven upload.

Never connects to a real watch. Execute: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import asyncio
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import DialCaps, DialFile, ProtocolError, section, status, choose_chunk_size
from watch6t_ble import WatchLink


class DialTests(unittest.TestCase):
    def test_capabilities(self):
        raw = bytes.fromhex("26010000000100f000f00100100000010000")
        c = DialCaps.parse(raw)
        self.assertEqual((c.width, c.height), (240, 240))
        self.assertEqual(c.max_data_size, 0x100000)

    def test_wrong_capabilities_rejected(self):
        with self.assertRaises(ProtocolError):
            DialCaps.parse(bytes.fromhex("260100"))
        with self.assertRaises(ProtocolError):
            DialCaps.parse(bytes.fromhex("260100000001000000000100000000010000"))

    def test_sections(self):
        self.assertEqual(section(258, b"AB"), b"\x27\x01\x02AB")
        self.assertEqual(choose_chunk_size(20, 23), 16)
        self.assertEqual(choose_chunk_size(244, 247), 128)
        self.assertEqual(status(b"\x26\x03\x00"), "success")
        self.assertEqual(status(b"\x26\x03\x03\x00\x13"), "resume")
        with self.assertRaises(ProtocolError):
            section(65536, b"a")

    def test_real_bin(self):
        path = Path(__file__).resolve().parents[1] / "D1898001_HOLO_V6_BETA_UNTESTED.bin"
        if not path.exists():
            self.skipTest("Private BIN not checked into public GitHub; present in private ZIP")
        info = DialFile.validate(path)
        self.assertEqual(info.items, 22)
        self.assertEqual(info.size, 421238)
        self.assertEqual(info.file_id, 189801)


class FakeClient:
    """Models an RK normal-command BLE peripheral, strictly for simulator tests."""
    def __init__(self, *, reject=False):
        self.is_connected = True
        self.mtu_size = 247
        self.packet_count = 0
        self.total = 0
        self.target_bytes = 0
        self.notify_cb = None
        self.reject = reject

    async def write_gatt_char(self, uuid, payload, response):
        assert uuid.lower().endswith("0000-1000-8000-00805f9b34fb")
        if payload == b"\x26\x01":
            self.notify_cb(None, bytes.fromhex("26010000000100f000f00100100000010000"))
        elif payload == b"\x26\x02":
            self.notify_cb(None, b"\x26\x03\x04")
        elif payload[0] == 0x27:
            self.packet_count += 1
            self.total += len(payload) - 3
            if self.reject and self.total >= 4096:
                self.notify_cb(None, b"\x26\x03\x01")
                return
            if self.total % 4096 == 0 and self.total < self.target_bytes:
                self.notify_cb(None, b"\x26\x03\x04")
            if self.total >= self.target_bytes:
                self.notify_cb(None, b"\x26\x03\x00")

class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_transfer_waits_for_real_acks(self):
        p = Path(__file__).resolve().parents[1] / "D1898001_HOLO_V6_BETA_UNTESTED.bin"
        if not p.exists():
            self.skipTest("Private BIN only, not included in public source")
        face = DialFile.validate(p)
        client = FakeClient()
        client.target_bytes = face.size
        link = WatchLink(client)
        client.notify_cb = link.on_notify
        link.write_response = False
        link.mtu = 247
        link.max_write = 244
        caps = await link.capabilities()
        await link.install(face, caps)
        self.assertEqual(client.total, face.size)
        self.assertGreater(client.packet_count, 3000)

    async def test_abort_on_watch_error(self):
        p = Path(__file__).resolve().parents[1] / "D1898001_HOLO_V6_BETA_UNTESTED.bin"
        if not p.exists():
            self.skipTest("Private BIN only, not included in public source")
        face = DialFile.validate(p)
        client = FakeClient(reject=True)
        client.target_bytes = face.size
        link = WatchLink(client)
        client.notify_cb = link.on_notify
        link.write_response = False
        link.mtu = 247
        link.max_write = 244
        caps = await link.capabilities()
        with self.assertRaises(ProtocolError):
            await link.install(face, caps)


if __name__ == "__main__":
    unittest.main()
