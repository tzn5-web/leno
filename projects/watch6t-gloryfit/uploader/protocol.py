"""GloryFit RK watch-face protocol primitives.

Derived from public protocol research and the user's original D1898001.bin.
These helpers do NOT talk to Bluetooth or alter a watch.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
import zlib
from pathlib import Path

HEADER = struct.Struct("<IIIHHII")
ITEM = struct.Struct("<HHIHHHHBBH4s")
MAX_ELEMENTS = 100
WATCH_SIZE = (240, 240)
UNASSIGNED_DIAL_ID = 0xFFFFFFFF  # Seen after interrupted 26 02 on iHunt Watch6T; interpretation unverified


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class DialCaps:
    dial_number: int
    width: int
    height: int
    screen_type: int
    max_data_size: int
    # On Watch6T the 26 01 response ends after the 4-byte capacity (15 bytes total).
    # Other GloryFit variants append compatibility and corner information.
    compatibility_level: int | None
    corner_angle: int | None

    @property
    def slot_state(self) -> str:
        """An informational hint; never infer a safe-to-write slot from it."""
        if self.dial_number == UNASSIGNED_DIAL_ID:
            return "unassigned-or-erased (not independently confirmed)"
        return "reported-dial-id"

    @classmethod
    def parse(cls, response: bytes) -> "DialCaps":
        # GloryFit classic / RK reply, from the OnlineDialUtil response layout.
        # response[0:2]=26 01; 2:6=dial number; 6:10=width/height.
        # Actual iHunt Watch6T packet recorded on 2026-11-10:
        # 26 01 | 00 02 e5 69 | 00 f0 | 00 f0 | 00 | 00 10 00 00
        # It has **15** bytes, not the 18 bytes used by some GloryFit models.
        # The optional compatibility byte is at offset 15, corner byte at 17.
        if len(response) < 15 or response[:2] != b"\x26\x01":
            raise ProtocolError(f"Not a complete dial capabilities reply: {response.hex()}")
        caps = cls(
            int.from_bytes(response[2:6], "big"),
            int.from_bytes(response[6:8], "big"),
            int.from_bytes(response[8:10], "big"),
            response[10],
            int.from_bytes(response[11:15], "big"),
            response[15] if len(response) >= 16 else None,
            response[17] if len(response) >= 18 else None,
        )
        if caps.dial_number == 0:
            raise ProtocolError("Empty reported face identifier")
        if not 50 <= caps.width <= 1000 or not 50 <= caps.height <= 1000:
            raise ProtocolError("Implausible reply resolution; wrong GloryFit protocol?")
        if not 4096 <= caps.max_data_size <= 16 * 1024 * 1024:
            raise ProtocolError("Implausible face storage capacity; abort")
        return caps


@dataclass(frozen=True)
class DialFile:
    path: Path
    file_id: int
    size: int
    width: int
    height: int
    items: int
    sha256: str
    crc32: int

    @classmethod
    def validate(cls, path: str | Path) -> "DialFile":
        p = Path(path)
        data = p.read_bytes()
        if len(data) < HEADER.size + ITEM.size:
            raise ProtocolError("File too small to be a native dial")
        identifier, length, crc, width, height, _, _ = HEADER.unpack_from(data)
        if length != len(data) - HEADER.size:
            raise ProtocolError("Dial header size does not match file length")
        if zlib.crc32(data[HEADER.size:]) & 0xFFFFFFFF != crc:
            raise ProtocolError("Dial CRC32 mismatch")
        if (width, height) != WATCH_SIZE:
            raise ProtocolError(f"Expected native 240x240 face, got {width}x{height}")
        if identifier == 0:
            raise ProtocolError("Empty watch-face identifier")
        items = 0
        for offset in range(HEADER.size, min(len(data), HEADER.size + (MAX_ELEMENTS + 1) * ITEM.size), ITEM.size):
            if offset + ITEM.size > len(data):
                raise ProtocolError("Truncated element table")
            kind, w, pos, h, x, y, _, frames, _, _, _ = ITEM.unpack_from(data, offset)
            if not kind:
                break
            if w < 1 or h < 1 or frames < 1 or pos < HEADER.size or pos + w * h * frames * 2 > len(data):
                raise ProtocolError(f"Invalid element bounds at index {items} / kind {kind}")
            if x + w > width or y + h > height:
                raise ProtocolError(f"Element outside watch screen: type {kind}")
            items += 1
        else:
            raise ProtocolError("No element-table sentinel found; unsupported dial format")
        if items < 2:
            raise ProtocolError("No usable layers")
        return cls(p, identifier, len(data), width, height, items, hashlib.sha256(data).hexdigest(), crc)


def choose_chunk_size(max_without_response: int, mtu: int) -> int:
    """Choose a power-of-two data size, respecting 3-byte 27+index prefix and ATT."""
    limit = min(max_without_response, mtu - 3, 247) - 3
    if limit < 16:
        raise ProtocolError(f"BLE MTU/write length too small for index+payload: {limit}")
    return max(c for c in (16, 32, 64, 128) if c <= limit)


def section(index: int, payload: bytes) -> bytes:
    if not (0 <= index <= 65535):
        raise ProtocolError("Section sequence index overflow")
    if not payload:
        raise ProtocolError("Empty data section")
    return b"\x27" + index.to_bytes(2, "big") + payload


def status(packet: bytes) -> str | None:
    if packet.startswith(b"\x26\x03") and len(packet) >= 3:
        return {0: "success", 1: "failure", 2: "crc-failure", 3: "resume", 4: "next-block"}.get(packet[2], "unexpected")
    return None
