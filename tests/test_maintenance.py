# SPDX-License-Identifier: Apache-2.0
import hashlib,json,os,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path

class MaintenanceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'console';self.root.mkdir()
  (self.root/'server.py').write_text('VERSION = 1\n');(self.root/'control.py').write_text('ROLE = 1\n')
  (self.root/'config.json').write_text('{"private":"private-fixture-value-712"}')
  (self.root/'data/files').mkdir(parents=True);(self.root/'data/files/photo.txt').write_text('keep-user-data')
 def bundle(self,files=None):
  files=files or {'server.py':b'VERSION = 2\n','control.py':b'ROLE = 2\n'}
  path=Path(self.temp.name)/'source.zip'
  with zipfile.ZipFile(path,'w') as z:
   for name,body in files.items():z.writestr('pi-console/'+name,body)
   z.writestr('pi-console/SOURCE_MANIFEST.sha256','\n'.join(hashlib.sha256(body).hexdigest()+'  '+name for name,body in files.items())+'\n')
  return path
 def maintenance(self):
  from maintenance import Maintenance
  return Maintenance(self.root)
 def test_doctor_and_uninstall_preview_are_readonly_and_never_disclose_secrets(self):
  m=self.maintenance();before=sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*'))
  result=m.doctor();preview=m.uninstall_preview()
  self.assertTrue(result['checks']);self.assertTrue(preview['user_data_retained'])
  self.assertNotIn('private-fixture-value-712',json.dumps(result));self.assertNotIn('keep-user-data',json.dumps(preview))
  self.assertEqual(before,sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')))
 def test_upgrade_preview_does_not_write_and_bad_manifests_or_paths_are_rejected(self):
  m=self.maintenance();self.assertEqual(m.preview(self.bundle())['files'],2)
  self.assertFalse((self.root/'state').exists())
  for name in ['../outside.py','config.json','state/control/auth.json','remote-desktop/connection.json']:
   with self.subTest(name=name),self.assertRaises((ValueError,RuntimeError)):m.preview(self.bundle({name:b'bad'}))
  path=self.bundle()
  with zipfile.ZipFile(path,'a') as z:z.writestr('pi-console/unlisted.py','evil = True')
  with self.assertRaises((ValueError,RuntimeError)):m.preview(path)
 def test_private_backup_upgrade_and_rollback_preserve_configuration_and_user_files(self):
  m=self.maintenance();result=m.upgrade(self.bundle());ident=result['backup']
  self.assertEqual((self.root/'server.py').read_text(),'VERSION = 2\n')
  self.assertEqual((m.directory/'backups'/ident/'private/config.json').read_text(),'{"private":"private-fixture-value-712"}')
  self.assertEqual(os.stat(m.directory/'backups'/ident).st_mode&0o777,0o700)
  self.assertEqual(os.stat(m.directory/'backups'/ident/'private/config.json').st_mode&0o777,0o600)
  m.rollback(ident)
  self.assertEqual((self.root/'server.py').read_text(),'VERSION = 1\n')
  self.assertEqual((self.root/'data/files/photo.txt').read_text(),'keep-user-data')
  self.assertEqual((self.root/'config.json').read_text(),'{"private":"private-fixture-value-712"}')
 def test_failed_restart_restores_old_source_before_restarting_previous_version(self):
  m=self.maintenance();calls=[]
  def runner(action):
   calls.append((action,(self.root/'server.py').read_text()))
   if action=='start' and 'VERSION = 2' in calls[-1][1]:raise RuntimeError('new backend failed health check')
  with self.assertRaises(RuntimeError):m.upgrade(self.bundle(),runner=runner)
  self.assertEqual((self.root/'server.py').read_text(),'VERSION = 1\n')
  self.assertEqual([a for a,_ in calls],['stop','start','stop','start'])
 def test_unhealthy_running_candidate_is_stopped_before_source_rollback(self):
  m=self.maintenance();running={'version':None}
  def runner(action):
   if action=='stop':running['version']=None
   elif running['version'] is None:
    running['version']=(self.root/'server.py').read_text()
    if 'VERSION = 2' in running['version']:raise RuntimeError('health check failed with process still running')
  with self.assertRaises(RuntimeError):m.upgrade(self.bundle(),runner=runner)
  self.assertEqual(running['version'],'VERSION = 1\n')
 def test_rollback_refuses_changed_files_and_symlinked_paths_without_data_loss(self):
  m=self.maintenance();ident=m.upgrade(self.bundle())['backup'];(self.root/'server.py').write_text('USER_EDIT = True\n')
  with self.assertRaises(RuntimeError):m.rollback(ident)
  self.assertEqual((self.root/'server.py').read_text(),'USER_EDIT = True\n')
  (self.root/'server.py').unlink();outside=Path(self.temp.name)/'outside.py';outside.write_text('outside');(self.root/'server.py').symlink_to(outside)
  with self.assertRaises(RuntimeError):m.upgrade(self.bundle())
  self.assertEqual(outside.read_text(),'outside')
 def test_cli_defaults_to_preview_and_doctor_json_is_parseable(self):
  script=Path(__file__).resolve().parents[1]/'maintenance.py'
  run=lambda *args:subprocess.run([sys.executable,'-B',str(script),'--root',str(self.root),*args],capture_output=True,text=True)
  result=run('doctor');self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(result.stdout)['checks'])
  result=run('upgrade',str(self.bundle()));self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual((self.root/'server.py').read_text(),'VERSION = 1\n');self.assertFalse((self.root/'state').exists())
