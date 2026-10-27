# SPDX-License-Identifier: Apache-2.0
import errno,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from control import ApiError
from files import Files

class ExternalFileRaceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.external=self.base/'external';self.external.mkdir();self.files=Files(self.base/'data',root=self.external)
  (self.external/'old.txt').write_text('original');self.ticket=self.files.stat('owner','old.txt')['ticket']
 def test_concurrent_destination_creation_cannot_be_overwritten_by_rename(self):
  original=os.stat;created=[]
  def stat_call(name,*args,**kwargs):
   try:return original(name,*args,**kwargs)
   except FileNotFoundError:
    if name=='new.txt' and 'dir_fd' in kwargs and not created:
     fd=os.open('new.txt',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600,dir_fd=kwargs['dir_fd']);os.write(fd,b'concurrent-user-file');os.close(fd);created.append(True)
    raise
  with patch('files.os.stat',side_effect=stat_call),self.assertRaises(ApiError):self.files.rename('owner','old.txt','new.txt',self.ticket)
  self.assertTrue(created);self.assertEqual((self.external/'new.txt').read_text(),'concurrent-user-file');self.assertEqual((self.external/'old.txt').read_text(),'original')
 def test_cross_filesystem_trash_retains_source_instead_of_copy_then_unchecked_unlink(self):
  rename=os.rename
  def move(name,*args,**kwargs):
   if name=='old.txt':raise OSError(errno.EXDEV,'different devices')
   return rename(name,*args,**kwargs)
  with patch('files.os.rename',side_effect=move),self.assertRaises(ApiError):self.files.trash('owner','old.txt',self.ticket)
  self.assertEqual((self.external/'old.txt').read_text(),'original');self.assertEqual(self.files.trash_list('owner')['items'],[])
