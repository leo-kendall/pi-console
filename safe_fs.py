# SPDX-License-Identifier: Apache-2.0
"""Directory-FD-relative filesystem access; no symlink traversal."""
import os,re,stat
from contextlib import contextmanager
from pathlib import Path
from control import ApiError

def parts(path,empty=False):
 if not isinstance(path,str) or len(path.encode())>2048 or '\\' in path or '\x00' in path:raise ApiError('无效文件路径')
 if path=='' and empty:return []
 values=path.split('/')
 if not values or len(values)>24 or any(v in ('','.','..') or v.startswith('.') or len(v.encode())>200 for v in values):raise ApiError('不允许的文件路径')
 return values

def fingerprint(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,stat.S_IFMT(s.st_mode)]
class SafeRoot:
 def __init__(self,root,create=True):
  self.root=Path(root)
  if any(p.is_symlink() for p in (self.root,*self.root.parents)):raise ApiError('目录路径含链接，不允许访问')
  if create:self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
  if self.root.is_symlink() or not self.root.is_dir():raise ApiError('文件目录不可用')
  self.identity=(self.root.stat().st_dev,self.root.stat().st_ino)
 @contextmanager
 def directory(self,path='',hidden=False):
  values=path.split('/') if hidden and path else parts(path,True)
  fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:
   s=os.fstat(fd)
   if (s.st_dev,s.st_ino)!=self.identity:raise ApiError('目录已变化',409)
   for name in values:
    if name in ('','.','..') or '/' in name:raise ApiError('无效目录')
    new=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=new
   yield fd
  finally:os.close(fd)
 @contextmanager
 def parent(self,path):
  values=parts(path)
  with self.directory('/'.join(values[:-1])) as fd:yield fd,values[-1]
