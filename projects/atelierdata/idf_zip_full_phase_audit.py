"""Full-member static IDF stride/phase audit on SHA256-verified ZIP.

The existing bounded ZIP audit is the preflight for path, symlink, duplicate,
size, CRC and blocked-part checks. This second pass reads only authorized .IDF
members; output contains aggregates, not original bytes, names or offsets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from idf_full_phase import phase_summary
from idf_zip_stride_streaks import audit, STRIDES, SCAN_LIMIT


def audit_full(archive_path: Path, expected_sha256: str) -> dict:
    archive_path = Path(archive_path)
    baseline = audit(archive_path, expected_sha256)
    count = baseline['idf_files_crc_checked']
    totals = {str(s): {'files_qualified': 0, 'files_single_phase': 0,
                       'qualified_runs': 0, 'longest_run': 0,
                       'covered_bytes': 0, 'new_files_after_first_window': 0}
              for s in STRIDES}
    seen = 0
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir() or not member.filename.casefold().endswith('.idf'):
                continue
            data = archive.read(member)
            seen += 1
            for stride in STRIDES:
                full = phase_summary(data, stride)
                bucket = totals[str(stride)]
                if not full['qualified_runs']:
                    continue
                bucket['files_qualified'] += 1
                bucket['files_single_phase'] += int(full['distinct_phases'] == 1)
                bucket['qualified_runs'] += full['qualified_runs']
                bucket['longest_run'] = max(bucket['longest_run'], full['longest_qualified_run'])
                bucket['covered_bytes'] += full['qualified_coverage_bytes']
                if not phase_summary(data[:SCAN_LIMIT], stride)['qualified_runs']:
                    bucket['new_files_after_first_window'] += 1
    if seen != count:
        raise ValueError('ZIP member inventory changed during analysis')
    h = hashlib.sha256()
    with archive_path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    if h.hexdigest() != expected_sha256:
        raise ValueError('ZIP changed during analysis')
    return {'schema': 'atelierdata-idf-zip-full-phase-v1',
            'archive_sha256_verified_before_and_after': True,
            'idf_files_crc_checked': count,
            'idf_bytes_crc_checked': baseline['idf_bytes_crc_checked'],
            'all_member_bytes_scanned_for_stride_candidates': True,
            'stride_candidates': list(STRIDES),
            'minimum_consecutive_complete_rows': 32,
            'by_stride': totals,
            'original_executed': False,
            'idf_decoder_proven': False,
            'limitations': ('Every member byte was checked for fixed-stride token repetition. '
                            'Runs require a diverse 8-byte token and >=4 distinct suffixes '
                            'with >=2 varying columns in up to 128 sampled rows. '
                            'Counts saturate at 65535. Phase consistency is not proof '
                            'of record boundaries, field semantics, decoding or encryption.')}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', required=True, type=Path)
    parser.add_argument('--expected-zip-sha256', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and (args.output.is_symlink() or
                        args.output.resolve() == args.zip.resolve()):
        parser.error('Output must not alias original ZIP')
    result = audit_full(args.zip, args.expected_zip_sha256)
    rendered = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')


if __name__ == '__main__':
    main()
