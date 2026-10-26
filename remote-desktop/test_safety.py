# SPDX-License-Identifier: Apache-2.0
"""Offline tests: no system command, service or firewall is changed."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).with_name("safety.py")


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), "remote desktop safety implementation is missing")
        spec = importlib.util.spec_from_file_location("rdp_safety", MODULE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_refuse_existing_config_and_active_service(self):
        for change in ({"configured": True}, {"active": True}, {"enabled": True},
                       {"port_busy": True}, {"credentials_present": True}):
            values = dict(configured=False, active=False, enabled=False,
                          port_busy=False, credentials_present=False)
            values.update(change)
            with self.assertRaises(RuntimeError):
                self.m.check_baseline(**values)

    def test_empty_baseline_is_accepted(self):
        self.m.check_baseline(False, False, False, False, False)

    def test_atomic_state_survives_serialization_failure(self):
        path = self.root / "state.json"
        self.m.save_json(path, {"phase": "installing"})
        with self.assertRaises(TypeError):
            self.m.save_json(path, {"bad": object()})
        self.assertEqual(path.read_text().strip(), '{"phase": "installing"}')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_symlink_parent_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "link").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.m.safe_path(self.root / "link" / "file")
        self.assertEqual(list(outside.iterdir()), [])

    def test_modified_owned_file_is_preserved(self):
        path = self.root / "owned"
        path.write_bytes(b"external edit")
        with self.assertRaises(RuntimeError):
            self.m.remove_owned(path, [self.m.sha(b"original")])
        self.assertEqual(path.read_bytes(), b"external edit")

    def test_owned_file_removal_is_retryable(self):
        path = self.root / "owned"
        path.write_bytes(b"original")
        for _ in range(2):
            self.m.remove_owned(path, [self.m.sha(b"original")])
        self.assertFalse(path.exists())

    def test_rule_signature_ignores_packet_counts_but_not_port(self):
        a = {"nftables": [{"metainfo": {"version": "1"}}, {"rule": {
            "expr": [{"counter": {"packets": 0, "bytes": 0}},
                     {"match": {"right": 3389}}]}}]}
        b = {"nftables": [{"metainfo": {"version": "2"}}, {"rule": {
            "expr": [{"counter": {"packets": 9, "bytes": 90}},
                     {"match": {"right": 3389}}]}}]}
        self.assertEqual(self.m.nft_signature(a), self.m.nft_signature(b))
        b["nftables"][1]["rule"]["expr"][1]["match"]["right"] = 22
        self.assertNotEqual(self.m.nft_signature(a), self.m.nft_signature(b))


if __name__ == "__main__":
    unittest.main()
