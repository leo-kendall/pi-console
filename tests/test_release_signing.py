# SPDX-License-Identifier: Apache-2.0
import importlib.util,tempfile,unittest,zipfile,os,hashlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('release_android',Path(__file__).resolve().parents[1]/'scripts/release_android.py')
m=importlib.util.module_from_spec(spec)
if spec.loader: spec.loader.exec_module(m)
class ReleaseSigningTests(unittest.TestCase):
 def test_repack_deterministic_and_stored_dex(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d)
   with zipfile.ZipFile(d/'unsigned.apk','w') as z:z.writestr('classes.dex',b'dex fixture');z.writestr('AndroidManifest.xml',b'manifest fixture');z.writestr('assets/a.js',b'fixture')
   m.repack(d/'unsigned.apk',d/'first.apk',1700000000);m.repack(d/'unsigned.apk',d/'second.apk',1700000000)
   self.assertEqual((d/'first.apk').read_bytes(),(d/'second.apk').read_bytes())
   with zipfile.ZipFile(d/'first.apk') as z:self.assertEqual(z.getinfo('classes.dex').compress_type,zipfile.ZIP_STORED)
 def test_repack_rejects_signatures_duplicate_and_traversal(self):
  for name in ['META-INF/CERT.RSA','../secret']:
   with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
    d=Path(d)
    with zipfile.ZipFile(d/'bad.apk','w') as z:z.writestr('AndroidManifest.xml',b'm');z.writestr('classes.dex',b'd');z.writestr(name,b'bad')
    with self.assertRaises(ValueError):m.repack(d/'bad.apk',d/'out.apk',1700000000)
 def test_cert_is_required_and_checked(self):
  self.assertEqual(m.fingerprint('AA:'*31+'AA'),'a'*64)
  with self.assertRaises(ValueError):m.fingerprint('')
  m.verify_certificate('Signer #1 certificate SHA-256 digest: '+'a'*64,'a'*64)
  with self.assertRaises(ValueError):m.verify_certificate('Signer #1 certificate SHA-256 digest: '+'b'*64,'a'*64)
 def test_private_key_policy_never_allows_repo_or_world_readable(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);key=d/'release.fixture';key.write_text('fake keystore fixture');key.chmod(0o644)
   with self.assertRaises(ValueError):m.private_key(key,Path('/nonexistent/repository'))
   key.chmod(0o600);self.assertEqual(m.private_key(key,Path('/nonexistent/repository')),key)
   with self.assertRaises(ValueError):m.private_key(key,d)
