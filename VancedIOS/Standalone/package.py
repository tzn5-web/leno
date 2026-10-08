#!/usr/bin/env python3
"""Package the user's local decrypted app; never upload the proprietary IPA."""
import argparse
import copy
import hashlib
import json
import plistlib
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = 'Payload/YouTube.app/'
LIBRARIES = ('VancedIdentity', 'YTVideoOverlay', 'YouPiP', 'YouTubeX')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def commands(data):
    if data[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError('expected a thin little-endian arm64 Mach-O')
    if struct.unpack_from('<I', data, 4)[0] != 0x100000c:
        raise ValueError('expected arm64')
    count, total = struct.unpack_from('<II', data, 16)
    offset = 32
    result = []
    for _ in range(count):
        cmd, size = struct.unpack_from('<II', data, offset)
        if size < 8 or size % 8 or offset + size > 32 + total:
            raise ValueError('invalid Mach-O load-command bounds')
        result.append((cmd, offset, bytes(data[offset:offset + size])))
        offset += size
    if offset != 32 + total:
        raise ValueError('incorrect load-command length')
    return result


def unsigned_macho(original, additions=()):
    data = bytearray(original)
    old_commands = commands(data)
    signed = [(offset, raw) for cmd, offset, raw in old_commands if cmd == 0x1d]
    if len(signed) > 1:
        raise ValueError('duplicate code signature load commands')
    end = len(data)
    if signed:
        signature_offset, signature_size = struct.unpack_from('<II', signed[0][1], 8)
        if signature_offset + signature_size != len(data):
            raise ValueError('signature is not a removable tail region')
        end = signature_offset
        data = data[:end]
    updated = []
    first_content = len(data)
    for cmd, offset, raw in old_commands:
        raw = bytearray(raw)
        if cmd == 0x1d:
            continue
        if cmd == 0x2c and struct.unpack_from('<I', raw, 16)[0] != 0:
            raise ValueError('the app contains encrypted executable code')
        if cmd == 0x19:
            segment_name = raw[8:24].split(b'\0')[0]
            file_offset, file_size = struct.unpack_from('<QQ', raw, 40)
            if segment_name == b'__LINKEDIT':
                size = end - file_offset
                if size < 0:
                    raise ValueError('invalid linkedit offset')
                struct.pack_into('<Q', raw, 48, size)
                struct.pack_into('<Q', raw, 32, (size + 0x3fff) & ~0x3fff)
            section_count = struct.unpack_from('<I', raw, 64)[0]
            for i in range(section_count):
                section = 72 + i * 80
                length = struct.unpack_from('<Q', raw, section + 40)[0]
                section_offset = struct.unpack_from('<I', raw, section + 48)[0]
                if length and section_offset:
                    first_content = min(first_content, section_offset)
        updated.append(bytes(raw))
    for path in additions:
        raw_name = path.encode() + b'\0'
        size = (24 + len(raw_name) + 7) & ~7
        updated.append(struct.pack('<6I', 0xc, size, 24, 0, 0x10000, 0x10000) + raw_name + bytes(size - 24 - len(raw_name)))
    raw_commands = b''.join(updated)
    old_size = struct.unpack_from('<I', original, 20)[0]
    if 32 + len(raw_commands) > first_content:
        raise ValueError('insufficient header padding for conservative injection')
    if any(original[32 + old_size:32 + len(raw_commands)]):
        raise ValueError('load commands would overwrite nonzero header data')
    struct.pack_into('<II', data, 16, len(updated), len(raw_commands))
    data[32:32 + max(old_size, len(raw_commands))] = raw_commands + bytes(max(old_size - len(raw_commands), 0))
    # Every byte beyond the first section, up to the removed signature, stays
    # identical. Chained fixups and existing dylib ordinals are not rewritten.
    if data[first_content:end] != original[first_content:end]:
        raise ValueError('unexpected changes to executable or linkedit content')
    commands(data)
    return bytes(data)


def standalone_info(raw, config):
    info = plistlib.loads(raw)
    info['CFBundleIdentifier'] = config['bundle_id']
    info['CFBundleDisplayName'] = config['display_name']
    info['CFBundleName'] = config['display_name']
    info['CFBundleURLTypes'] = [{'CFBundleURLName': config['bundle_id'],
                               'CFBundleURLSchemes': ['youtubevanced', config['bundle_id']]}]
    info['NSUserActivityTypes'] = [v.replace('com.google.ios.youtube', config['bundle_id']) for v in info.get('NSUserActivityTypes', [])]
    queries = info.get('LSApplicationQueriesSchemes', [])
    info['LSApplicationQueriesSchemes'] = [s for s in queries if 'youtube' not in s.lower()]
    # Native playback already requests the audio background mode.
    if 'audio' not in info.get('UIBackgroundModes', []):
        raise ValueError('audio background mode missing in original app')
    info['UIBackgroundModes'] = [m for m in info['UIBackgroundModes'] if m != 'remote-notification']
    return plistlib.dumps(info, fmt=plistlib.FMT_BINARY, sort_keys=False)


def should_remove(name):
    return (name.startswith(APP + 'PlugIns/') or '/_CodeSignature/' in name or
            name.endswith('/_CodeSignature/') or name.endswith('.mobileprovision') or
            name.startswith(APP + 'SC_Info/') or name.startswith('META-INF/'))


def package(source, artifacts, output):
    config = json.loads((ROOT / 'dependencies.json').read_text())
    if sha(source.read_bytes()) != config['original_sha256']:
        raise ValueError('input does not match the audited original YouTube 20.21.6 IPA')
    build = json.loads((artifacts / 'BUILD.json').read_text())
    if build['status'] != 'PASS_BUILD_ONLY' or build['dependencies'] != config['dependencies']:
        raise ValueError('build evidence does not match pinned module sources')
    removed, changed, preserved, added = [], [], [], []
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as z, zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        if len(set(z.namelist())) != len(z.namelist()):
            raise ValueError('duplicate ZIP entries in input')
        for entry in z.infolist():
            name = entry.filename
            if should_remove(name):
                removed.append(name)
                continue
            data = z.read(name)
            original = data
            if name == APP + 'Info.plist':
                data = standalone_info(data, config)
            elif name == APP + 'YouTube':
                data = unsigned_macho(data, ['@executable_path/Frameworks/' + n + '.dylib' for n in LIBRARIES])
            elif data[:4] == b'\xcf\xfa\xed\xfe':
                data = unsigned_macho(data)
            (changed if data != original else preserved).append(name)
            entry = copy.copy(entry)
            # Store Info.plist files uncompressed for signer compatibility.
            entry.compress_type = zipfile.ZIP_STORED if name.endswith('Info.plist') else zipfile.ZIP_DEFLATED
            out.writestr(entry, data)
        for name in LIBRARIES:
            filename = name + '.dylib'
            binary = (artifacts / filename).read_bytes()
            if sha(binary) != build['artifacts'][filename]['sha256']:
                raise ValueError('module hash differs from CI build: ' + filename)
            binary = unsigned_macho(binary)
            path = APP + 'Frameworks/' + filename
            entry = zipfile.ZipInfo(path)
            entry.create_system = 3
            entry.external_attr = 0o100755 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(entry, binary)
            added.append(path)
        for resource in ('YouPiP.bundle', 'YTVideoOverlay.bundle', 'VancedLicenses'):
            for path in sorted((artifacts / resource).rglob('*')):
                if path.is_file():
                    name = APP + path.relative_to(artifacts).as_posix()
                    out.writestr(name, path.read_bytes(), compress_type=zipfile.ZIP_STORED if path.name == 'Info.plist' else zipfile.ZIP_DEFLATED)
                    added.append(name)
    report = {'status': 'PACKAGED_UNSIGNED_DEVICE_TEST_PENDING', 'source_sha256': config['original_sha256'],
              'output_sha256': sha(output.read_bytes()), 'bundle_id': config['bundle_id'],
              'display_name': config['display_name'], 'removed': removed, 'changed': changed,
              'preserved_count': len(preserved), 'added': added, 'build': build,
              'limitations': ['Full recursive personal signing required before installation.',
                              'Runtime, login and signing on iOS 27.0.1 are not yet tested.',
                              'Five original app extensions are intentionally excluded.',
                              'Original URL schemes and shared Google app groups are not reused.',
                              'Google login uses compatibility hooks but needs a device test.']}
    output.with_suffix('.audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status','output_sha256','bundle_id','preserved_count','changed')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    package(args.input, args.artifacts, args.output)
