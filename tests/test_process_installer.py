# SPDX-License-Identifier: Apache-2.0
"""Filesystem/recovery tests in temporary directories, without touching root paths."""
import contextlib,importlib.util,io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('process_installer',Path(__file__).resolve().parents[1]/'process-control/manage.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class InstallerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name);source=root/'source';(source/'process-control').mkdir(parents=True)
  for name in ['process_identity.py','process_policy.py','process-control/helper.py']:(source/name).write_text('# test source\n')
  self.lib=root/'lib';self.state=root/'state';self.rule=root/'rule';self.helper=root/'helper';self.source=source
  self.patches=[patch.multiple(m,SOURCE=source,LIB=self.lib,STATE=self.state,RECORD=self.state/'state.json',HELPER=self.helper,RULE=self.rule),patch.object(m,'sudo_rule',return_value=b'testuser ALL=(root) NOPASSWD: /test/helper\n'),patch.object(m,'safe',return_value=None),patch.object(m.os,'geteuid',return_value=0),patch.object(m.subprocess,'run')]
  for p in self.patches:p.start();self.addCleanup(p.stop)
 def run_action(self,action):
  with patch.object(sys,'argv',['manage.py',action]),contextlib.redirect_stdout(io.StringIO()):m.main()
 def test_complete_cleanup_does_not_need_original_sources(self):
  self.run_action('install')
  for p in self.source.rglob('*.py'):p.unlink()
  self.run_action('uninstall')
  for p in [self.lib,self.state,self.rule,self.helper]:self.assertFalse(p.exists(),p)
 def test_preexisting_directories_are_retained(self):
  self.lib.mkdir();self.state.mkdir();self.run_action('install');self.run_action('uninstall')
  self.assertTrue(self.lib.is_dir());self.assertTrue(self.state.is_dir());self.assertFalse(list(self.lib.iterdir()));self.assertFalse(list(self.state.iterdir()))
 def test_interrupted_install_can_be_retried_and_cleaned(self):
  original=m.write
  def fail_on_rule(path,data,mode):
   if path==self.rule:raise OSError('simulated interrupted install')
   return original(path,data,mode)
  with patch.object(m,'write',side_effect=fail_on_rule):
   with self.assertRaises(OSError):self.run_action('install')
  self.assertTrue((self.state/'state.json').is_file());self.run_action('install');self.run_action('uninstall');self.assertFalse(self.state.exists())
 def test_unknown_files_are_preserved_and_cleanup_can_be_retried(self):
  self.run_action('install');extra=self.lib/'unrelated.txt';extra.write_text('keep')
  with self.assertRaises(RuntimeError):self.run_action('uninstall')
  self.assertEqual(extra.read_text(),'keep');self.assertFalse(self.rule.exists());self.assertTrue((self.state/'state.json').exists())
  extra.unlink();self.run_action('uninstall');self.assertFalse(self.lib.exists());self.assertFalse(self.state.exists())
 def test_modified_owned_file_is_not_deleted(self):
  self.run_action('install');self.helper.write_text('unrelated replacement')
  with self.assertRaises(RuntimeError):self.run_action('uninstall')
  self.assertEqual(self.helper.read_text(),'unrelated replacement');self.assertTrue(self.rule.exists())
 def test_an_unowned_file_is_never_overwritten(self):
  self.helper.write_text('existing unrelated helper')
  with self.assertRaises(RuntimeError):self.run_action('install')
  self.assertEqual(self.helper.read_text(),'existing unrelated helper');self.assertFalse(self.state.exists())
if __name__=='__main__':unittest.main()
