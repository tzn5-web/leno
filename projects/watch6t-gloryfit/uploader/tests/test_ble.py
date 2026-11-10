"""Offline Watch6T uploader tests. Does not require a Bluetooth adapter or a watch."""
from __future__ import annotations
import asyncio
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol import DialCaps, DialFile, ProtocolError, section, status, choose_chunk_size
from watch6t_ble import WatchLink


def native_fixture(path: Path):
    # 2 native 48x48 RGB565 resources (9.2kB), 24-byte table, 2-byte sentinel.
    table_end = 24 + 2 * 24 + 2
    pixel_bytes = b"\x7c\x00" * (48 * 48)
    records = (
        struct.pack("<HHIHHHHBBH4s", 10, 48, table_end, 48, 0, 0, 0, 1, 0, 0, b"\0"*4)
        + struct.pack("<HHIHHHHBBH4s", 17, 48, table_end + len(pixel_bytes), 48, 75, 75, 0, 1, 0, 0, b"\0"*4)
        + b"\0\0"
    )
    data = records + pixel_bytes * 2
    header = struct.pack("<IIIHHII", 189801, len(data), zlib.crc32(data) & 0xFFFFFFFF, 240, 240, 0, 0)
    path.write_bytes(header + data)
    return DialFile.validate(path)


class DialTests(unittest.TestCase):
    def test_capabilities_real_watch6t_15_byte_reply(self):
        # Captured from user's iHunt Watch6T-D123 on 2026-11-10.
        reply = bytes.fromhex("26010002e56900f000f00000100000")
        self.assertEqual(len(reply), 15)
        caps = DialCaps.parse(reply)
        self.assertEqual(caps.dial_number, 189801)
        self.assertEqual((caps.width, caps.height), (240, 240))
        self.assertEqual(caps.max_data_size, 1048576)
        self.assertEqual(caps.screen_type, 0)
        self.assertIsNone(caps.compatibility_level)
        self.assertIsNone(caps.corner_angle)

    def test_extended_capabilities_18_byte_reply(self):
        caps = DialCaps.parse(bytes.fromhex("26010002e56900f000f0000010000001002a"))
        self.assertEqual(caps.compatibility_level, 1)
        self.assertEqual(caps.corner_angle, 42)

    def test_partial_extension_16_byte_reply(self):
        caps = DialCaps.parse(bytes.fromhex("26010002e56900f000f0000010000001"))
        self.assertEqual(caps.compatibility_level, 1)
        self.assertIsNone(caps.corner_angle)

    def test_bad_capabilities(self):
        with self.assertRaises(ProtocolError):
            DialCaps.parse(bytes.fromhex("26010002e56900f000f000001000"))
        with self.assertRaises(ProtocolError):
            DialCaps.parse(bytes.fromhex("2601"))
        with self.assertRaises(ProtocolError):
            DialCaps.parse(bytes.fromhex("260100000001000000000100000000010000"))

    def test_chunk_and_status(self):
        self.assertEqual(section(258, b"AB"), b"\x27\x01\x02AB")
        self.assertEqual(choose_chunk_size(20, 23), 16)
        self.assertEqual(choose_chunk_size(20, 247), 16)  # actual Windows Watch6T write cap
        self.assertEqual(choose_chunk_size(244, 247), 128)
        self.assertEqual(status(b"\x26\x03\x00"), "success")
        self.assertEqual(status(b"\x26\x03\x01"), "failure")
        with self.assertRaises(ProtocolError):
            section(65536, b"hello")

    def test_synthetic_and_corrupt_bin(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fixture.bin"
            f = native_fixture(p)
            self.assertEqual(f.items, 2)
            corrupted = bytearray(p.read_bytes())
            corrupted[-1] ^= 0x40
            p.write_bytes(corrupted)
            with self.assertRaises(ProtocolError):
                DialFile.validate(p)

    def test_real_holo_bin_if_available(self):
        p = Path(__file__).resolve().parents[1] / "D1898001_HOLO_V6_BETA_UNTESTED.bin"
        if not p.exists():
            self.skipTest("Private V6 BIN not committed to GitHub")
        f = DialFile.validate(p)
        self.assertEqual((f.items, f.file_id, f.size), (22, 189801, 421238))


class FakeClient:
    def __init__(self, target_bytes: int, *, reject: bool = False, no_ack: bool = False):
        self.is_connected = True
        self.mtu_size = 247
        self.target_bytes = target_bytes
        self.reject = reject
        self.no_ack = no_ack
        self.total = 0
        self.packet_count = 0
        self.notify = lambda *args: None

    async def write_gatt_char(self, characteristic, payload, response):
        if payload == b"\x26\x01":
            self.notify(None, bytes.fromhex("26010002e56900f000f00000100000"))
        elif payload == b"\x26\x02":
            if not self.no_ack:
                self.notify(None, b"\x26\x03\x04")
        elif payload[:1] == b"\x27":
            self.packet_count += 1
            self.total += len(payload) - 3
            if self.reject and self.total >= 4096:
                self.notify(None, b"\x26\x03\x01")
                return
            if self.total % 4096 == 0 and self.total < self.target_bytes:
                self.notify(None, b"\x26\x03\x04")
            if self.total >= self.target_bytes:
                self.notify(None, b"\x26\x03\x00")


class UploaderTests(unittest.IsolatedAsyncioTestCase):
    async def transfer(self, *, reject=False, no_ack=False):
        with tempfile.TemporaryDirectory() as d:
            face = native_fixture(Path(d) / "synthetic.bin")
            device = FakeClient(face.size, reject=reject, no_ack=no_ack)
            link = WatchLink(device)
            device.notify = link.on_notify
            link.mtu = 247
            link.max_write = 20  # actual watch reports this despite MTU=247
            caps = await link.capabilities()
            if reject:
                with self.assertRaises(ProtocolError):
                    await link.install(face, caps)
            elif no_ack:
                # Test no-ack behavior without waiting 25s: inject timeout at queue layer.
                async def always_timeout(predicate, timeout=15):
                    if timeout == 25:
                        raise ProtocolError("simulated timeout")
                    return await original_response(predicate, timeout)
                original_response = link.response
                link.response = always_timeout
                with self.assertRaises(ProtocolError):
                    await link.install(face, caps)
                self.assertEqual(device.packet_count, 0)
            else:
                await link.install(face, caps)
                self.assertEqual(device.total, face.size)
                self.assertGreater(device.packet_count, 1)

    async def test_acknowledged_upload(self):
        await self.transfer()

    async def test_rejected_upload(self):
        await self.transfer(reject=True)

    async def test_no_erase_ready_ack(self):
        await self.transfer(no_ack=True)

    async def test_mismatched_face_id_never_sends_erase(self):
        with tempfile.TemporaryDirectory() as d:
            face = native_fixture(Path(d) / 'synthetic.bin')
            device = FakeClient(face.size)
            link = WatchLink(device)
            device.notify = link.on_notify
            link.mtu = 247
            link.max_write = 20
            caps = await link.capabilities()
            from dataclasses import replace
            caps = replace(caps, dial_number=face.file_id + 1)
            with self.assertRaises(ProtocolError):
                await link.install(face, caps)
            self.assertEqual(device.packet_count, 0)

    async def test_single_gatt_packet_must_not_exceed_reported_20_bytes(self):
        device = FakeClient(10000)
        link = WatchLink(device)
        link.mtu = 247
        link.max_write = 20
        with self.assertRaises(ProtocolError):
            await link.command(section(0, b'A' * 18))
        self.assertEqual(device.packet_count, 0)


if __name__ == "__main__":
    unittest.main()
