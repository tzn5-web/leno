"""Read-only, evidence-limited Autodata distribution installation readiness report.

Uses owner-provided SHA256 manifest and optional authorized ZIP parts. Does not
unpack, execute, patch, register, install, or activate original components.
Checksums prove integrity against a manifest, not authenticity or licensing.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path, PurePosixPath

from original_archive_preflight import load_manifest
from original_runtime_dependency_audit import audit as runtime_audit

ROOT = 'Autodata__3.45/'
APP = ROOT + 'ADCDA2/'
ENTRY = APP + 'ADBCD.exe'
RUNTIME_DLLS = ('RelLic.dll', 'SentinelKeyW.DLL', 'ChilkatCert.dll',
                'ChilkatCrypt2.dll', 'ChilkatUtil.dll', 'cw3220mt.dll',
                'gdiplus.dll', 'libeay32.dll', 'ssleay32.dll')
INSTALLER_NAMES = ('Install-x32.cmd', 'Install-x64.cmd',
                   'Sentinel Protection Installer 7.6.1.exe',
                   'Sentinel Protection Installer 7.6.6.exe',
                   'vcredist_x86.exe', 'vcredist_x64.exe', 'RegSvr.bat')
# Name-based security review leads only; NOT malware verdicts.
UNTRUSTED_ACTIVATION_TERMS = ('keygen', 'emulator', 'dseo', 'license.exe',
                              'getuid', 'audas0')


def _package_for(row: dict) -> set[str]:
    return {chunk['package'] for chunk in row['chunks']}


def _status(row: dict, available: set[str]) -> str:
    return 'packages_present_not_hash_verified' if _package_for(row) <= available else 'package_unavailable'


def analyze_manifest(manifest: dict, available: set[str]) -> dict:
    """Compute manifest facts; never confuse package presence with SHA verification."""
    rows = {x['path']: x for x in manifest['files']}
    packages = {chunk['package'] for x in rows.values() for chunk in x['chunks']}
    if len(rows) != len(manifest['files']):
        raise ValueError('Duplicate manifest path')
    if ENTRY not in rows:
        raise ValueError('Main executable missing from inventory')
    if not packages or (manifest.get('package_count') is not None and
                        manifest['package_count'] != len(packages)):
        raise ValueError('Package count mismatch')
    if not available <= packages:
        raise ValueError('Unknown package name supplied as available')

    idf = [x for x in rows.values() if x['path'].lower().endswith('.idf')]
    idf_available = [x for x in idf if _package_for(x) <= available]
    app_modules = [x for x in rows.values()
                   if x['path'].startswith(APP) and '/' not in x['path'][len(APP):]]
    dlls = {PurePosixPath(x['path']).name.casefold(): x for x in app_modules
            if x['path'].lower().endswith('.dll')}
    installers = []
    for name in INSTALLER_NAMES:
        matches = [x for x in rows.values() if PurePosixPath(x['path']).name.casefold() == name.casefold()]
        for row in matches:
            installers.append({'name': name, 'package_status': _status(row, available),
                               'package': sorted(_package_for(row)),
                               'purpose_inferred_from_filename_only': True})
    indicators = []
    for row in rows.values():
        tail = row['path'][len(ROOT):].casefold()
        if any(term in tail for term in UNTRUSTED_ACTIVATION_TERMS):
            indicators.append({'name': PurePosixPath(row['path']).name,
                               'package_status': _status(row, available),
                               'manual_security_review_required': True})

    groups = defaultdict(list)
    for row in rows.values():
        if len(row['chunks']) == 1:
            chunk = row['chunks'][0]
            groups[(chunk['bytes'], chunk['sha256'].lower())].append(row['path'])
    duplicate_groups = [
        {'sha256': sha, 'bytes': size,
         'names': sorted(PurePosixPath(path).name for path in members),
         'all_in_unavailable_packages': all(not (_package_for(rows[path]) <= available) for path in members)}
        for (size, sha), members in groups.items() if len(members) > 1
    ]
    duplicate_groups.sort(key=lambda x: (x['names'], x['sha256']))

    module_status = {}
    for name in RUNTIME_DLLS:
        row = dlls.get(name.casefold())
        module_status[name] = (_status(row, available) if row else 'not_in_manifest')

    blocked = sorted(packages - available)
    missing_idf = len(idf) - len(idf_available)
    installer_accessible = sum(x['package_status'] != 'package_unavailable' for x in installers)
    return {
        'schema': 'atelierdata-original-installation-readiness-v1',
        'scope': 'manifest_inventory_only; ZIP presence is not a SHA256 verification',
        'original_executed': False, 'installer_executed': False,
        'license_checked': False, 'authenticity_verified': False,
        'file_count': len(rows), 'expected_package_count': len(packages),
        'available_package_count': len(available), 'unavailable_packages': blocked,
        'idf_count': len(idf), 'idf_wholly_in_present_packages': len(idf_available),
        'idf_requiring_unavailable_packages': missing_idf,
        'idf_data_complete_by_package_presence_only': missing_idf == 0,
        'main_executable': {'name': 'ADBCD.exe', 'status': _status(rows[ENTRY], available),
                            'bytes': rows[ENTRY]['size_bytes'],
                            'sha256': rows[ENTRY]['chunks'][0]['sha256'] if len(rows[ENTRY]['chunks']) == 1 else None},
        'root_runtime_dlls': module_status,
        'installer_named_entries': installers,
        'named_installer_entries_accessible': installer_accessible,
        'activation_or_emulation_name_indicators': sorted(indicators, key=lambda x: x['name'].casefold()),
        'manifest_declared_equal_sha256_groups_unverified_when_package_absent': duplicate_groups,
        'blocking_facts': [
            'Installer scripts, registration files, vendor driver redistributables and activation-related tools '
            'are in unavailable ZIP packages; their content and provenance have not been verified.'
            if not installer_accessible else
            'Some installer-named files are available, but their provenance and safe execution remain unverified.',
            'Presence of a SentinelKeyW.DLL name or literal does not prove mandatory runtime loading.',
            'License entitlement, genuine vendor installer and compatibility on Windows remain unverified.',
        ],
        'safe_next_action': 'Obtain an authentic vendor-authorized installer and license through official channels; '
                            'inspect its signature and vendor documentation before isolated Windows testing. '
                            'Never run activation/emulation tools from the untrusted package.',
        'conclusion': 'NOT_READY_FOR_ORIGINAL_WINDOWS_EXECUTION',
    }


def build_report(manifest_path: Path, parts_dir: Path | None = None) -> dict:
    manifest, _ = load_manifest(manifest_path)
    packages = {c['package'] for f in manifest['files'] for c in f['chunks']}
    if parts_dir is None:
        available = set()
    else:
        directory = Path(parts_dir).resolve(strict=True)
        if not directory.is_dir():
            raise ValueError('Expected ZIP directory')
        available = {p for p in packages if (directory / p).is_file() and not (directory / p).is_symlink()}
    result = analyze_manifest(manifest, available)
    if parts_dir is not None and result['main_executable']['status'] != 'package_unavailable':
        runtime = runtime_audit(manifest_path, parts_dir)
        result['static_runtime_evidence'] = {
            'main_executable_sha256_verified': runtime['components']['ADBCD.EXE']['status'] == 'verified',
            'verified_pe_components': runtime['verified_component_count'],
            'invalid_pe_components': sorted(name for name, row in runtime['components'].items()
                                            if row['status'] not in ('verified', 'package_unavailable')),
            'unavailable_pe_components': runtime['unavailable_component_count'],
            'direct_import_unresolved_count': len(runtime['unresolved_direct_imports']),
            'direct_import_unresolved': runtime['unresolved_direct_imports'],
            'sentinel_literal_candidate': runtime['sentinel_literal_candidate'],
            'note': 'Only verified PE modules and direct import names; dynamic loads not proven.'
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--parts-dir', type=Path, help='Optional user-authorized directory with ZIP parts')
    parser.add_argument('--output', type=Path, help='Optional JSON report; no proprietary bytes')
    args = parser.parse_args()
    result = build_report(args.manifest, args.parts_dir)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
