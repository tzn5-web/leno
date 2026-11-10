#!/usr/bin/env python3
"""Experimental Watch6T Bluetooth watch-face uploader (GloryFit RK 26/27).

Read the README before --install. By default this tool only scans/probes.
Never uses firmware OTA/DFU characteristics. Physical Watch6T support unverified.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from protocol import DialCaps, DialFile, ProtocolError, choose_chunk_size, section, status

SERVICE = "000055ff-0000-1000-8000-00805f9b34fb"
COMMAND = "000033f1-0000-1000-8000-00805f9b34fb"
BLE5_COMMAND = "000034f1-0000-1000-8000-00805f9b34fb"
NOTIFY = "000033f2-0000-1000-8000-00805f9b34fb"
DATA_NOTIFY = "000034f2-0000-1000-8000-00805f9b34fb"
OTA_SHORT_UUIDS = ("fef5", "d0ff", "6287", "ffd3")
WATCH_PREFIX = "ihunt watch6t"


def ble_import():
    try:
        from bleak import BleakClient, BleakScanner
        return BleakClient, BleakScanner
    except ImportError as exc:
        raise ProtocolError("Missing BLE library. Run: py -m pip install -r requirements.txt") from exc


def describe_device(device) -> str:
    return f"{device.name or '[no advertised name]'} : {device.address}"


async def pick_device(name: str, address: str | None, timeout: float, all_devices: bool):
    _, BleakScanner = ble_import()
    seen = await BleakScanner.discover(timeout=timeout)
    if all_devices:
        for d in sorted(seen, key=lambda x: (x.name or "", x.address)):
            print(describe_device(d))
    if address:
        matching = [d for d in seen if d.address.lower() == address.lower()]
    else:
        matching = [d for d in seen if name.lower() in (d.name or "").lower()]
    if not matching:
        if all_devices:
            raise ProtocolError("Watch not found. Check Bluetooth and disconnect GloryFit.")
        raise ProtocolError("Watch not found. Run scan --all to see advertised BLE devices.")
    if len(matching) > 1:
        raise ProtocolError("More than one matching device. Use --address to select exactly one.")
    return matching[0]


class WatchLink:
    def __init__(self, client):
        self.client = client
        self.notifications: asyncio.Queue[bytes] = asyncio.Queue()
        self.write_response = False
        self.max_write = 20
        self.mtu = 23
        self.ble5_command = None
        self.ble5_notify = None
        self.ble5_response = None
        self.ble5_max_write = None
        self.last_dial_notification = None

    def on_notify(self, characteristic, payload: bytearray):
        packet = bytes(payload)
        if packet and packet[0] in (0x26, 0x27):
            self.last_dial_notification = packet.hex()
            print(f"BLE DIAL NOTIFY: {packet.hex()}", flush=True)
            if packet[0] == 0x26:
                self.notifications.put_nowait(packet)
        elif packet:
            # Do not dump other potentially private notifications such as health measurements.
            print(f"BLE OTHER NOTIFY: {len(packet)} bytes, prefix=0x{packet[0]:02x}", flush=True)

    async def setup(self):
        # BLE GATT service discovery does not send watchface payload data.
        services = self.client.services
        service = services.get_service(SERVICE)
        if service is None:
            raise ProtocolError("Normal GloryFit 55FF service missing; this device is not a supported RK profile")
        command = services.get_characteristic(COMMAND)
        notify = services.get_characteristic(NOTIFY)
        if command is None or notify is None:
            raise ProtocolError("Missing 33F1/33F2 command/response characteristics; no writes performed")
        props = {x.lower() for x in command.properties}
        if "write-without-response" not in props and "write" not in props:
            raise ProtocolError("33F1 does not permit protocol commands")
        if "notify" not in {x.lower() for x in notify.properties}:
            raise ProtocolError("33F2 cannot send acknowledgements; unsafe to upload")
        self.write_response = "write-without-response" not in props
        self.max_write = command.max_write_without_response_size if not self.write_response else 20
        self.mtu = max(23, self.client.mtu_size)
        # 34F1 is the BLE5 data channel used by some GloryFit implementations.
        # Discovery is read-only; NEVER assume it is safe to send 26 02 or 27 there.
        self.ble5_command = services.get_characteristic(BLE5_COMMAND)
        self.ble5_notify = services.get_characteristic(DATA_NOTIFY)
        if self.ble5_command is not None:
            transfer_props = {x.lower() for x in self.ble5_command.properties}
            if "write-without-response" in transfer_props:
                self.ble5_response = False
                self.ble5_max_write = max(20, int(getattr(
                    self.ble5_command, "max_write_without_response_size", 20
                )))
            elif "write" in transfer_props:
                self.ble5_response = True
                self.ble5_max_write = 20
            print(f"GloryFit BIN data 34F1: properties={list(self.ble5_command.properties)}; "
                  f"max_write={self.ble5_max_write}; "
                  f"mode={'with-response' if self.ble5_response else 'without-response'}")
        else:
            print("GloryFit BIN data 34F1: NOT PRESENT (upload cannot use vendor route)")
        await self.client.start_notify(NOTIFY, self.on_notify)
        if services.get_characteristic(DATA_NOTIFY):
            try:
                await self.client.start_notify(DATA_NOTIFY, self.on_notify)
            except Exception:
                pass
        print(f"Normal GloryFit service: OK; ATT MTU={self.mtu}; "
              f"max GATT write={self.max_write}; "
              f"mode={'with-response' if self.write_response else 'without-response'}")

    async def command(self, payload: bytes):
        if not self.client.is_connected:
            raise ProtocolError("Bluetooth disconnected")
        if payload.startswith(b"\x01\xe3"):
            raise ProtocolError("Actions/JX 01 E3 protocol not implemented; no guesswork")
        if payload[:2] not in (b"\x26\x01", b"\x26\x02"):
            raise ProtocolError(f"Command blocked: {payload.hex()}")
        # Watch6T reports MTU 247 but its Windows GATT write limit is 20 bytes.
        # Follow the actual characteristic limit; never rely on the MTU alone.
        if len(payload) > self.max_write:
            raise ProtocolError(
                f"GATT frame {len(payload)} bytes exceeds conservative write limit {self.max_write}"
            )
        # A write-with-response ACK only confirms GATT delivery, not storage of
        # the watch face; final acceptance still requires 26 03 00 from the watch.
        try:
            await asyncio.wait_for(
                self.client.write_gatt_char(COMMAND, payload, response=self.write_response),
                timeout=15.0,
            )
        except asyncio.TimeoutError as exc:
            raise ProtocolError(
                f"GATT WRITE timeout (15s), command={payload[:3].hex()}, mode="
                f"{'with-response' if self.write_response else 'without-response'}"
            ) from exc
        except Exception as exc:
            raise ProtocolError(
                f"GATT WRITE failed, command={payload[:3].hex()}, "
                f"error={type(exc).__name__}: {exc!s}"
            ) from exc

    async def send_section(self, index: int, data: bytes):
        """Transport a 27 section on 34F1 (vendor APK writeCharaBle5Gps).

        Not called while prepare/ACK compatibility remains unverified.
        """
        if self.ble5_command is None or self.ble5_response is None:
            raise ProtocolError("34F1 data characteristic is unavailable/has no supported write property")
        packet = section(index, data)
        if len(packet) > self.ble5_max_write:
            raise ProtocolError(f"34F1 packet {len(packet)} exceeds safe limit {self.ble5_max_write}")
        if not self.client.is_connected:
            raise ProtocolError("BLE disconnected during 34F1 transfer")
        try:
            await asyncio.wait_for(
                self.client.write_gatt_char(BLE5_COMMAND, packet, response=self.ble5_response),
                timeout=15,
            )
        except asyncio.TimeoutError as exc:
            raise ProtocolError(f"34F1 section {index}: GATT write timeout (15s)") from exc
        except Exception as exc:
            raise ProtocolError(
                f"34F1 section {index}: {type(exc).__name__}: {exc!s}"
            ) from exc

    async def response(self, predicate, timeout=15.0, stage="response") -> bytes:
        end = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = end - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise ProtocolError("No expected BLE reply before timeout; transfer stopped")
            try:
                packet = await asyncio.wait_for(self.notifications.get(), remaining)
            except asyncio.TimeoutError as exc:
                raise ProtocolError(
                    f"{stage}: no matching dial notification within {timeout:g}s; "
                    f"connected={self.client.is_connected}; "
                    f"last_dial_notify={self.last_dial_notification or 'none'}"
                ) from exc
            if packet.startswith(b"\x26\x03"):
                code = status(packet)
                if code in ("failure", "crc-failure", "unexpected"):
                    raise ProtocolError(f"Watch reports error {code}, data={packet.hex()}")
            if predicate(packet):
                return packet

    async def capabilities(self) -> DialCaps:
        # This is the documented read-only capability query, not 26 02 (slot erase).
        await self.command(b"\x26\x01")
        response = await self.response(lambda p: p.startswith(b"\x26\x01"), timeout=12, stage="26 01 capability query")
        return DialCaps.parse(response)

    async def install(self, face: DialFile, caps: DialCaps):
        if (caps.width, caps.height) != (240, 240):
            raise ProtocolError("Watch did not report 240x240 resolution; refusing")
        if face.size > caps.max_data_size:
            raise ProtocolError(f"HOLO size {face.size} bytes exceeds watch slot limit {caps.max_data_size}")
        if face.file_id != 189801:
            raise ProtocolError("Unexpected native dial identifier; refusing to overwrite a slot")
        if caps.dial_number != face.file_id:
            raise ProtocolError(
                f"Watch reported face ID {caps.dial_number}, but BIN is {face.file_id}; no slot write"
            )
        if caps.compatibility_level is not None and caps.compatibility_level > 2:
            print(f"Note: compatibility level {caps.compatibility_level} is not specifically validated")
        if caps.compatibility_level is None:
            print("Watch6T short capability reply: optional compatibility/corner fields unavailable")
        # iHunt Watch6T exposes 33F1 as WRITE (with response), not WRITE-WITHOUT-RESPONSE.
        # The read-only 26 01 query succeeded with this same write mode on the real watch.
        # GATT-confirmed writes are slower but valid; do not force response=False or
        # exceed 20 bytes merely because the ATT MTU reports 247.
        if self.write_response:
            print("Watch6T GATT write WITH response: sending acknowledged <=20-byte frames")
        else:
            print("GATT write WITHOUT response: waiting for watch's explicit dial ACKs")
        if self.ble5_max_write is None:
            raise ProtocolError("34F1 unavailable: cannot send native 27 sections")
        chunk_bytes = choose_chunk_size(self.ble5_max_write, self.mtu)
        packet_count = (face.size + chunk_bytes - 1) // chunk_bytes
        if packet_count > 65536:
            raise ProtocolError("Binary is too large for 16-bit section indices at negotiated MTU")
        print(f"Validated watch capacity {caps.max_data_size} bytes, face {face.size}, "
              f"payload per section {chunk_bytes}, sections {packet_count}")
        # Previous Watch6T attempt reached this stage and timed out. 26 02 may
        # erase a custom-face slot. Until the genuine 33F1/34F1 vendor transfer
        # path is confirmed, do not repeat this potentially destructive command.
        raise ProtocolError(
            "PREPARE UNSAFE: the last 26 02 attempt received no proven ready ACK. "
            "Read-only GATT profile is available; watchface transfer is disabled "
            "until the device-specific 33F1/34F1 handshake is confirmed."
        )
        data = face.path.read_bytes()
        offset, index, next_boundary = 0, 0, 4096
        while offset < len(data):
            block = data[offset:offset + chunk_bytes]
            await self.send_section(index, block)
            offset += len(block)
            index += 1
            # Avoid overflowing the host's BLE TX queue on Windows.
            if index % 12 == 0:
                await asyncio.sleep(0.006)
            if offset >= next_boundary and offset < len(data):
                ack = await self.response(
                    lambda p: p.startswith(b"\x26\x03\x04") or p.startswith(b"\x26\x03\x03"),
                    timeout=25,
                )
                if ack.startswith(b"\x26\x03\x03"):
                    if len(ack) < 5:
                        raise ProtocolError("Invalid resume request; refusing to guess offset")
                    resume = int.from_bytes(ack[3:5], "big")
                    if resume > index:
                        raise ProtocolError("Watch requested a section that was never sent")
                    index = resume
                    offset = min(resume * chunk_bytes, len(data))
                    next_boundary = ((offset // 4096) + 1) * 4096
                else:
                    next_boundary += 4096
                    print(f"Confirmed transfer progress: {offset}/{face.size} bytes")
        # The firmware sends 26 03 00 when finished; do NOT invent an OTA finish.
        # An extra 26 03 04 (block-ready) is not a final acceptance.
        # Only a 26 03 00 status confirms that the watch accepted the dial.
        confirmation = await self.response(lambda p: status(p) == "success", timeout=45)
        if status(confirmation) != "success":
            raise ProtocolError(f"Watch did not confirm a successful dial: {confirmation.hex()}")
        print("WATCH ACK: watchface upload accepted; inspect display to confirm visual correctness.")


async def main(args):
    BleakClient, _ = ble_import()
    face = DialFile.validate(args.file) if args.file else None
    if args.mode == "scan":
        await pick_device(args.name, args.address, args.scan_seconds, all_devices=True)
        return
    if args.mode == "install":
        if face is None:
            raise ProtocolError("--file is mandatory for installation")
        if args.confirm != "ERASE-DIAL-SLOT":
            raise ProtocolError("Use --confirm ERASE-DIAL-SLOT to explicitly authorize a custom-face slot write")
    device = await pick_device(args.name, args.address, args.scan_seconds, all_devices=args.all)
    print("Selected:", describe_device(device))
    async with BleakClient(device, timeout=18) as client:
        link = WatchLink(client)
        await link.setup()
        caps = await link.capabilities()
        print("Watchface capabilities:", json.dumps(asdict(caps), sort_keys=True))
        if args.mode == "probe":
            print("READ-ONLY GATE PASSED. No watchface bytes uploaded.")
            return
        await link.install(face, caps)


def parse_args():
    p = argparse.ArgumentParser(description="Watch6T native HOLO BLE uploader (RK protocol only)")
    p.add_argument("mode", choices=("scan", "probe", "install"))
    p.add_argument("--name", default="iHunt Watch6T", help="BLE advertised name substring")
    p.add_argument("--address", help="Explicit BLE address, if name-based discovery fails")
    p.add_argument("--all", action="store_true", help="Show all devices during discovery")
    p.add_argument("--scan-seconds", type=float, default=9)
    p.add_argument("--file", help="Validated native .bin watchface (not a ZIP or a PNG)")
    p.add_argument("--confirm", default="", help="For install only: ERASE-DIAL-SLOT")
    return p.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args()))
    except (ProtocolError, TimeoutError, asyncio.TimeoutError) as e:
        detail = str(e) or f"{type(e).__name__} (no message)"
        print("BLOCKED:", detail, file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("Cancelled")
        sys.exit(130)
