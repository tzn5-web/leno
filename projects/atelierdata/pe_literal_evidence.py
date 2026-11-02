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
    the *same* section. Positions are private and must not be published.
    """
    if encoding not in ('ascii', 'utf-16le') or not isinstance(term, str) or not term:
        raise ValueError('Unsupported literal encoding or empty term')
    if type(limit) is not int or limit < 1:
        raise ValueError('Invalid literal limit')
    needle = term.encode(encoding)
    terminator = b'\x00' if encoding == 'ascii' else b'\x00\x00'
    found = []
    for sec in sections:
        start = sec['raw_at']
        backed = min(sec['raw_size'], sec['vsize'])
        if backed <= 0 or start < 0 or start + backed > len(data):
            continue
        raw = data[start:start + backed]
        at = raw.find(needle)
        while at >= 0:
            end = at + len(needle)
            terminated = end + len(terminator) <= len(raw) and raw[end:end + len(terminator)] == terminator
            if encoding == 'ascii':
                embedded = at > 0 and raw[at - 1] in ASCII_WORD
            else:
                embedded = (at >= 2 and raw[at - 1] == 0 and raw[at - 2] in ASCII_WORD)
            rva = sec['rva'] + at
            if terminated and not embedded and 0 <= rva <= 0xffffffff:
                if len(found) == limit:
                    return found, True
                found.append((start + at, rva))
            at = raw.find(needle, at + 1)
    return found, False
