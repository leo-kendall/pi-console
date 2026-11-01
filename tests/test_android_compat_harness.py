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

    def test_runner_without_run_flag_never_installs(self):
        self.runner()
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/test_android_compat.py')],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--run', result.stderr)

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
