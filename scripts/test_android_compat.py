#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build and run the actual Android app in an explicitly selected emulator.

Requires --run; clears the emulator's dev.piconsole app data for an offline first
launch. Never accepts a physical device. Saves aggregate reports, no screenshots.
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

ROOT = Path(__file__).resolve().parents[1]


def parse_instrumentation(output, require_full_ui=False):
    if re.search(r'INSTRUMENTATION_(?:FAILED|ABORTED)', output):
        raise ValueError('Instrumentation failed or aborted')
    codes = re.findall(r'^INSTRUMENTATION_CODE:\s*(-?\d+)\s*$', output, re.M)
    fields = dict(re.findall(r'^INSTRUMENTATION_RESULT: ([a-z_]+)=(.*)$', output, re.M))
    if codes != ['-1'] or fields.get('compat_success', '').strip() != 'true':
        raise ValueError('Missing explicit successful instrumentation completion')
    try:
        report = json.loads(fields['compat_report'])
    except (KeyError, ValueError):
        raise ValueError('Missing valid compatibility report') from None
    if not isinstance(report, dict) or report.get('passed') is not True or not report.get('scenarios'):
        raise ValueError('Instrumentation report did not pass scenarios')
    if require_full_ui and report.get('full_ui_tested') is not True:
        raise ValueError('Full WebView UI coverage required; only recovery UI was exercised')
    return report


def require_emulator(qemu):
    if qemu.strip() != '1':
        raise ValueError('Refusing app installation/data clearing on a non-emulator device')


def verify_artifact(path, expected):
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Missing or modified development APK')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', required=True,
                        help='Authorize installation and fresh app-data reset in the selected emulator')
    parser.add_argument('--serial', default=os.environ.get('ANDROID_SERIAL'))
    parser.add_argument('--label', default='default')
    parser.add_argument('--require-full-ui', action='store_true',
                        help='Fail if an outdated WebView only exercises the native update recovery UI')
    args = parser.parse_args()
    if not args.serial:
        parser.error('--serial or ANDROID_SERIAL must identify the emulator')
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}', args.label):
        parser.error('--label must contain 1-80 letters, digits, dots, underscores or hyphens')
    sdk = Path(os.environ.get('ANDROID_HOME', os.environ.get('ANDROID_SDK_ROOT', '/nonexistent')))
    adb = str(sdk / 'platform-tools/adb') if (sdk / 'platform-tools/adb').is_file() else shutil.which('adb')
    if not adb:
        parser.error('adb not found in Android SDK or PATH')
    output_dir = ROOT / 'build/compatibility' / args.label
    output_dir.mkdir(parents=True, exist_ok=True)
    output = ''

    def device(*command, timeout=60):
        return subprocess.run([adb, '-s', args.serial, *command], check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, timeout=timeout).stdout

    try:
        require_emulator(device('shell', 'getprop', 'ro.kernel.qemu'))
        # Always fresh source builds; --reuse-debug exists only on the compile-only builder.
        subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_android_compat.py')], check=True)
        artifacts = json.loads((ROOT / 'build/android-compat/artifacts.json').read_text())
        for name in ('app', 'test'):
            verify_artifact(Path(artifacts[name]), artifacts[name + '_sha256'])
            if 'Success' not in device('install', '-r', '-t', artifacts[name]):
                raise ValueError('Development APK install did not report success')
        if 'Success' not in device('shell', 'pm', 'clear', 'dev.piconsole'):
            raise ValueError('Could not reset emulator app data for offline first launch')
        output = device('shell', 'am', 'instrument', '-w', '-r',
                        'dev.piconsole.compat/dev.piconsole.compat.CompatInstrumentation', timeout=240)
        (output_dir / 'instrumentation.log').write_text(output)
        report = parse_instrumentation(output, require_full_ui=args.require_full_ui)
        report.update({'label': args.label, 'app_sha256': artifacts['app_sha256'],
                       'test_sha256': artifacts['test_sha256']})
        (output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'passed': True, 'result_kind': report.get('result_kind'),
                          'full_ui_tested': report.get('full_ui_tested'),
                          'report': str(output_dir / 'report.json')}))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        captured = getattr(error, 'stdout', None)
        if captured:
            (output_dir / 'instrumentation.log').write_text(captured if isinstance(captured, str) else captured.decode(errors='replace'))
        failure_report = {}
        fields = re.findall(r'^INSTRUMENTATION_RESULT: compat_report=(.*)$', output, re.M)
        if fields:
            try:
                decoded = json.loads(fields[-1])
                if isinstance(decoded, dict):
                    failure_report = decoded
            except ValueError:
                pass
        failure_report.update({'passed': False, 'label': args.label, 'runner_failure': str(error)[:1000]})
        (output_dir / 'report.json').write_text(json.dumps(failure_report, indent=2) + '\n')
        raise SystemExit('Android compatibility failed: ' + str(error)) from None


if __name__ == '__main__':
    main()
