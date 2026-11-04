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
import shlex
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


def summarize_gesture_handler(raw):
    # Retain only fixed state names and Boolean/numeric values, never window
    # titles, activity names, recent input payloads or the raw SystemUI dump.
    start = raw.find('EdgeBackGestureHandler:')
    result = {'handler_dump_found': start >= 0}
    if start < 0:
        return result
    section = raw[start:start + 5000]
    for key in ('mIsEnabled', 'mIsAttached', 'mIsBackGestureAllowed', 'mIsGesturalModeEnabled',
                'mIsNavBarShownTransiently', 'mGestureBlockingActivityRunning', 'mAllowGesture',
                'mDisabledForQuickstep', 'mInRejectedExclusion', 'mIsInPip', 'mUsingThreeButtonNav',
                'mIsButtonForcedVisible', 'mInGestureNavMode', 'mIsGestureHandlingEnabled'):
        value = re.search(r'\b' + key + r'=\s*(true|false)\b', section)
        if value:
            result[key] = value.group(1) == 'true'
    for key in ('mEdgeWidthLeft', 'mEdgeWidthRight', 'mLeftInset', 'mRightInset', 'mLongPressTimeout'):
        value = re.search(r'\b' + key + r'=\s*(\d{1,6})\b', section)
        if value:
            result[key] = int(value.group(1))
    events = []
    for line in re.findall(r'Gesture \[[^\r\n]{0,1500}', section)[-6:]:
        event = {}
        for key in ('alw', 'left', 'backAlw', 'disbld', 'qsDisbld', 'blkdAct', 'pip'):
            value = re.search(r'\b' + key + r'=\s*(true|false)\b', line, re.I)
            if value:
                event[key] = value.group(1).lower() == 'true'
        if event:
            events.append(event)
    result['gesture_down_events'] = events
    return result


def require_emulator(qemu):
    if qemu.strip() != '1':
        raise ValueError('Refusing app installation/data clearing on a non-emulator device')


def verify_artifact(path, expected):
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Missing or modified development APK')


def clean_revision():
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True)
    if status or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Installed APK reuse requires an unchanged clean source revision')
    return revision


