# SPDX-License-Identifier: Apache-2.0
import base64,hashlib,json,tempfile,unittest
from pathlib import Path
from files import Files
from control import ApiError

class ExtendedTransferTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.files=Files(self.base/'data')
 def test_large_file_metadata_and_explicit_size_bound(self):
  u=self.files.create_upload('phone','','video.mp4',101*1024*1024,request='upload-video-0001')
  self.assertEqual(self.files.upload_status('phone',u['id'])['size'],101*1024*1024)
  with self.assertRaises(ApiError):self.files.create_upload('phone','','too-large.bin',8*1024**3+1)
 def test_resume_after_backend_restart_and_lost_chunk_acknowledgement(self):
  content=b'resume-content';request='upload-resume-0001';u=self.files.create_upload('phone','','file.bin',len(content),request=request)
  encoded=base64.b64encode(content[:6]).decode();self.files.append('phone',u['id'],0,encoded)
  self.assertEqual(self.files.append('phone',u['id'],0,encoded)['offset'],6)
  new=Files(self.base/'data');same=new.create_upload('phone','','file.bin',len(content),request=request)
  self.assertEqual(same['id'],u['id']);self.assertEqual(same['offset'],6)
  new.append('phone',same['id'],6,base64.b64encode(content[6:]).decode());new.finish('phone',same['id'],hashlib.sha256(content).hexdigest())
  self.assertEqual((self.base/'data/files/file.bin').read_bytes(),content)
 def test_wrong_owner_or_changed_request_cannot_resume(self):
  u=self.files.create_upload('phone','','file.bin',6,request='upload-private-0001')
  with self.assertRaises(ApiError):self.files.upload_status('other',u['id'])
  with self.assertRaises(ApiError):self.files.create_upload('phone','','other.bin',6,request='upload-private-0001')
 def test_resume_reconciles_chunk_written_before_metadata_was_saved(self):
  u=self.files.create_upload('phone','','file.bin',6,request='upload-crash-0001')
  (self.base/'data/uploads'/ (u['id']+'.part')).write_bytes(b'abc')
  self.assertEqual(Files(self.base/'data').upload_status('phone',u['id'])['offset'],3)
 def test_named_external_root_and_readonly_enforced_for_direct_calls(self):
  from file_spaces import FileSpaces
  external=self.base/'media';external.mkdir();(external/'test.txt').write_text('data')
  spaces=FileSpaces(self.base/'data',{'media':{'name':'媒体','path':str(external),'writable':False}})
  self.assertEqual(spaces.space('media').list()['items'][0]['name'],'test.txt')
  self.assertFalse(next(x for x in spaces.roots()['roots'] if x['id']=='media')['writable'])
  with self.assertRaises(ApiError):spaces.space('media').create_upload('phone','','no.txt',1)
  with self.assertRaises(ApiError):spaces.space('media').mkdir('','no')
  with self.assertRaises(ApiError):spaces.space('../').list()
 def test_batch_trash_is_idempotent_and_retains_partial_results(self):
  for name in ['a.txt','b.txt']:(self.base/'data/files'/name).write_text(name)
  items=[{'path':name,'ticket':self.files.stat('phone',name)['ticket']} for name in ['a.txt','b.txt']]
  result=self.files.batch_trash('phone',items,'batch-trash-0001')
  self.assertEqual(result['completed'],2);self.assertEqual(self.files.batch_trash('phone',items,'batch-trash-0001'),result)
  self.assertEqual(len(self.files.trash_list('phone')['items']),2)
 def test_external_root_requires_existing_safe_path_and_writable_system_paths_refused(self):
  from file_spaces import FileSpaces
  from config import load_config
  p=self.base/'config.json';p.write_text(json.dumps({'file_roots':{'system':{'name':'系统','path':'/etc','writable':True}}}))
  with self.assertRaises(ValueError):load_config(p)
  link=self.base/'link';link.symlink_to(self.base)
  with self.assertRaises(ApiError):FileSpaces(self.base/'data',{'unsafe':{'name':'链接','path':str(link),'writable':True}})
