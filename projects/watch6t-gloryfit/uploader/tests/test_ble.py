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
from protocol import (
    DialCaps, DialFile, ProtocolError, section, status, choose_chunk_size,
    is_prepare_ack, is_final_ack,
)
from watch6t_ble import WatchLink, BLE5_COMMAND, COMMAND


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

    def test_new_watch6t_unassigned_dial_id_reply(self):
        # Real, read-only reply after failed 26 02 attempt (2026-11-10).
        caps = DialCaps.parse(bytes.fromhex("2601ffffffff00f000f00000100000"))
        self.assertEqual(caps.dial_number, 0xFFFFFFFF)
        self.assertEqual(caps.max_data_size, 1048576)
        self.assertEqual(caps.slot_state, "no-online-dial-displayed")

    def test_vendor_ready_and_finish_are_distinct(self):
        self.assertTrue(is_prepare_ack(b"\x26\x02"))
        self.assertTrue(is_prepare_ack(b"\x26\x02\x00"))
        self.assertFalse(is_prepare_ack(b"\x26\x03\x04"))
        self.assertTrue(is_final_ack(b"\x26\x03\x00"))
        self.assertFalse(is_final_ack(b"\x26\x03\x04"))

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
        self.assertEqual(choose_chunk_size(20, 23), 17)
        self.assertEqual(choose_chunk_size(20, 247), 17)
        self.assertEqual(choose_chunk_size(244, 247), 241)  # actual 34F1 hardware
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
        self.prepare_count = 0
        self.next_block_ack = 4096
        self.write_modes = []
        self.frame_sizes = []
        self.writes = []
        self.notify = lambda *args: None

    async def write_gatt_char(self, characteristic, payload, response):
        self.write_modes.append(response)
        self.frame_sizes.append(len(payload))
        self.writes.append((characteristic, bytes(payload), response))
        if payload == b"\x26\x01":
            self.notify(None, bytes.fromhex("26010002e56900f000f00000100000"))
        elif payload == b"\x26\x02":
            self.prepare_count += 1
            if not self.no_ack:
                # Official SDK's prepare handler accepts an incoming 26 02.
                self.notify(None, b"\x26\x02")
        elif payload == b"\x26\x03\x00":
            # Final ACK follows explicit phone-side finish command.
            self.notify(None, b"\x26\x03\x00")
        elif payload[:1] == b"\x27":
            self.packet_count += 1
            self.total += len(payload) - 3
            if self.reject and self.total >= 4096:
                self.notify(None, b"\x26\x03\x01")
                return
            if self.total >= self.next_block_ack:
                self.notify(None, b"\x26\x03\x04")
                self.next_block_ack += 4096
            # Final success is only emitted AFTER the phone sends 26 03 00.


