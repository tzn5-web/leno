#!/usr/bin/env python3
"""Fail-closed structural gate for real Xiaomi LatinIME Glass APK builds.

Usage:
  python3 audit_full_apk.py original-installed-glass.apk rebuilt-unsigned.apk

Compare against the previously working Xiaomi based APK, not a synthetic
keyboard. This verifier never reads or stores user keystrokes; APK code and
resources only. It does NOT prove runtime usability or zero text retention.
"""
import argparse
import collections
import hashlib
import struct
import zipfile

READ16 = lambda b,p: struct.unpack_from('<H', b, p)[0]
READ32 = lambda b,p: struct.unpack_from('<I', b, p)[0]
IMENAME = 'com.android.inputmethod.latin.LatinIME'
WRONG = 'com.android.inputmethod.latin.GlassIME'
SETTINGS = 'com.android.inputmethod.latin.setup.GlassActivity'


def strings(axml):
    if READ16(axml, 0) != 3 or READ16(axml, 8) != 1:
        raise ValueError('Expected binary Android XML')
    pool, header = 8, READ16(axml, 10)
    count, flags, start = READ32(axml, 16), READ32(axml, 24), READ32(axml, 28)

    def utf8len(p):
        size = axml[p]; p += 1
        if size & 0x80:
            size, p = ((size & 0x7f) << 8) | axml[p], p + 1
        return size, p

    def utf16len(p):
        size = READ16(axml, p); p += 2
        if size & 0x8000:
            size, p = ((size & 0x7fff) << 16) | READ16(axml, p), p + 2
        return size, p

    values = []
    for index in range(count):
        p = pool + start + READ32(axml, pool + header + index * 4)
        if flags & 0x100:
            _, p = utf8len(p)
            n, p = utf8len(p)
            values.append(axml[p:p+n].decode('utf-8'))
        else:
            n, p = utf16len(p)
            values.append(axml[p:p+n*2].decode('utf-16le'))
    return values


def start_elements(axml):
    names = strings(axml)
    p = 8 + READ32(axml, 12)
    while p < len(axml):
        kind, length = READ16(axml, p), READ32(axml, p + 4)
        if length < 8 or p + length > len(axml):
            raise ValueError('Invalid binary XML chunk')
        if kind == 0x102:
            element = names[READ32(axml, p + 20)]
            attr_start, stride, count = READ16(axml,p+24), READ16(axml,p+26), READ16(axml,p+28)
            values = {}
            for index in range(count):
                at = p + 16 + attr_start + index * stride
                key = names[READ32(axml,at+4)]
                raw = READ32(axml,at+8)
                if raw != 0xffffffff:
                    value = names[raw]
                elif axml[at+15] == 3:
                    value = names[READ32(axml,at+16)]
                else:
                    value = READ32(axml,at+16)
                values[key] = value
            yield element, values
        p += length


def check(original_apk, rebuilt_apk):
    with zipfile.ZipFile(original_apk) as original, zipfile.ZipFile(rebuilt_apk) as output:
        bad_integrity = original.testzip(), output.testzip()
        assert bad_integrity == (None,None), f'Corrupted APK ZIP members: {bad_integrity}'
        origin_names = set(original.namelist())
        output_names = set(output.namelist())
        assert output_names >= { 'classes.dex', 'classes2.dex',
            'AndroidManifest.xml', 'res/xml/method.xml' }
        assert origin_names - output_names <= {
            n for n in origin_names if n.startswith('META-INF/')
        }, 'Unexpected removal of original APK files'

        changes = []
        for name in origin_names.intersection(output_names):
            if original.read(name) != output.read(name):
                changes.append(name)
                assert name in {
                    'AndroidManifest.xml', 'classes.dex', 'classes2.dex'
                }, f'Original Xiaomi asset unexpectedly altered: {name}'
        assert sorted(changes) == [
            'AndroidManifest.xml', 'classes.dex', 'classes2.dex'
        ], f'Expected exactly three changes, got {sorted(changes)}'

        manifest = list(start_elements(output.read('AndroidManifest.xml')))
        services = [
            attrs.get('name') for element, attrs in manifest
            if element == 'service' and attrs.get('permission') ==
                'android.permission.BIND_INPUT_METHOD'
        ]
        assert services == [IMENAME], f'Unexpected actual IME component: {services}'
        assert WRONG not in [attrs.get('name') for _,attrs in manifest]
        assert SETTINGS in [
            attrs.get('name') for element, attrs in manifest if element == 'activity'
        ], 'GlassActivity missing in manifest'

        ime_xml = list(start_elements(output.read('res/xml/method.xml')))
        input_methods = [attrs for element,attrs in ime_xml if element == 'input-method']
        assert len(input_methods) == 1, 'IME settings root missing/duplicated'
        assert input_methods[0].get('settingsActivity') == SETTINGS, (
            'Android IME settings gear does not open GlassActivity'
        )
        original_ime = list(start_elements(original.read('res/xml/method.xml')))
        assert ime_xml == original_ime, 'Original Romanian/English input subtypes changed'

        addon = output.read('classes2.dex')
        core = output.read('classes.dex')
        assert addon.startswith(b'dex\n') and core.startswith(b'dex\n')
        assert len(addon) > 8000, 'Glass/Emoji addon DEX unexpectedly small'

        fixed_assets = [
            name for name in origin_names if name.startswith(('assets/','res/','lib/'))
        ]
        assert all(original.read(n) == output.read(n) for n in fixed_assets)
        assert any('keyboard_background' in n for n in fixed_assets)
        print('PASS: original Xiaomi keys, borders, dictionaries and layouts untouched')
        print('PASS: original LatinIME Android service identity and Glass settings')
        print('PASS: original IME language subtypes (including Romanian) unchanged')
        print('PASS: both DEX files present and no unexpected binary changes')
        print('ORIGINAL RESOURCE ENTRIES:',len(fixed_assets))
        print('CHANGED ENTRIES:',', '.join(sorted(changes)))
        print('QA APK SHA256:',hashlib.sha256(open(rebuilt_apk,'rb').read()).hexdigest())
        print('NOT TESTED: Samsung runtime, window blur support, emoji clicks, crashes')
        print('NOT CERTIFIED: lack of original dictionary text persistence')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('previous_glass_apk')
    parser.add_argument('rebound_unsigned_apk')
    args = parser.parse_args()
    check(args.previous_glass_apk, args.rebound_unsigned_apk)
