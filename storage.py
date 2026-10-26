# SPDX-License-Identifier: Apache-2.0
"""Bounded read-only scans; preview-only cleanup of explicitly disposable cache."""
import os,stat,time,secrets,threading
from pathlib import Path
from control import ApiError
from safe_fs import SafeRoot,fingerprint
from config import SETTINGS
ROOT=Path(__file__).resolve().parent
class Storage:
 def __init__(self,roots=None,caches=None):
  self.roots=roots if roots is not None else SETTINGS['storage_roots']
  self.caches=caches or {'preview':ROOT/'tools/preview-firefox-profile/cache2'}
  self.lock=threading.RLock();self.previews={};self.results={}
 def scan(self,key):
  if key not in self.roots:raise ApiError('不允许的分析目录')
  with self.lock:
   old=self.results.get(key)
   if old and time.monotonic()-old[0]<60:return old[1]
   root=SafeRoot(self.roots[key],False);items=[];count=0;complete=True;deadline=time.monotonic()+5
   def walk(fd,depth):
    nonlocal count,complete
    total=0
    with os.scandir(fd) as entries:
     for entry in entries:
      if count>=20000 or time.monotonic()>deadline or depth>16:complete=False;break
      count+=1
      try:
       s=entry.stat(follow_symlinks=False)
       if stat.S_ISREG(s.st_mode):total+=s.st_size
       elif stat.S_ISDIR(s.st_mode) and s.st_dev==root.identity[0]:
        child=os.open(entry.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
        try:total+=walk(child,depth+1)
        finally:os.close(child)
      except OSError:complete=False
    return total
   with root.directory() as fd:
    with os.scandir(fd) as entries:
     for entry in entries:
      if time.monotonic()>deadline or count>=20000:complete=False;break
      count+=1
      try:
       s=entry.stat(follow_symlinks=False)
       if stat.S_ISREG(s.st_mode):size=s.st_size;kind='file'
       elif stat.S_ISDIR(s.st_mode) and s.st_dev==root.identity[0]:
        child=os.open(entry.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
        try:size=walk(child,1)
        finally:os.close(child)
        kind='directory'
       else:continue
       items.append(dict(name=entry.name,bytes=size,kind=kind))
      except OSError:complete=False
   items.sort(key=lambda x:x['bytes'],reverse=True)
   data=dict(root=key,path=str(self.roots[key]),items=items[:30],complete=complete,scanned_entries=count,sampled_at=time.time());self.results[key]=(time.monotonic(),data);return data
 def manifest(self,root):
  result={};deadline=time.monotonic()+4
  def walk(fd,prefix):
   with os.scandir(fd) as entries:
    for e in entries:
     if len(result)>=5000 or time.monotonic()>deadline:raise ApiError('缓存过大，不能安全预览')
     s=e.stat(follow_symlinks=False);path=prefix+e.name
     if not(stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise ApiError('缓存含链接或特殊文件，保留不清理')
     result[path]=fingerprint(s)
     if stat.S_ISDIR(s.st_mode):
      child=os.open(e.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
      try:walk(child,path+'/')
      finally:os.close(child)
  with root.directory() as fd:walk(fd,'')
  return result
 def preview(self,owner,key):
  if key not in self.caches:raise ApiError('不允许的清理对象')
  path=self.caches[key]
  if not path.exists():return dict(id=None,name='控制台预览缓存',files=0,bytes=0)
  with self.lock:
   root=SafeRoot(path,False);manifest=self.manifest(root);token=secrets.token_hex(16)
   self.previews={k:v for k,v in self.previews.items() if time.monotonic()-v['time']<120}
   if len(self.previews)>=16:raise ApiError('预览过多，请稍后再试',429)
   self.previews[token]=dict(owner=owner,root=root,manifest=manifest,time=time.monotonic())
   return dict(id=token,name='控制台预览缓存',files=sum(x[-1]==stat.S_IFREG for x in manifest.values()),bytes=sum(x[2] for x in manifest.values() if x[-1]==stat.S_IFREG))
 def clean(self,owner,token):
  with self.lock:
   p=self.previews.get(token)
   if not p or p['owner']!=owner or time.monotonic()-p['time']>120:raise ApiError('清理预览已失效，请重新检查',409)
   root=p['root'];manifest=p['manifest']
   if self.manifest(root)!=manifest:raise ApiError('缓存内容已变化，未清理，请重新预览',409)
   for path,expected in sorted(manifest.items(),key=lambda x:x[0].count('/'),reverse=True):
    names=path.split('/')
    with root.directory('/'.join(names[:-1]),hidden=True) as fd:
     s=os.stat(names[-1],dir_fd=fd,follow_symlinks=False)
     if stat.S_ISREG(s.st_mode):
      if fingerprint(s)!=expected:raise ApiError('缓存内容在清理中变化，请刷新核实',409)
      os.unlink(names[-1],dir_fd=fd)
     elif stat.S_ISDIR(s.st_mode):
      try:os.rmdir(names[-1],dir_fd=fd)
      except OSError:pass
     else:raise ApiError('缓存类型已变化，停止清理',409)
   del self.previews[token];self.results.clear()
