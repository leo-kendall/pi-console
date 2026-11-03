# SPDX-License-Identifier: Apache-2.0
"""Host-side failure boundaries; real Android execution belongs to emulator CI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CompatibilityHarnessTests(unittest.TestCase):
    def runner(self):
        path = ROOT / 'scripts/test_android_compat.py'
        self.assertTrue(path.is_file(), 'Missing real-device instrumentation runner')
        spec = importlib.util.spec_from_file_location('compat_runner', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_success_requires_explicit_runner_result_and_passed_report(self):
        runner = self.runner()
        report = {'passed': True, 'sdk': 35, 'scenarios': [{'name': 'portrait'}]}
        output = ('INSTRUMENTATION_RESULT: compat_success=true\n'
                  'INSTRUMENTATION_RESULT: compat_report=' + json.dumps(report) + '\n'
                  'INSTRUMENTATION_CODE: -1\n')
        self.assertEqual(runner.parse_instrumentation(output), report)
        for bad in ('', 'INSTRUMENTATION_CODE: -1\n',
                    output.replace('compat_success=true', 'compat_success=false'),
                    output.replace('INSTRUMENTATION_CODE: -1', 'INSTRUMENTATION_CODE: 0'),
                    output.replace('"passed": true', '"passed": false'),
                    output + 'INSTRUMENTATION_FAILED: process crashed\n',
                    output.replace(json.dumps(report), '{bad json}')):
            with self.subTest(output=bad), self.assertRaises(ValueError):
                runner.parse_instrumentation(bad)

    def test_display_size_requires_actual_override_and_fullscreen_window(self):
        runner = self.runner()
        self.assertEqual(runner.effective_display_size('Physical size: 1080x1920\nOverride size: 1080x2400\n'), [1080,2400])
        self.assertEqual(runner.effective_display_size('Physical size: 1080x1920\n'), [1080,1920])
        with self.assertRaises(ValueError):
            runner.effective_display_size('Error: unavailable')
        report = {'full_ui_tested': True, 'scenarios': [{'name':'fullscreen-portrait-2560', 'native':{'window':[1080,1920]}}]}
        with self.assertRaises(ValueError):
            runner.verify_display_report(report, [1080,2400])
        runner.verify_display_report(report, [1080,1920])

    def test_crash_summary_keeps_fixed_diagnostics_without_private_messages(self):
        runner = self.runner()
        raw = ("Fatal signal 11 (SIGSEGV) in tid 123\n"
               "java.lang.IllegalStateException: PRIVATE_VALUE https://private.invalid/token\n"
               " at dev.piconsole.MainActivity.onCreate(MainActivity.java:44)\n"
               " #00 pc 1234 /apex/runtime/lib64/libwebview.so (function)\n"
               "Render process crash wasn't handled\nreason=5 (CRASH_NATIVE) status=11\n")
        report = runner.summarize_process_crash(raw, raw)
        self.assertEqual(report['exit_reason_codes'], [5])
        self.assertEqual(report['signals'], [{'number':11,'name':'SIGSEGV'}])
        self.assertIn('dev.piconsole.MainActivity.onCreate', report['java_frames'])
        self.assertIn('libwebview.so', report['native_libraries'])
        self.assertTrue(report['unhandled_renderer_exit'])
        self.assertNotIn('PRIVATE_VALUE', json.dumps(report))
        self.assertNotIn('https:', json.dumps(report))
        self.assertLess(len(report['java_frames']), 25)

    def test_runner_without_run_flag_never_installs(self):
        self.runner()
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/test_android_compat.py')],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--run', result.stderr)

    def test_gesture_diagnostics_keep_state_without_systemui_content(self):
        runner = self.runner()
        raw = ('PRIVATE_HEADER https://private.invalid/\nEdgeBackGestureHandler:\n'
               ' mIsEnabled=true\n mIsBackGestureAllowed=false\n mIsButtonForcedVisible=true\n'
               ' mEdgeWidthLeft=45\n mPackageName=PRIVATE_APP\n mRecentGesture=PRIVATE_INPUT\n'
               ' mGestureLogInsideInsets=Gesture [123 [00:00],alw=FALSE, left=TRUE,disbld=TRUE,excl=PRIVATE_EXCLUSION]\n')
        result = runner.summarize_gesture_handler(raw)
        self.assertTrue(result['handler_dump_found'])
        self.assertFalse(result['mIsBackGestureAllowed'])
        self.assertTrue(result['mIsButtonForcedVisible'])
        self.assertEqual(result['mEdgeWidthLeft'], 45)
        self.assertEqual(result['gesture_down_events'], [{'alw': False, 'left': True, 'disbld': True}])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('https:', json.dumps(result))
        self.assertEqual(runner.summarize_gesture_handler('unavailable'), {'handler_dump_found': False})

    def test_full_ui_requirement_rejects_recovery_only_result(self):
        runner = self.runner()
        report = {'passed': True, 'result_kind': 'requires-webview-update',
                  'full_ui_tested': False, 'recovery_ui_tested': True,
                  'scenarios': [{'name': 'native-webview-update-recovery'}]}
        output = ('INSTRUMENTATION_RESULT: compat_success=true\n'
                  'INSTRUMENTATION_RESULT: compat_report=' + json.dumps(report) + '\n'
                  'INSTRUMENTATION_CODE: -1\n')
        self.assertEqual(runner.parse_instrumentation(output), report)
        with self.assertRaises(ValueError):
            runner.parse_instrumentation(output, require_full_ui=True)

    def test_emulator_guard_rejects_physical_devices(self):
        runner = self.runner()
        self.assertEqual(runner.require_emulator('1\r\n'), None)
        for physical in ('0', '', 'true'):
            with self.assertRaises(ValueError):
                runner.require_emulator(physical)

    def test_artifacts_reject_modified_apk(self):
        runner = self.runner()
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            apk = Path(temporary) / 'dev.apk'
            apk.write_bytes(b'abc')
            runner.verify_artifact(apk, 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
            apk.write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                runner.verify_artifact(apk, 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')


if __name__ == '__main__':
    unittest.main()
