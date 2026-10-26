# SPDX-License-Identifier: Apache-2.0
import tempfile,unittest,subprocess,sys,os
from pathlib import Path
from manage import Installer

class InstallTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);p=Path(self.tmp.name)
  self.root=p/'project';self.root.mkdir();self.home=p/'home';self.home.mkdir();self.calls=[]
  self.installer=Installer(self.root,self.home,lambda args:self.calls.append(args))
 def test_install_remove_preserves_source_and_user_data(self):
  i=self.installer;(self.root/'server.py').write_text('# retained source')
  i.install();self.assertTrue(i.unit.is_file());self.assertTrue(i.enabled.is_symlink())
  (self.root/'data/files').mkdir(parents=True);(self.root/'data/files/photo').write_bytes(b'private')
  i.uninstall();self.assertFalse(i.unit.exists());self.assertFalse(i.enabled.is_symlink())
  self.assertEqual((self.root/'data/files/photo').read_bytes(),b'private');self.assertTrue((self.root/'server.py').exists())
 def test_unowned_unit_is_not_overwritten(self):
  i=self.installer;i.unit.parent.mkdir(parents=True);i.unit.write_text('unrelated')
  with self.assertRaises(RuntimeError):i.install()
  self.assertEqual(i.unit.read_text(),'unrelated');self.assertEqual(self.calls,[])
 def test_changed_link_is_not_removed(self):
  i=self.installer;i.install();i.enabled.unlink();i.enabled.symlink_to('/unrelated')
  with self.assertRaises(RuntimeError):i.uninstall()
  self.assertTrue(i.enabled.is_symlink());self.assertTrue(i.unit.exists())
 def test_purge_rechecks_files_created_during_stop(self):
  i=self.installer;i.install()
  def runner(args):
   if 'stop' in args:(self.root/'data/files').mkdir(parents=True);(self.root/'data/files/important').write_text('keep')
  i.runner=runner
  with self.assertRaises(RuntimeError):i.uninstall(purge=True)
  self.assertEqual((self.root/'data/files/important').read_text(),'keep');self.assertTrue(i.unit.exists())
 def test_empty_runtime_can_be_purged_without_removing_checkout(self):
  i=self.installer;i.install();(self.root/'data/files').mkdir(parents=True)
  i.uninstall(purge=True);self.assertFalse((self.root/'state').exists());self.assertFalse((self.root/'data').exists());self.assertTrue(self.root.exists())
 def test_file_in_place_of_managed_directory_is_preserved(self):
  i=self.installer;i.install();(self.root/'data').mkdir();(self.root/'data/files').write_text('important')
  with self.assertRaises(RuntimeError):i.uninstall(purge=True)
  self.assertEqual((self.root/'data/files').read_text(),'important');self.assertTrue(i.unit.exists())
 def test_unknown_state_file_is_preserved(self):
  i=self.installer;i.install();(self.root/'state/custom-backup').write_text('important')
  with self.assertRaises(RuntimeError):i.uninstall(purge=True)
  self.assertEqual((self.root/'state/custom-backup').read_text(),'important')
 def test_preview_still_works_with_broken_runtime_configuration(self):
  config=self.root/'bad.json';config.write_text('{')
  for script in ('manage.py','uninstall.py'):
   result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve().parents[1]/script)],env={**os.environ,'PI_CONSOLE_CONFIG':str(config)},capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Preview only:',result.stdout)
