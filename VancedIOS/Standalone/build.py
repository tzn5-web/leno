#!/usr/bin/env python3
"""Build independently loadable arm64 tweaks with Logos' internal ObjC backend."""
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPS = ROOT / '.deps'
OUTPUT = ROOT / 'artifacts'


def run(args, **kwargs):
    print(' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def fetch_dependency(dep):
    target = DEPS / dep['name']
    target.mkdir(parents=True, exist_ok=True)
    archive = DEPS / (dep['name'] + '.tar.gz')
    url = f"https://codeload.github.com/{dep['repo']}/tar.gz/{dep['ref']}"
    urllib.request.urlretrieve(url, archive)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts[1:]
            if not parts or '.git' in parts:
                continue
            member.name = str(Path(*parts))
            tar.extract(member, target, filter='data')
    return target


def main():
    config = json.loads((ROOT / 'dependencies.json').read_text())
    DEPS.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    theos = ROOT.parent / '.toolchain' / 'theos'
    run(['bash', ROOT.parent / 'Scripts' / 'bootstrap_theos.sh'])
    paths = {d['name']: fetch_dependency(d) for d in config['dependencies']}
    settings = paths['YouPiP'] / 'Settings.x'
    original_settings = settings.read_text()
    start_marker = '    if (IS_IOS_OR_NEWER(iOS_14_0)) {'
    end_marker = '    YTAppSettingsSectionItemActionController *sectionItemActionController'
    if original_settings.count(start_marker) != 1 or original_settings.count(end_marker) != 1:
        raise RuntimeError('upstream PiP settings adapter no longer matches pinned source')
    start = original_settings.index(start_marker)
    end = original_settings.index(end_marker, start)
    if 'addObject:legacyPiP' not in original_settings[start:end]:
        raise RuntimeError('unexpected legacy PiP settings block')
    settings.write_text(original_settings[:start] + original_settings[end:])
    pip_tweak = paths['YouPiP'] / 'Tweak.x'
    pip_source = pip_tweak.read_text()
    dynamic_flag = '- (BOOL)hasPictureInPicture {\n    return YES;\n}'
    if pip_source.count(dynamic_flag) != 1:
        raise RuntimeError('dynamic PiP accessor adapter no longer matches pinned source')
    # This GPBMessage accessor is absent from the original 20.21.6 method table.
    # The internal hook backend enumerates methods without invoking resolution;
    # explicitly adding the accessor makes it override protobuf lazy resolution.
    pip_tweak.write_text(pip_source.replace(dynamic_flag, '%new(B@:)\n' + dynamic_flag))
    # YouPiP's relative includes expect the sibling folder YTVideoOverlay.
    include = DEPS / 'include'
    include.mkdir(exist_ok=True)
    for header in ('YouTubeHeader', 'PSHeader'):
        shutil.copytree(paths[header], include / header, dirs_exist_ok=True)
    shutil.copy2(ROOT / 'rootless.h', include / 'rootless.h')
    sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
    common = ['xcrun', '--sdk', 'iphoneos', 'clang', '-dynamiclib', '-arch', 'arm64',
              '-isysroot', sdk, '-miphoneos-version-min=15.0', '-fobjc-arc', '-fblocks',
              '-O2', '-DNDEBUG=1', '-DDEBUG=0', '-I' + str(include),
              '-I' + str(theos / 'include'), '-I' + str(theos / 'vendor/include'),
              '-I' + str(theos / 'include/_fallback'),
              '-F' + str(theos / 'vendor/lib'), '-F' + str(theos / 'lib'), '-framework', 'Foundation',
              '-framework', 'UIKit', '-framework', 'AVFoundation', '-framework', 'AVKit', '-framework', 'CoreGraphics']
    targets = {
        'VancedIdentity': [ROOT / 'VancedIdentity.m', ROOT / 'VUpdatePolicy.m'],
        'YouTubeX': [paths['YouTubeX'] / 'Tweak.x'],
        'YTVideoOverlay': [paths['YTVideoOverlay'] / 'Tweak.x'],
        'VancedGuest': [ROOT / 'VancedGuest.x', ROOT / 'VGuestEntry.m', ROOT / 'VGuestStore.m', ROOT / 'VGuestUI.m', ROOT / 'VDiagnostics.m'],
        'YouPiP': [paths['YouPiP'] / 'Tweak.x', paths['YouPiP'] / 'Settings.x', ROOT / 'ModernPiP.m']
    }
    evidence = {'status': 'PASS_BUILD_ONLY', 'runtime': 'NOT_TESTED', 'sdk': sdk,
                'dependencies': config['dependencies'],
                'adapters': ['internal Objective-C hook backend', 'identity paths for a jailed app',
                             'iOS 15+ PiP only; legacy compatibility code and settings row excluded',
                             'explicit dynamic protobuf hasPictureInPicture accessor',
                             'upgrade policy/presentation disabled; native worker completion preserved'],
                'artifacts': {}}
    for name, sources in targets.items():
        processed = []
        for source in sources:
            if source.suffix == '.x':
                output = source.with_suffix('.generated.m')
                with output.open('w') as stream:
                    run([theos / 'bin/logos.pl', '-c', 'generator=internal', source], stdout=stream)
                processed.append(output)
            else:
                processed.append(source)
        binary = OUTPUT / (name + '.dylib')
        extra = ['-framework', 'Security', '-Wall', '-Wextra', '-Werror'] if name == 'VancedIdentity' else []
        if name in ('YouPiP', 'VancedGuest'):
            # Enforce initialization order: overlay registration precedes PiP.
            extra += ['-Wl,-needed_library,' + str(OUTPUT / 'YTVideoOverlay.dylib')]
        run(common + extra + processed + ['-Wl,-install_name,@rpath/' + binary.name, '-o', binary])
        dependencies = subprocess.check_output(['xcrun', 'otool', '-L', binary], text=True)
        if 'libsubstrate' in dependencies or 'CydiaSubstrate' in dependencies:
            raise RuntimeError('unexpected external hook runtime: ' + dependencies)
        run(['xcrun', 'nm', '-u', binary])
        evidence['artifacts'][binary.name] = {'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                                             'size': binary.stat().st_size, 'dependencies': dependencies}
    for name in ('YouPiP', 'YTVideoOverlay'):
        resource = paths[name] / 'layout/Library/Application Support' / (name + '.bundle')
        shutil.copytree(resource, OUTPUT / resource.name, dirs_exist_ok=True)
    licenses = OUTPUT / 'VancedLicenses'
    licenses.mkdir(exist_ok=True)
    for name in ('YouTubeX', 'YouPiP', 'YTVideoOverlay'):
        shutil.copy2(paths[name] / 'LICENSE', licenses / (name + '.txt'))
    (OUTPUT / 'BUILD.json').write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    main()
