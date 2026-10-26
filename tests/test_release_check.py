# SPDX-License-Identifier: Apache-2.0
import hashlib,importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('release_check',Path(__file__).resolve().parents[1]/'scripts/check_release.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReleaseCheckTests(unittest.TestCase):
 def test_reviewed_image_is_allowed_only_with_its_exact_hash(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);name='android/res/drawable-nodpi/pi_console_mark.png';p=root/name;p.parent.mkdir(parents=True)
   data=b'\x89PNG\r\n\x1a\n\x00reviewed-image';p.write_bytes(data)
   with patch.object(m,'BINARY_ASSETS',{name:hashlib.sha256(data).hexdigest()},create=True):
    self.assertEqual(m.scan_files(root,[name]),[])
    p.write_bytes(data+b'changed')
    self.assertTrue(m.scan_files(root,[name]))
 def test_unreviewed_image_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'other.png').write_bytes(b'\x89PNG\r\n\x1a\n\x00image')
   self.assertTrue(m.scan_files(root,['other.png']))
 def test_credentials_binaries_and_runtime_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);files=['state/auth.json','config.json','release.jks','tools/browser','readme.md']
   for name in files:p=root/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_text('safe text')
   errors=m.scan_files(root,files);self.assertEqual(len(errors),4);self.assertTrue(all('readme.md' not in e for e in errors))
 def test_secret_contents_are_flagged_without_echoing_them(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);secret='gh'+'p_'+'a'*32;(root/'settings.py').write_text('TOKEN="'+secret+'"')
   errors=m.scan_files(root,['settings.py']);self.assertEqual(len(errors),1);self.assertNotIn(secret,str(errors))
 def test_symlink_escapes_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'link.py').symlink_to('/etc/hostname');self.assertTrue(m.scan_files(root,['link.py']))
 def test_example_config_is_distributable(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'config.example.json').write_text('{"resources":{}}');self.assertEqual(m.scan_files(root,['config.example.json']),[])
