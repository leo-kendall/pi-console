# SPDX-License-Identifier: Apache-2.0
import importlib.util,tempfile,unittest,zipfile,os,hashlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('release_android',Path(__file__).resolve().parents[1]/'scripts/release_android.py')
m=importlib.util.module_from_spec(spec)
if spec.loader: spec.loader.exec_module(m)
class ReleaseSigningTests(unittest.TestCase):
 def test_repack_keeps_resource_table_uncompressed_for_android_11(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d)
   with zipfile.ZipFile(d/'unsigned.apk','w',compression=zipfile.ZIP_DEFLATED) as z:
    z.writestr('classes.dex',b'dex fixture');z.writestr('AndroidManifest.xml',b'manifest fixture');z.writestr('resources.arsc',b'resources fixture')
   m.repack(d/'unsigned.apk',d/'release.apk',1700000000)
   with zipfile.ZipFile(d/'release.apk') as z:
    self.assertEqual(z.getinfo('resources.arsc').compress_type,zipfile.ZIP_STORED)
    self.assertEqual(z.read('resources.arsc'),b'resources fixture')
 def test_resource_table_validation_rejects_compression_and_misalignment(self):
  for compressed,extra,valid in [(True,b'',False),(False,b'',True),(False,b'\xfe\xca\x01\x00x',False),(False,b'\xfe\xca\x04\x00xxxx',True)]:
   with self.subTest(compressed=compressed,extra=extra),tempfile.TemporaryDirectory() as d:
    apk=Path(d)/'fixture.apk'
    item=zipfile.ZipInfo('resources.arsc');item.compress_type=zipfile.ZIP_DEFLATED if compressed else zipfile.ZIP_STORED;item.extra=extra
    with zipfile.ZipFile(apk,'w') as z:z.writestr(item,b'resources fixture')
    if valid:m.verify_resource_table(apk)
    else:
     with self.assertRaisesRegex(ValueError,'resources.arsc'):m.verify_resource_table(apk)
 def test_resource_table_validation_rejects_missing_table(self):
  with tempfile.TemporaryDirectory() as d:
   apk=Path(d)/'fixture.apk'
   with zipfile.ZipFile(apk,'w') as z:z.writestr('classes.dex',b'dex fixture')
   with self.assertRaisesRegex(ValueError,'resources.arsc'):m.verify_resource_table(apk)
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
