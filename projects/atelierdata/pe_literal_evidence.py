"""Strict, read-only PE32 string-literal evidence for static API triage.

Only complete NUL-terminated literals in initialized section bytes qualify.
This is not a disassembler, data-flow analysis, or IDF decoder.
"""
from __future__ import annotations

ASCII_WORD = frozenset(b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_')


def mapped_literal_positions(data: bytes, sections: list[dict], term: str,
                             encoding: str, limit: int = 1024):
    """Return (file_offset, RVA) hits and a truthful truncation flag.

    Ignore overlay, virtual-only tails, raw alignment padding, embedded word
    suffixes, and unterminated prefixes. A hit's NUL must be file-backed in
    the *same, unambiguously mapped* section. Positions are private.
    """
    if encoding not in ('ascii', 'utf-16le') or not isinstance(term, str) or not term:
        raise ValueError('Unsupported literal encoding or empty term')
    if type(limit) is not int or limit < 1:
        raise ValueError('Invalid literal limit')
    needle = term.encode(encoding)
    terminator = b'\x00' if encoding == 'ascii' else b'\x00\x00'
    found = []
    for index, sec in enumerate(sections):
        start = sec['raw_at']
        backed = min(sec['raw_size'], sec['vsize'])
        if backed <= 0 or start < 0 or start + backed > len(data):
            continue
        raw = data[start:start + backed]
        at = raw.find(needle)
        while at >= 0:
            end = at + len(needle)
            extent = end + len(terminator) - at
            terminated = end + len(terminator) <= len(raw) and raw[end:end + len(terminator)] == terminator
            if encoding == 'ascii':
                embedded = at > 0 and raw[at - 1] in ASCII_WORD
            else:
                embedded = (at >= 2 and (lambda c: c.isalnum() or c == '_')(\n                    chr(int.from_bytes(raw[at - 2:at], 'little'))))
            rva = sec['rva'] + at
            file_at = start + at
            # Raw aliases or overlapping RVAs make the source of a literal
            # ambiguous. Fail closed rather than double-counting bytes or
            # attributing one virtual address to multiple PE sections.
            if terminated and not embedded and 0 <= rva and rva + extent <= 0x100000000:
                ambiguous = False
                for other_index, other in enumerate(sections):
                    if other_index == index:
                        continue
                    other_backed = min(other['raw_size'], other['vsize'])
                    if other_backed <= 0:
                        continue
                    other_file = other['raw_at']
                    other_rva = other['rva']
                    if (file_at < other_file + other_backed and
                            other_file < file_at + extent) or (
                            rva < other_rva + other_backed and
                            other_rva < rva + extent):
                        ambiguous = True
                        break
                if not ambiguous:
                    if len(found) == limit:
                        return found, True
                    found.append((file_at, rva))
            at = raw.find(needle, at + 1)
    return found, False
