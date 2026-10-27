# SPDX-License-Identifier: Apache-2.0
import importlib.util,json,tempfile,unittest,subprocess,sys
from pathlib import Path
SCRIPT=Path(__file__).with_name('configure.py')
class ConfigureTests(unittest.TestCase):
 def invoke(self,*args,value=None):return subprocess.run([sys.executable,str(SCRIPT),*args],input=json.dumps(value) if value is not None else '',text=True,capture_output=True)
 def test_preview_redacts_credentials_and_never_writes(self):
  with tempfile.TemporaryDirectory() as t:
   target=Path(t)/'connection.json';r=self.invoke('preview','--output',str(target),value={'protocol':'vnc','password':'SECRET','security':'vnc'})
   self.assertEqual(r.returncode,0,r.stderr);self.assertNotIn('SECRET',r.stdout+r.stderr);self.assertFalse(target.exists());self.assertIn('unchanged',r.stdout)
 def test_configure_private_file_refuses_existing_and_symlink(self):
  with tempfile.TemporaryDirectory() as t:
   target=Path(t)/'connection.json';value={'protocol':'vnc','security':'none'}
   r=self.invoke('configure','--output',str(target),value=value);self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(target.stat().st_mode&0o777,0o600)
   before=target.read_bytes();r=self.invoke('configure','--output',str(target),value={'protocol':'vnc','security':'vnc','password':'SECRET'});self.assertNotEqual(r.returncode,0);self.assertEqual(target.read_bytes(),before);self.assertNotIn('SECRET',r.stdout+r.stderr)
   link=Path(t)/'link';link.symlink_to(target);self.assertNotEqual(self.invoke('configure','--output',str(link),value=value).returncode,0);self.assertEqual(target.read_bytes(),before)
 def test_bad_configs_fail_without_secret_or_mutation(self):
  for value in ({'protocol':'vnc','host':'public.example','password':'SECRET'},{'protocol':'rdp','fingerprint':'SECRET'}, {'protocol':'vnc','security':'tls','password':'SECRET'}):
   with tempfile.TemporaryDirectory() as t:
    target=Path(t)/'connection.json';r=self.invoke('configure','--output',str(target),value=value);self.assertNotEqual(r.returncode,0);self.assertNotIn('SECRET',r.stdout+r.stderr);self.assertFalse(target.exists())
if __name__=='__main__':unittest.main()
