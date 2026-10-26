# SPDX-License-Identifier: Apache-2.0
"""Exercise installer orchestration with real temporary files and fake OS commands."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import base64
from unittest.mock import patch


class FakeCommands:
    def __init__(self, fail_stop=False):
        self.calls = []
        self.fail_stop = fail_stop
        self.inputs = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        self.inputs.append(kwargs.get("input"))
        if self.fail_stop and args[1:3] == ["stop", "gnome-remote-desktop.service"]:
            raise subprocess.CalledProcessError(1, args)
        out = ""
        if Path(args[0]).name == "systemctl" and args[1] == "show":
            out = "ActiveState=inactive\nUnitFileState=disabled\n"
        if Path(args[0]).name == "nft" and "list" in args:
            out = '{"nftables": []}'
        return subprocess.CompletedProcess(args, 0, out, "")


class ManageTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).with_name("manage.py")
        self.assertTrue(source.exists(), "RDP lifecycle implementation is missing")
        spec = importlib.util.spec_from_file_location("rdp_manage", source)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fake = FakeCommands()
        self.m = self.mod.Manager(self.root / "system", self.root / "project", self.fake)
        self.m.state_dir.mkdir(parents=True, mode=0o700)
        self.m.config.parent.mkdir(parents=True)
        self.m.config.write_bytes(b"managed")
        self.record = {"version": 1, "phase": "installed", "files": {
            str(self.m.config): [self.mod.safety.sha(b"managed")]},
            "dirs": [], "ufw_added": False, "nft_signature": None,
            "credential_hashes": {}, "credential_pending": False}
        self.mod.safety.save_json(self.m.state, self.record)

    def test_stop_failure_retains_configuration_and_recovery_record(self):
        self.fake.fail_stop = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.m.uninstall()
        self.assertEqual(self.m.config.read_bytes(), b"managed")
        self.assertTrue(self.m.state.exists())
        self.assertFalse(any("delete" in a and "pi_console_rdp" in a for a in self.fake.calls))

    def test_external_config_change_aborts_without_system_changes(self):
        self.m.config.write_bytes(b"changed externally")
        with self.assertRaises(RuntimeError):
            self.m.uninstall()
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.m.config.read_bytes(), b"changed externally")

    def test_cleanup_stops_desktop_before_removing_guard_and_files(self):
        self.m.uninstall()
        self.assertFalse(self.m.config.exists())
        self.assertFalse(self.m.state_dir.exists())
        stops = [a[2] for a in self.fake.calls if a[1] == "stop"]
        self.assertLess(stops.index("gnome-remote-desktop.service"),
                        stops.index("pi-console-rdp-guard.service"))
        self.assertFalse(any("reboot" in a or "terminate-session" in a for a in self.fake.calls))

    def test_missing_managed_file_can_be_cleaned_on_retry(self):
        self.m.config.unlink()
        self.record["phase"] = "removing"
        self.mod.safety.save_json(self.m.state, self.record)
        self.m.uninstall()
        self.assertFalse(self.m.state_dir.exists())

    def test_credential_command_sends_secret_only_on_stdin(self):
        self.m.set_credentials("pi-console", "private-value")
        self.assertEqual(self.fake.inputs, ["private-value\n"])
        self.assertEqual(self.fake.calls[0][-4:], ["/usr/bin/grdctl", "rdp", "set-credentials", "pi-console"])
        self.assertFalse(any("private-value" in arg for call in self.fake.calls for arg in call))

    @unittest.skipUnless(Path("/usr/bin/grdctl").exists(), "requires local GNOME grdctl")
    def test_real_grdctl_accepts_installer_credential_input(self):
        # Exercise actual parsing in an isolated file-backed headless profile.
        # No system account, daemon, port or existing desktop settings are used.
        import resource
        profile = self.root / "grd-profile"
        profile.mkdir()
        env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "HOME": str(profile),
               "XDG_DATA_HOME": str(profile / "data"),
               "XDG_CONFIG_HOME": str(profile / "config"),
               "XDG_CACHE_HOME": str(profile / "cache"), "GSETTINGS_BACKEND": "memory"}
        def actual_parser(args, **kwargs):
            start = args.index("/usr/bin/grdctl")
            return subprocess.run(["/usr/bin/grdctl", "--headless", *args[start + 1:]],
                                  input=kwargs["input"], text=True, capture_output=True,
                                  check=True, timeout=20, env=env,
                                  preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
        self.m.run = actual_parser
        self.m.set_credentials("diagnostic-user", "diagnostic-password")
        stored = (profile / "data/gnome-remote-desktop/credentials.ini").read_text()
        self.assertIn("diagnostic-user", stored)
        self.assertIn("diagnostic-password", stored)

    def test_private_data_removal_preserves_foreign_target_of_symlink(self):
        self.m.data.mkdir(parents=True)
        (self.m.data / ".owner").write_text("test-marker")
        outside = self.root / "keep"
        outside.write_text("keep me")
        (self.m.data / "link").symlink_to(outside)
        self.record["marker"] = "test-marker"
        self.mod.safety.save_json(self.m.state, self.record)
        self.m.uninstall()
        self.assertEqual(outside.read_text(), "keep me")
        self.assertFalse(self.m.data.exists())

    def test_interrupted_owner_write_can_be_removed(self):
        self.m.data.mkdir(parents=True)
        marker = self.m.data / ".owner"
        marker.write_bytes(b"test-")
        self.record.update(phase="installing", marker="test-marker",
                           contents={str(marker): base64.b64encode(b"test-marker").decode()})
        self.record["files"][str(marker)] = [self.mod.safety.sha(b"test-marker")]
        self.mod.safety.save_json(self.m.state, self.record)
        self.m.uninstall()
        self.assertFalse(self.m.data.exists())

    def test_credential_crash_partial_data_can_be_cleaned(self):
        self.m.data.mkdir(parents=True)
        (self.m.data / ".owner").write_text("test-marker")
        credentials = self.m.data / "data/gnome-remote-desktop/credentials.ini"
        credentials.parent.mkdir(parents=True)
        credentials.write_text("")
        self.record.update(phase="installing", marker="test-marker", credential_pending=True)
        self.mod.safety.save_json(self.m.state, self.record)
        self.m.uninstall()
        self.assertFalse(self.m.data.exists())
        self.assertFalse(self.m.state_dir.exists())

    def test_empty_state_directory_after_final_interruption_can_be_removed(self):
        self.m.config.unlink()
        self.m.state.unlink()
        self.m.uninstall()
        self.assertFalse(self.m.state_dir.exists())

    def test_missing_state_with_remaining_resource_is_refused(self):
        self.m.state.unlink()
        with self.assertRaises(RuntimeError):
            self.m.uninstall()
        self.assertTrue(self.m.config.exists())

    def test_final_directory_failure_restores_recovery_record(self):
        original = Path.rmdir
        def fail_final(path):
            if path == self.m.state_dir:
                raise OSError("simulated rmdir failure")
            return original(path)
        with patch.object(Path, "rmdir", fail_final):
            with self.assertRaises(OSError):
                self.m.uninstall()
        self.assertTrue(self.m.state.exists())
        self.m.uninstall()
        self.assertFalse(self.m.state_dir.exists())


if __name__ == "__main__":
    unittest.main()
