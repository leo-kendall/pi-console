# SPDX-License-Identifier: Apache-2.0
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage import Storage
from control import ApiError
class StorageTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.cache=self.root/'cache';self.cache.mkdir();self.s=Storage({'home':self.root},{'preview':self.cache})
 def test_scan_does_not_follow_links(self):
  outside=self.root/'secret';outside.mkdir();(outside/'x').write_bytes(b'private');(self.root/'link').symlink_to(outside,target_is_directory=True)
  data=self.s.scan('home');self.assertFalse(any(x['name']=='link' for x in data['items']))
  with self.assertRaises(ApiError):self.s.scan('/etc')
 def test_cleanup_requires_owner_preview_and_unchanged_content(self):
  p=self.cache/'x';p.write_bytes(b'old');preview=self.s.preview('owner','preview')
  with self.assertRaises(ApiError):self.s.clean('other',preview['id'])
  p.write_bytes(b'changed')
  with self.assertRaises(ApiError):self.s.clean('owner',preview['id'])
  self.assertEqual(p.read_bytes(),b'changed')
 def test_only_previewed_cache_is_removed(self):
  p=self.cache/'x';p.write_bytes(b'cache');other=self.root/'photos';other.write_bytes(b'keep');preview=self.s.preview('owner','preview');self.s.clean('owner',preview['id']);self.assertFalse(p.exists());self.assertEqual(other.read_bytes(),b'keep')
 def test_symlink_in_cleanup_root_refused(self):
  (self.cache/'link').symlink_to(self.root/'photos')
  with self.assertRaises(ApiError):self.s.preview('owner','preview')
