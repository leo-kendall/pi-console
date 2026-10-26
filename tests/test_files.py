# SPDX-License-Identifier: Apache-2.0
import base64,hashlib,tempfile,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from files import Files
from control import ApiError
class FileTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.f=Files(self.base/'data')
 def upload(self,name='test.txt',data=b'hello'):
  u=self.f.create_upload('owner','',name,len(data));self.f.append('owner',u['id'],0,base64.b64encode(data).decode());self.f.finish('owner',u['id'],hashlib.sha256(data).hexdigest());return self.f.stat('owner',name)
 def test_upload_download_and_no_overwrite(self):
  p=self.upload();r=self.f.read('owner','test.txt',0,p['ticket']);self.assertEqual(base64.b64decode(r['data']),b'hello');self.assertTrue(r['eof'])
  with self.assertRaises(ApiError):self.f.create_upload('owner','','test.txt',1)
 def test_path_and_symlink_refused(self):
  for path in ['../','/etc','x/../../y','.hidden','a\\b']:
   with self.assertRaises(ApiError):self.f.list(path)
  (self.f.root.root/'link').symlink_to(self.base,target_is_directory=True)
  with self.assertRaises((ApiError,OSError)):self.f.list('link')
 def test_upload_owner_offset_and_size_checked(self):
  u=self.f.create_upload('owner','','a',2)
  for owner,offset,data in [('other',0,b'a'),('owner',1,b'a'),('owner',0,b'aaa')]:
   with self.assertRaises(ApiError):self.f.append(owner,u['id'],offset,base64.b64encode(data).decode())
  self.f.append('owner',u['id'],0,'YWI=')
  with self.assertRaises(ApiError):self.f.finish('owner',u['id'],'0'*64)
 def test_trash_restore_and_changed_file_ticket(self):
  p=self.upload();(self.f.root.root/'test.txt').write_bytes(b'changed')
  with self.assertRaises(ApiError):self.f.trash('owner','test.txt',p['ticket'])
  p=self.f.stat('owner','test.txt');self.f.trash('owner','test.txt',p['ticket']);self.assertEqual(self.f.list('')['items'],[])
  items=self.f.trash_list('owner')['items'];self.assertEqual(self.f.trash_list('other')['items'],[])
  self.f.restore('owner',items[0]['id']);self.assertEqual((self.f.root.root/'test.txt').read_bytes(),b'changed')
 def test_rename_no_overwrite_and_directory(self):
  p=self.upload();self.upload('other');
  with self.assertRaises(ApiError):self.f.rename('owner','test.txt','other',p['ticket'])
  self.f.mkdir('','folder');self.f.rename('owner','test.txt','renamed',p['ticket']);self.assertEqual((self.f.root.root/'renamed').read_bytes(),b'hello')