def verify_installed_artifact(device, package, expected):
    listing = device('shell', 'pm', 'path', package).strip().splitlines()
    if len(listing) != 1 or not listing[0].startswith('package:'):
        raise ValueError('Expected one installed development base APK')
    path = listing[0][8:]
    if not re.fullmatch(r'/data/app/[A-Za-z0-9_./=~+\-]+/base\.apk', path):
        raise ValueError('Invalid installed development APK path')
    checksum = device('shell', 'sha256sum', shlex.quote(path)).split()
    if not checksum or checksum[0] != expected:
        raise ValueError('Installed development APK does not match source-bound artifact')


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
    parser.add_argument('--reuse-installed', action='store_true',
                        help='Reuse source-bound development APKs after verifying clean revision and installed hashes')
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
    restore_user_setup = None

    def device(*command, timeout=60):
        return subprocess.run([adb, '-s', args.serial, *command], check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, timeout=timeout).stdout

    try:
        require_emulator(device('shell', 'getprop', 'ro.kernel.qemu'))
        display_evidence['display_size_before_install'] = device('shell', 'wm', 'size').strip()
        binding_path = ROOT / 'build/android-compat-installed.json'
        revision = None
        if args.reuse_installed:
            binding = json.loads(binding_path.read_text())
            revision = clean_revision()
            if binding.get('revision') != revision or binding.get('serial') != args.serial:
                raise ValueError('Installed development APK source/device binding changed')
        else:
            binding_path.unlink(missing_ok=True)
            try:
                revision = clean_revision()
            except (ValueError, OSError, subprocess.SubprocessError):
                pass  # A fresh one-off local build can also exercise edited sources.
            subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_android_compat.py')], check=True)
        artifacts = json.loads((ROOT / 'build/android-compat/artifacts.json').read_text())
        for name in ('app', 'test'):
            verify_artifact(Path(artifacts[name]), artifacts[name + '_sha256'])
            if args.reuse_installed:
                if binding.get(name + '_sha256') != artifacts[name + '_sha256']:
                    raise ValueError('Development APK binding hash changed')
            elif 'Success' not in device('install', '-r', '-t', artifacts[name]):
                raise ValueError('Development APK install did not report success')
            verify_installed_artifact(device, 'dev.piconsole' if name == 'app' else 'dev.piconsole.compat', artifacts[name + '_sha256'])
        if revision is not None:
            if clean_revision() != revision:
                raise ValueError('Source revision changed during development APK preparation')
            binding_path.write_text(json.dumps({'revision': revision, 'serial': args.serial,
                'app_sha256': artifacts['app_sha256'], 'test_sha256': artifacts['test_sha256']}) + '\n')
        display_evidence['reused_installed_artifacts'] = args.reuse_installed
        if 'Success' not in device('shell', 'pm', 'clear', 'dev.piconsole'):
            raise ValueError('Could not reset emulator app data for offline first launch')
        power = device('shell', 'dumpsys', 'power')
        wake = re.search(r'mWakefulness=(Awake|Asleep|Dreaming|Dozing)\b', power)
        display_evidence['wakefulness_before_launch'] = wake.group(1) if wake else 'unknown'
        device('shell', 'input', 'keyevent', 'KEYCODE_WAKEUP')
        device('shell', 'wm', 'dismiss-keyguard')
        # Match AOSP CTS's immersive tests: finish the OS first-use tutorial
        # before testing app input. A focused tutorial otherwise consumes Back.
        previous = device('shell', 'settings', 'get', 'secure', 'immersive_mode_confirmations').rstrip('\r\n')
        if len(previous) > 1024 or any(c in previous for c in '\0\r\n'):
            raise ValueError('Invalid emulator immersive confirmation setting')
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
            # SystemUI blocks edge Back until device setup is complete, even
            # when the gestural navigation overlay reports mode 2.
            previous_setup = device('shell', 'settings', 'get', 'secure', 'user_setup_complete').strip()
            if previous_setup not in ('null', '0', '1'):
                raise ValueError('Invalid emulator user setup state')
            restore_user_setup = previous_setup
            display_evidence['user_setup_complete_before_gesture'] = int(previous_setup) if previous_setup != 'null' else None
            device('shell', 'settings', 'put', 'secure', 'user_setup_complete', '1')
            if device('shell', 'settings', 'get', 'secure', 'user_setup_complete').strip() != '1':
                raise ValueError('Emulator device setup did not complete')
            display_evidence['user_setup_complete_for_gesture'] = True
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
        if args.gesture_back and restore_tutorial is not None:
            gesture = {}
            try:
                raw = device('shell', 'dumpsys', 'activity', 'service', 'com.android.systemui/.SystemUIService', timeout=20)
                gesture.update(summarize_gesture_handler(raw))
                for namespace, key in [('secure', 'user_setup_complete'), ('global', 'device_provisioned'),
                                       ('secure', 'navigation_mode'), ('secure', 'touch_exploration_enabled')]:
                    value = device('shell', 'settings', 'get', namespace, key).strip()
                    gesture[key] = int(value) if value in ('0', '1', '2') else None
            except (OSError, subprocess.SubprocessError):
                gesture['diagnostic_unavailable'] = True
            failure_report['system_gesture_state'] = gesture
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
        restoration = {}
        failed_restoration = []
        for key, previous, field in (
                ('user_setup_complete', restore_user_setup, 'user_setup_setting_restored'),
                ('immersive_mode_confirmations', restore_tutorial, 'immersive_tutorial_setting_restored')):
            if previous is None:
                continue
            restored = False
            try:
                if previous == 'null':
                    device('shell', 'settings', 'delete', 'secure', key)
                else:
                    # adb shell joins arguments into a command: preserve empty
                    # and customized values with actual shell quoting.
                    device('shell', 'settings', 'put', 'secure', key, shlex.quote(previous))
                restored = device('shell', 'settings', 'get', 'secure', key).rstrip('\r\n') == previous
            except (OSError, subprocess.SubprocessError):
                pass
            restoration[field] = restored
            if not restored:
                failed_restoration.append(key)
        report_path = output_dir / 'report.json'
        if restoration and report_path.is_file():
            final_report = json.loads(report_path.read_text())
            final_report.update(restoration)
            if failed_restoration:
                final_report.update(passed=False, runner_failure='Emulator test settings were not restored')
            report_path.write_text(json.dumps(final_report, indent=2) + '\n')
        if failed_restoration:
            raise SystemExit('Could not restore emulator test settings')


if __name__ == '__main__':
    main()