class UploaderTests(unittest.IsolatedAsyncioTestCase):
    async def transfer(self, *, reject=False, no_ack=False, displayed_id=None):
        with tempfile.TemporaryDirectory() as d:
            face = native_fixture(Path(d) / "synthetic.bin")
            device = FakeClient(face.size, reject=reject, no_ack=no_ack)
            link = WatchLink(device)
            device.notify = link.on_notify
            link.mtu = 247
            link.write_response = True
            link.max_write = 20
            link.ble5_command = BLE5_COMMAND
            link.ble5_response = False
            link.ble5_max_write = 244
            caps = await link.capabilities()
            if displayed_id is not None:
                from dataclasses import replace
                caps = replace(caps, dial_number=displayed_id)
            if no_ack:
                original_response = link.response
                async def immediate_timeout(predicate, timeout=15, stage="response"):
                    if "prepare ACK" in stage:
                        raise ProtocolError("simulated 26 02 ACK timeout")
                    return await original_response(predicate, timeout=timeout, stage=stage)
                link.response = immediate_timeout
                with self.assertRaisesRegex(ProtocolError, "simulated 26 02 ACK timeout"):
                    await link.install(face, caps)
                self.assertEqual(device.prepare_count, 1)
                self.assertEqual(device.packet_count, 0)
            elif reject:
                with self.assertRaisesRegex(ProtocolError, "Watch reports error"):
                    await link.install(face, caps)
                self.assertEqual(device.prepare_count, 1)
                self.assertGreater(device.packet_count, 0)
            else:
                await link.install(face, caps)
                self.assertEqual(device.total, face.size)
                self.assertEqual(device.prepare_count, 1)
                self.assertTrue(any(p == b"\x26\x03\x00" for _,p,_ in device.writes))
                self.assertTrue(all(ch==BLE5_COMMAND for ch,p,_ in device.writes if p[:1]==b"\x27"))
                self.assertLessEqual(max(device.frame_sizes), 244)
                self.assertEqual([w[2] for w in device.writes if w[0]==COMMAND], [True,True,True])

    async def test_actual_vendor_ready_allows_transfer(self):
        await self.transfer()

    async def test_no_ready_ack_fails_without_data(self):
        await self.transfer(no_ack=True)

    async def test_watch_rejection_aborts_transfer(self):
        await self.transfer(reject=True)

    async def test_display_id_mismatch_is_not_target_id_error(self):
        # The 26 01 dialNumber is currently DISPLAYED face, not target file ID.
        await self.transfer(displayed_id=123456)

    async def test_no_online_face_ffffffff_still_uploads_when_ready(self):
        await self.transfer(displayed_id=0xFFFFFFFF)

    async def test_wrong_bin_identifier_refused_before_erase(self):
        with tempfile.TemporaryDirectory() as d:
            face = native_fixture(Path(d) / "fixture.bin")
            from dataclasses import replace
            face = replace(face, file_id=17)
            device = FakeClient(face.size)
            link = WatchLink(device)
            device.notify = link.on_notify
            link.ble5_command = BLE5_COMMAND
            link.ble5_response = False
            link.ble5_max_write = 244
            link.mtu = 247
            link.max_write = 20
            caps = await link.capabilities()
            with self.assertRaisesRegex(ProtocolError, "Unexpected native dial identifier"):
                await link.install(face, caps)
            self.assertEqual(device.prepare_count, 0)
            self.assertEqual(device.packet_count, 0)

    async def test_gatt_with_response_control_and_34f1_without_response(self):
        await self.transfer()

    async def test_offline_transfer_after_vendor_ready_writes_finish(self):
        # Simulates real 34F1 streaming, 4KiB flow control, explicit
        # 33F1 26 03 00 finish, without an actual destructive 26 02.
        with tempfile.TemporaryDirectory() as d:
            face = native_fixture(Path(d) / "test.bin")
            device = FakeClient(face.size)
            link = WatchLink(device)
            device.notify = link.on_notify
            link.ble5_command = BLE5_COMMAND
            link.ble5_response = False
            link.ble5_max_write = 244
            link.max_write = 20
            link.mtu = 247
            await link.transfer_after_vendor_ready(face, b"\x26\x02")
            self.assertEqual(device.total, face.size)
            self.assertGreater(device.packet_count, 30)
            self.assertTrue(
                all(ch == BLE5_COMMAND for ch, p, _ in device.writes if p[:1] == b"\x27")
            )
            self.assertEqual(device.writes[-1], (COMMAND, b"\x26\x03\x00", False))
            self.assertEqual(device.prepare_count, 0)

    async def test_offline_transfer_requires_real_prepare_ack(self):
        with tempfile.TemporaryDirectory() as d:
            face = native_fixture(Path(d) / "test.bin")
            device = FakeClient(face.size)
            link = WatchLink(device)
            device.notify = link.on_notify
            link.ble5_command = BLE5_COMMAND
            link.ble5_response = False
            link.ble5_max_write = 244
            link.mtu = 247
            with self.assertRaisesRegex(ProtocolError, "No 26 02"):
                await link.transfer_after_vendor_ready(face, b"\x26\x03\x04")
            self.assertEqual(device.writes, [])

    async def test_vendor_apk_requires_34f1_for_27_data(self):
        device = FakeClient(16)
        link = WatchLink(device)
        link.ble5_command = BLE5_COMMAND
        link.ble5_response = False
        link.ble5_max_write = 20
        await link.send_section(0, b"A" * 16)
        self.assertEqual(device.writes[-1][0], BLE5_COMMAND)
        self.assertEqual(device.writes[-1][1], b"\x27\x00\x00" + b"A" * 16)
        self.assertEqual(device.packet_count, 1)
        self.assertFalse(device.writes[-1][2])

    async def test_34f1_data_missing_refuses_any_section_write(self):
        device = FakeClient(1000)
        link = WatchLink(device)
        with self.assertRaisesRegex(ProtocolError, "34F1"):
            await link.send_section(0, b"A" * 16)
        self.assertEqual(device.writes, [])

    async def test_34f1_data_oversize_rejected_before_write(self):
        device = FakeClient(1000)
        link = WatchLink(device)
        link.ble5_command = BLE5_COMMAND
        link.ble5_response = False
        link.ble5_max_write = 20
        with self.assertRaisesRegex(ProtocolError, "exceeds safe limit"):
            await link.send_section(0, b"A" * 18)
        self.assertEqual(device.writes, [])

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
