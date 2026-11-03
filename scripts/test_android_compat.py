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


def effective_display_size(output):
    sizes = re.findall(r'^(Physical|Override) size:\s*(\d+)x(\d+)\s*$', output, re.M)
    if not sizes:
        raise ValueError('Missing window-manager display size')
    selected = next((size for size in reversed(sizes) if size[0] == 'Override'), sizes[-1])
    return [int(selected[1]), int(selected[2])]


def verify_display_report(report, expected):
    if report.get('full_ui_tested'):
        portrait = next((row for row in report['scenarios'] if row.get('name') == 'fullscreen-portrait-2560'), None)
        if not portrait or sorted(portrait['native']['window']) != sorted(expected):
            raise ValueError('App fullscreen window does not match requested display size')


def summarize_process_crash(crash, exit_info):
    # Export identifiers/codes only, never exception messages, URLs or payloads.
    def unique(values, limit):
        return list(dict.fromkeys(values))[:limit]
    return {
        'exit_reason_codes': unique([int(v) for v in re.findall(r'\breason=(\d+)', exit_info)], 8),
        'exit_status_codes': unique([int(v) for v in re.findall(r'\bstatus=(\d+)', exit_info)], 8),
        'signals': [{'number': int(n), 'name': name} for n, name in
                    unique(re.findall(r'Fatal signal (\d+) \((SIG[A-Z0-9]+)\)', crash), 8)],
        'exception_classes': unique(re.findall(r'\b((?:java\.lang|java\.util|android(?:\.[A-Za-z0-9_$]+)+|dev\.piconsole)\.[A-Za-z0-9_$]*(?:Error|Exception))\b', crash), 16),
        'java_frames': unique(re.findall(r'\bat ((?:dev\.piconsole|android|java|org\.chromium)\.[A-Za-z0-9_.$]+)\(', crash), 24),
        'native_libraries': unique(re.findall(r'/(lib[A-Za-z0-9_-]{1,80}\.so)\b', crash), 16),
        'unhandled_renderer_exit': "crash wasn't handled" in crash.lower(),
        'jni_fatal': 'JNI DETECTED ERROR IN APPLICATION' in crash,
    }


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
    parser.add_argument('--display-size', help='Required effective emulator size, for example 1080x2400')
    parser.add_argument('--gesture-back', action='store_true', help='Require active system gesture navigation and test actual edge swipes')
    args = parser.parse_args()
    if args.display_size and not re.fullmatch(r'[1-9][0-9]{2,3}x[1-9][0-9]{2,3}', args.display_size):
        parser.error('Invalid --display-size')
    expected_size = [int(n) for n in args.display_size.split('x')] if args.display_size else None
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
    display_evidence = {'requested_display_size': expected_size}
    restore_tutorial = None

    def device(*command, timeout=60):
        return subprocess.run([adb, '-s', args.serial, *command], check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, timeout=timeout).stdout

    try:
        require_emulator(device('shell', 'getprop', 'ro.kernel.qemu'))
        display_evidence['display_size_before_install'] = device('shell', 'wm', 'size').strip()
        # Always fresh source builds; --reuse-debug exists only on the compile-only builder.
        subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_android_compat.py')], check=True)
        artifacts = json.loads((ROOT / 'build/android-compat/artifacts.json').read_text())
        for name in ('app', 'test'):
            verify_artifact(Path(artifacts[name]), artifacts[name + '_sha256'])
            if 'Success' not in device('install', '-r', '-t', artifacts[name]):
                raise ValueError('Development APK install did not report success')
        if 'Success' not in device('shell', 'pm', 'clear', 'dev.piconsole'):
            raise ValueError('Could not reset emulator app data for offline first launch')
        power = device('shell', 'dumpsys', 'power')
        wake = re.search(r'mWakefulness=(Awake|Asleep|Dreaming|Dozing)\b', power)
        display_evidence['wakefulness_before_launch'] = wake.group(1) if wake else 'unknown'
        device('shell', 'input', 'keyevent', 'KEYCODE_WAKEUP')
        device('shell', 'wm', 'dismiss-keyguard')
        # Match AOSP CTS's immersive tests: finish the OS first-use tutorial
        # before testing app input. A focused tutorial otherwise consumes Back.
        previous = device('shell', 'settings', 'get', 'secure', 'immersive_mode_confirmations').strip()
        if previous not in ('null', 'confirmed'):
            raise ValueError('Unexpected emulator immersive confirmation setting')
        restore_tutorial = previous
        device('shell', 'settings', 'put', 'secure', 'immersive_mode_confirmations', 'confirmed')
        if device('shell', 'settings', 'get', 'secure', 'immersive_mode_confirmations').strip() != 'confirmed':
            raise ValueError('Could not prepare emulator immersive confirmation')
        display_evidence['immersive_tutorial_preconfirmed'] = True
        display_evidence['display_size_before_instrumentation'] = device('shell', 'wm', 'size').strip()
        print(json.dumps(display_evidence), flush=True)
        if expected_size and effective_display_size(display_evidence['display_size_before_instrumentation']) != expected_size:
            raise ValueError('Window-manager size override did not take effect')
        instrument = ['shell', 'am', 'instrument', '-w', '-r']
        if args.gesture_back:
            mode = device('shell', 'settings', 'get', 'secure', 'navigation_mode').strip()
            display_evidence['navigation_mode'] = mode
            if mode != '2':
                raise ValueError('System gesture navigation is not active')
            instrument += ['-e', 'gestureBack', 'true']
        instrument += ['dev.piconsole.compat/dev.piconsole.compat.CompatInstrumentation']
        output = device(*instrument, timeout=240)
        (output_dir / 'instrumentation.log').write_text(output)
        report = parse_instrumentation(output, require_full_ui=args.require_full_ui)
        if args.gesture_back and (not report.get('controlsBackNavigation') or report.get('backInput') != 'system-gesture'):
            raise ValueError('Missing actual system-gesture Back coverage')
        report.update(display_evidence)
        if expected_size:
            verify_display_report(report, expected_size)
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
        if 'Process crashed' in output:
            # This runs only after the emulator guard and fresh app-data reset.
            # The raw buffers stay in memory and are discarded after parsing.
            crash, exit_info = '', ''
            try:
                crash = device('shell', 'logcat', '-b', 'crash', '-d', '-t', '160', timeout=10)
                crash += device('shell', 'logcat', '-b', 'main', '-d', '-t', '120', '-s',
                                'AndroidRuntime:E', 'chromium:E', 'cr_AwContents:E', 'libc:F', 'DEBUG:F', '*:S', timeout=10)
                exit_info = device('shell', 'dumpsys', 'activity', 'exit-info', 'dev.piconsole', timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
            failure_report['process_crash'] = summarize_process_crash(crash, exit_info)
        failure_report.update(display_evidence)
        failure_report.update({'passed': False, 'label': args.label, 'runner_failure': str(error)[:1000]})
        (output_dir / 'report.json').write_text(json.dumps(failure_report, indent=2) + '\n')
        raise SystemExit('Android compatibility failed: ' + str(error)) from None
    finally:
        if restore_tutorial is not None:
            restored = False
            try:
                if restore_tutorial == 'null':
                    device('shell', 'settings', 'delete', 'secure', 'immersive_mode_confirmations')
                else:
                    device('shell', 'settings', 'put', 'secure', 'immersive_mode_confirmations', 'confirmed')
                restored = device('shell', 'settings', 'get', 'secure', 'immersive_mode_confirmations').strip() == restore_tutorial
            except (OSError, subprocess.SubprocessError):
                pass
            report_path = output_dir / 'report.json'
            if report_path.is_file():
                final_report = json.loads(report_path.read_text())
                final_report['immersive_tutorial_setting_restored'] = restored
                if not restored:
                    final_report.update(passed=False, runner_failure='Emulator immersive confirmation was not restored')
                report_path.write_text(json.dumps(final_report, indent=2) + '\n')
            if not restored:
                raise SystemExit('Could not restore emulator immersive confirmation')


if __name__ == '__main__':
    main()
