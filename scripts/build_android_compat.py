#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a development app and dependency-free Android instrumentation APK offline.

Uses the same SDK/JDK overrides as build_android.py. No device is contacted.
Only build/debug-signing.p12, alias pi-console-debug, password android is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from release_android import verify_resource_table

ROOT = Path(__file__).resolve().parents[1]


def run(args, capture=False):
    result = subprocess.run(list(map(str, args)), check=True, stdin=subprocess.DEVNULL,
                            text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout if capture else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse-debug', action='store_true',
                        help='Compile-only local checks: use existing development APK/key')
    args = parser.parse_args()
    # This builder has no release-signing path and ignores all PI_CONSOLE_KEY* values.
    if not args.reuse_debug:
        run([sys.executable, '-B', ROOT / 'scripts/build_android.py'])
    build = ROOT / 'build'
    app = build / 'pi-console-debug.apk'
    key = build / 'debug-signing.p12'
    for path in (app, key):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing regular development APK/key; build debug app first')
    sdk = Path(os.environ.get('ANDROID_HOME', os.environ.get('ANDROID_SDK_ROOT', '/nonexistent')))
    tools = sdk / 'build-tools' / os.environ.get('PI_ANDROID_BUILD_TOOLS', '35.0.0')
    platform = sdk / 'platforms/android-35/android.jar'
    resource = Path(os.environ.get('PI_ANDROID_RESOURCE_JAR', str(platform)))
    jbin = Path(os.environ.get('JAVA_HOME', '/nonexistent')) / 'bin'
    java = str(jbin / 'java') if (jbin / 'java').is_file() else 'java'
    javac = str(jbin / 'javac') if (jbin / 'javac').is_file() else 'javac'
    aapt = os.environ.get('PI_ANDROID_AAPT2', str(tools / 'aapt2'))
    align = os.environ.get('PI_ANDROID_ZIPALIGN', str(tools / 'zipalign'))
    d8 = [java, '-cp', os.environ['PI_ANDROID_D8_JAR'], 'com.android.tools.r8.D8'] if 'PI_ANDROID_D8_JAR' in os.environ else [tools / 'd8']
    signer = [java, '-jar', os.environ['PI_ANDROID_APKSIGNER_JAR']] if 'PI_ANDROID_APKSIGNER_JAR' in os.environ else [tools / 'apksigner']
    work = build / 'android-compat'
    if work.is_symlink():
        raise ValueError('Compatibility build directory must not be a symlink')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    classes = work / 'classes'
    dex = work / 'dex'
    classes.mkdir()
    dex.mkdir()
    source = ROOT / 'android/compat'
    run([javac, '--release', '8', '-classpath', platform, '-d', classes,
         *sorted((source / 'src').rglob('*.java'))])
    jar = work / 'classes.jar'
    with zipfile.ZipFile(jar, 'w') as out:
        for path in sorted(classes.rglob('*.class')):
            out.write(path, path.relative_to(classes))
    run([*d8, '--release', '--min-api', '26', '--lib', platform, '--output', dex, jar])
    run([aapt, 'compile', '--dir', source / 'res', '-o', work / 'compiled.zip'])
    run([aapt, 'link', '--manifest', source / 'AndroidManifest.xml', '-I', resource,
         '-o', work / 'resources.ap_', work / 'compiled.zip'])
    with zipfile.ZipFile(work / 'resources.ap_') as resources, zipfile.ZipFile(work / 'unsigned.apk', 'w') as out:
        for item in resources.infolist():
            out.writestr(item, resources.read(item.filename))
        out.write(dex / 'classes.dex', 'classes.dex', compress_type=zipfile.ZIP_STORED)
        for path in sorted((source / 'assets').rglob('*')):
            if path.is_file():
                out.write(path, 'assets/' + str(path.relative_to(source / 'assets')))
    run([align, '-f', '-p', '4', work / 'unsigned.apk', work / 'aligned.apk'])
    apk = build / 'pi-console-compat-test.apk'
    run([*signer, 'sign', '--ks', key, '--ks-key-alias', 'pi-console-debug',
         '--ks-pass', 'pass:android', '--out', apk, work / 'aligned.apk'])
    certificates = []
    for artifact in (app, apk):
        output = run([*signer, 'verify', '--verbose', '--print-certs', artifact], capture=True)
        found = re.findall(r'Signer #\d+ certificate SHA-256 digest:\s*([a-fA-F0-9]{64})', output)
        if len(found) != 1:
            raise ValueError('Expected one development signer')
        certificates.append(found[0].lower())
        run([align, '-c', '-p', '4', artifact])
        verify_resource_table(artifact)
    if certificates[0] != certificates[1]:
        raise ValueError('App and instrumentation development signers differ')
    metadata = {'app': str(app), 'test': str(apk), 'development_signing': True,
                'app_sha256': hashlib.sha256(app.read_bytes()).hexdigest(),
                'test_sha256': hashlib.sha256(apk.read_bytes()).hexdigest()}
    (work / 'artifacts.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
