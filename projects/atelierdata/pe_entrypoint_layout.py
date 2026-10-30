"""Static PE32 entrypoint/section triage for authorized interoperability.

High entropy is not proof of packing, encryption or DRM. No target execution,
decoding or modification. Public output excludes raw code and offsets.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from pe_file_io_xrefs import MAX_PE, analyze as analyze_iat, parse_pe32, _u32

WINDOW = 65536


def entropy(data):
    if not data:
        return 0.0
    hist = Counter(data)
    return -sum((v / len(data)) * math.log2(v / len(data)) for v in hist.values())


def windows(data):
    if not data:
        return []
    size = min(WINDOW, len(data))
    offsets = (0, (len(data) - size) // 2, len(data) - size)
    return [round(entropy(data[o:o + size]), 4) for o in offsets]


def analyze_layout(data, expected_sha256):
    if len(data) > MAX_PE:
        raise ValueError('PE size limit exceeded')
    if (len(expected_sha256) != 64 or
        any(c not in '0123456789abcdefABCDEF' for c in expected_sha256)):
        raise ValueError('Expected SHA256 is mandatory')
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError('PE SHA256 mismatch')
    pe = parse_pe32(data)
    pe_offset = _u32(data, 0x3c)
    entry_rva = _u32(data, pe_offset + 24 + 16)
    section_rows = []
    entry_section = None
    for index, s in enumerate(pe['sections']):
        if s['rva'] <= entry_rva < s['rva'] + max(s['vsize'], s['raw_size']):
            if entry_section is not None:
                raise ValueError('Ambiguous entrypoint section: overlapping RVAs')
            entry_section = index
        raw = data[s['raw_at']:s['raw_at'] + s['raw_size']] if s['raw_size'] else b''
        section_rows.append(dict(index=index, name=s['name'], executable=s['executable'],
                                 raw_bytes=s['raw_size'], virtual_bytes=s['vsize'],
                                 entropy_first_middle_last=windows(raw)))
    if entry_section is None:
        raise ValueError('Entrypoint not mapped to any PE section')
    iat_public, iat_private = analyze_iat(data, expected_sha256)
    calls = Counter(item['section'] for item in iat_private['candidates'])
    for row in section_rows:
        row['iat_byte_pattern_candidates'] = calls[row['name']]
    other_high_entropy_exec = [
        row['index'] for row in section_rows
        if row['index'] != entry_section and row['executable'] and row['raw_bytes'] >= WINDOW
        and row['entropy_first_middle_last']
        and min(row['entropy_first_middle_last']) >= 7.95
    ]
    entry = section_rows[entry_section]
    entry_low_entropy = (entry['raw_bytes'] >= WINDOW and
                         entry['entropy_first_middle_last'] and
                         min(entry['entropy_first_middle_last']) < 7.0)
    last_raw = max((s['raw_at'] + s['raw_size'] for s in pe['sections'] if s['raw_size']), default=0)
    return dict(
        schema='atelierdata-pe-entrypoint-layout-v1', sha256=digest,
        binary_bytes=len(data), format='PE32 x86',
        entrypoint_section_index=entry_section, sections=section_rows,
        iat_candidate_total=iat_public['candidate_count'],
        iat_candidates_in_entrypoint_section=entry['iat_byte_pattern_candidates'],
        other_high_entropy_executable_section_indices=other_high_entropy_exec,
        loader_wrapper_hypothesis=bool(entry_low_entropy and other_high_entropy_exec),
        overlay_bytes=max(0, len(data) - last_raw),
        target_executed=False, decoder_proven=False,
        interpretation='Heuristic only. High entropy and section layout cannot establish packing, encryption, a loader, or IDF decoding.',
        next_step='Analyze entrypoint code and references to executable sections in a verified Ghidra project; do not assume decoded payloads.'
    )


def run(pe, expected_sha256, output):
    with Path(pe).open('rb') as fh:
        data = fh.read(MAX_PE + 1)
    report = analyze_layout(data, expected_sha256)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pe', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--public-output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.pe, args.expected_sha256, args.public_output)
    print(f"PE_LAYOUT_AUDIT=PASS entry_section={result['entrypoint_section_index']} "
          f"iat_candidates={result['iat_candidate_total']} "
          f"loader_wrapper_hypothesis={result['loader_wrapper_hypothesis']}")


if __name__ == '__main__':
    main()
