#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'Config' / 'dependencies.lock.json'
THIRD = ROOT / 'ThirdParty'


def cmd(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def main() -> int:
    data = json.loads(LOCK.read_text(encoding='utf-8'))
    errors = []
    warnings = []
    rows = []

    entries = []
    for item in data.get('headers', []):
        entries.append(('header', item, THIRD / 'Headers' / item['name']))
    for item in data.get('modules', []):
        entries.append(('module', item, THIRD / 'Modules' / item['name']))

    for kind, item, path in entries:
        row = {'kind': kind, 'name': item['name'], 'path': str(path), 'expected_ref': item['ref'], 'expected_repo': item['repo'], 'license': item.get('license')}
        if not (path / '.git').exists():
            errors.append(f"missing checkout: {item['name']}")
            row['ok'] = False
            rows.append(row)
            continue
        try:
            head = cmd(['git', 'rev-parse', 'HEAD'], cwd=path)
            origin = cmd(['git', 'remote', 'get-url', 'origin'], cwd=path)
            status = cmd(['git', 'status', '--porcelain'], cwd=path)
            submodules = cmd(['git', 'submodule', 'status', '--recursive'], cwd=path)
        except subprocess.CalledProcessError as exc:
            errors.append(f"git probe failed for {item['name']}: {exc.output}")
            row['ok'] = False
            rows.append(row)
            continue

        row.update({'actual_ref': head, 'origin': origin, 'dirty': bool(status), 'submodules': submodules.splitlines() if submodules else []})
        ok = True
        if head != item['ref']:
            errors.append(f"pin mismatch {item['name']}: expected {item['ref']} actual {head}")
            ok = False
        if origin.rstrip('/').removesuffix('.git') != item['repo'].rstrip('/').removesuffix('.git'):
            errors.append(f"origin mismatch {item['name']}: expected {item['repo']} actual {origin}")
            ok = False
        if status:
            errors.append(f"dirty dependency checkout: {item['name']}")
            ok = False
        bad_submodules = [line for line in row['submodules'] if line[:1] in {'-', '+', 'U'}]
        if bad_submodules:
            errors.append(f"submodule state invalid for {item['name']}: {bad_submodules}")
            ok = False
        if item.get('license') == 'NO-LICENSE-DETECTED':
            warnings.append(f"no license file detected upstream for {item['name']}; do not vendor/distribute it without resolving terms")
        row['ok'] = ok
        rows.append(row)

    result = {'status': 'PASS' if not errors else 'FAIL', 'errors': errors, 'warnings': warnings, 'dependencies': rows}
    print(json.dumps(result, indent=2, sort_keys=True))
    reports = ROOT / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    (reports / 'DEPENDENCY_AUDIT.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
