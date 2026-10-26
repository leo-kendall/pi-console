# SPDX-License-Identifier: Apache-2.0
"""Isolated files, bounded chunked transfers, and recoverable file removal."""
import base64,errno,hashlib,hmac,json,os,re,secrets,stat,threading,time
from pathlib import Path
from control import ApiError,save
from safe_fs import SafeRoot,parts,fingerprint
CHUNK=128*1024;MAX_FILE=8*1024**3;RESERVE=256*1024*1024
class Files:
 def __init__(self,base=Path(__file__).resolve().parent/'data',root=None,writable=True):
  self.base=Path(base);self.writable=writable;self.root=SafeRoot(self.base/'files' if root is None else root,create=root is None);self.uploads=SafeRoot(self.base/'uploads');self.bin=SafeRoot(self.base/'trash');self.batches=SafeRoot(self.base/'batches');self.key=secrets.token_bytes(32);self.lock=threading.RLock()
 def write_check(self):
  if not self.writable:raise ApiError('此目录只允许查看和下载',403)
 def ident(self,value):
  if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ApiError('无效传输标识')
  return value
 def list(self,path=''):
  items=[]
  with self.root.directory(path) as fd:
   with os.scandir(fd) as entries:
    for e in entries:
     if e.name.startswith('.'):continue
     s=e.stat(follow_symlinks=False)
     if not(stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):continue
     items.append(dict(name=e.name,kind='directory' if stat.S_ISDIR(s.st_mode) else 'file',bytes=s.st_size,modified=s.st_mtime))
     if len(items)>=500:break
  items.sort(key=lambda x:(x['kind']!='directory',x['name'].casefold()))
  return dict(path=path,items=items,limit=500,max_file_bytes=MAX_FILE,writable=self.writable)
 def stamp(self,owner,path,s):return hmac.new(self.key,json.dumps([owner,path,fingerprint(s)]).encode(),hashlib.sha256).hexdigest()
 def stat(self,owner,path):
  with self.root.parent(path) as (fd,name):
   s=os.stat(name,dir_fd=fd,follow_symlinks=False)
   if not(stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise ApiError('链接和特殊文件不提供操作')
   return dict(path=path,name=name,kind='directory' if stat.S_ISDIR(s.st_mode) else 'file',bytes=s.st_size,modified=s.st_mtime,ticket=self.stamp(owner,path,s))
 def check(self,owner,path,s,ticket):
  if not isinstance(ticket,str) or not hmac.compare_digest(self.stamp(owner,path,s),ticket):raise ApiError('文件已变化，请重新打开详情',409)
 def read(self,owner,path,offset,ticket):
  if type(offset)!=int or not 0<=offset<=MAX_FILE:raise ApiError('无效读取位置')
  with self.root.parent(path) as (fd,name):
   file=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
   try:
    s=os.fstat(file)
    if not stat.S_ISREG(s.st_mode) or s.st_size>MAX_FILE:raise ApiError('仅支持 8 GiB 以内的普通文件')
    self.check(owner,path,s,ticket);os.lseek(file,offset,os.SEEK_SET);data=os.read(file,CHUNK)
    if fingerprint(os.fstat(file))!=fingerprint(s):raise ApiError('文件读取中发生变化，请重试',409)
    return dict(data=base64.b64encode(data).decode(),offset=offset,eof=offset+len(data)>=s.st_size,size=s.st_size)
   finally:os.close(file)
 def mkdir(self,path,name):
  self.write_check()
  if len(parts(name))!=1:raise ApiError('无效文件夹名称')
  with self.lock,self.root.directory(path) as fd:
   try:os.mkdir(name,mode=0o700,dir_fd=fd)
   except FileExistsError:raise ApiError('同名项目已存在',409)
 def clean_expired(self):
  with os.scandir(self.uploads.root) as entries:
   for e in entries:
    if re.fullmatch('[0-9a-f]{32}\\.json',e.name) and time.time()-e.stat(follow_symlinks=False).st_mtime>86400:
     for suffix in ('.part','.json'):(self.uploads.root/(e.name[:-5]+suffix)).unlink(missing_ok=True)
 def start_cleanup(self):
  def loop():
   while True:
    try:
     with self.lock:self.clean_expired()
    except (OSError,ValueError,KeyError):pass
    time.sleep(60)
  threading.Thread(target=loop,name='partial-file-cleanup',daemon=True).start()
 def create_upload(self,owner,directory,name,size,request=None):
  self.write_check()
  if request is not None and (not isinstance(request,str) or not re.fullmatch('[A-Za-z0-9-]{12,64}',request)):raise ApiError('无效上传请求标识')
  if len(parts(name))!=1 or type(size)!=int or not 0<=size<=MAX_FILE:raise ApiError('文件名或大小无效，最多 8 GiB')
  path='/'.join(filter(None,[directory,name]));parts(path)
  with self.lock,self.root.directory(directory) as fd:
   self.clean_expired()
   if request is not None:
    for p in self.uploads.root.glob('*.json'):
     meta=json.loads(p.read_text())
     if meta['owner']==owner and meta.get('request')==request:
      if meta['path']!=path or meta['size']!=size:raise ApiError('上传请求已用于其他文件',409)
      status=self.upload_status(owner,p.stem);return dict(id=p.stem,offset=status['offset'],chunk_bytes=CHUNK)
   try:os.stat(name,dir_fd=fd,follow_symlinks=False)
   except FileNotFoundError:pass
   else:raise ApiError('同名项目已存在，不会覆盖',409)
   fs=os.statvfs(self.uploads.root)
   if fs.f_bavail*fs.f_frsize<size+RESERVE:raise ApiError('磁盘可用空间不足，保留系统余量')
   metas=list(self.uploads.root.glob('*.json'))
   if len(metas)>=8 or sum(json.loads(p.read_text())['size'] for p in metas)+size>32*1024**3:raise ApiError('传输空间或数量已达上限',429)
   ident=secrets.token_hex(16);file=os.open(self.uploads.root/(ident+'.part'),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(file)
   save(self.uploads.root/(ident+'.json'),dict(owner=owner,path=path,size=size,offset=0,created=time.time(),request=request))
   return dict(id=ident,offset=0,chunk_bytes=CHUNK)
 def session(self,owner,ident):
  self.ident(ident);p=self.uploads.root/(ident+'.json')
  if not p.is_file():raise ApiError('上传已结束或不存在',404)
  data=json.loads(p.read_text())
  if data['owner']!=owner:raise ApiError('上传不存在',404)
  if time.time()-p.stat().st_mtime>86400 or time.time()-data['created']>7*86400:raise ApiError('上传已过期，请重新选择文件',410)
  return data
 def upload_status(self,owner,ident):
  with self.lock:
   meta=self.session(owner,ident);fd=os.open(self.uploads.root/(ident+'.part'),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
   try:
    info=os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or not meta['offset']<=info.st_size<=meta['size']:raise ApiError('暂存文件已变化，请重新选择文件',409)
    if info.st_size!=meta['offset']:meta['offset']=info.st_size;save(self.uploads.root/(ident+'.json'),meta)
   finally:os.close(fd)
   return dict(id=ident,path=meta['path'],name=meta['path'].rsplit('/',1)[-1],size=meta['size'],offset=meta['offset'],expires=min(meta['created']+7*86400,(self.uploads.root/(ident+'.json')).stat().st_mtime+86400),chunk_bytes=CHUNK)
 def resumable(self,owner):
  result=[]
  with self.lock:
   for p in self.uploads.root.glob('*.json'):
    try:
     meta=json.loads(p.read_text())
     if meta['owner']==owner:result.append(self.upload_status(owner,p.stem))
    except (OSError,ApiError,ValueError):continue
  return {'uploads':result[:8]}
 def append(self,owner,ident,offset,encoded):
  self.write_check()
  if type(offset)!=int or not isinstance(encoded,str) or len(encoded)>CHUNK*4//3+8:raise ApiError('无效数据块')
  try:data=base64.b64decode(encoded,validate=True)
  except ValueError:raise ApiError('无效文件编码')
  if not data or len(data)>CHUNK:raise ApiError('文件数据块超出范围')
  with self.lock:
   meta=self.session(owner,ident)
   if 0<=offset<meta['offset'] and offset+len(data)<=meta['offset']:
    fd=os.open(self.uploads.root/(ident+'.part'),os.O_RDONLY|os.O_NOFOLLOW)
    try:os.lseek(fd,offset,os.SEEK_SET);same=hmac.compare_digest(os.read(fd,len(data)),data)
    finally:os.close(fd)
    if same:return dict(offset=meta['offset'])
   if offset!=meta['offset'] or offset+len(data)>meta['size']:raise ApiError('上传位置或大小不匹配',409)
   fs=os.statvfs(self.uploads.root)
   if fs.f_bavail*fs.f_frsize<len(data)+RESERVE:raise ApiError('磁盘可用空间不足，已暂停写入',409)
   fd=os.open(self.uploads.root/(ident+'.part'),os.O_WRONLY|os.O_NOFOLLOW)
   try:
    if os.fstat(fd).st_size!=offset:raise ApiError('上传状态已变化，请重新上传',409)
    os.lseek(fd,offset,os.SEEK_SET)
    with os.fdopen(os.dup(fd),'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
   finally:os.close(fd)
   meta['offset']+=len(data);save(self.uploads.root/(ident+'.json'),meta);return dict(offset=meta['offset'])
 def finish(self,owner,ident,checksum):
  self.write_check()
  if not isinstance(checksum,str) or not re.fullmatch('[0-9a-f]{64}',checksum):raise ApiError('无效文件校验值')
  with self.lock:
   meta=self.session(owner,ident)
   if meta['offset']!=meta['size']:raise ApiError('上传尚未完成',409)
   fd=os.open(self.uploads.root/(ident+'.part'),os.O_RDONLY|os.O_NOFOLLOW)
   try:
    digest=hashlib.sha256()
    while chunk:=os.read(fd,CHUNK):digest.update(chunk)
    if not hmac.compare_digest(digest.hexdigest(),checksum):raise ApiError('文件校验失败，未发布',409)
   finally:os.close(fd)
   with self.root.parent(meta['path']) as (dest,name),self.uploads.directory() as source:
    try:self.publish(source,ident+'.part',dest,name)
    except FileExistsError:raise ApiError('同名文件已存在，不会覆盖',409)
    os.unlink(ident+'.part',dir_fd=source);os.unlink(ident+'.json',dir_fd=source)
 def abort(self,owner,ident):
  with self.lock:
   self.session(owner,ident)
   for suffix in ('.part','.json'):(self.uploads.root/(ident+suffix)).unlink(missing_ok=True)
 def rename(self,owner,path,new_name,ticket):
  self.write_check()
  if len(parts(new_name))!=1:raise ApiError('名称不能包含目录')
  with self.lock,self.root.parent(path) as (fd,name):
   s=os.stat(name,dir_fd=fd,follow_symlinks=False);self.check(owner,path,s,ticket)
   if not(stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise ApiError('不支持此文件类型')
   try:os.stat(new_name,dir_fd=fd,follow_symlinks=False)
   except FileNotFoundError:pass
   else:raise ApiError('同名项目已存在',409)
   os.rename(name,new_name,src_dir_fd=fd,dst_dir_fd=fd)
 def trash(self,owner,path,ticket):
  self.write_check()
  with self.lock,self.root.parent(path) as (fd,name),self.bin.directory() as dest:
   s=os.stat(name,dir_fd=fd,follow_symlinks=False);self.check(owner,path,s,ticket)
   if not stat.S_ISREG(s.st_mode):raise ApiError('仅支持将普通文件移入回收区；文件夹保留')
   ident=secrets.token_hex(16);meta=dict(id=ident,owner=owner,path=path,bytes=s.st_size,time=time.time());save(self.bin.root/(ident+'.json'),meta)
   try:
    try:os.rename(name,ident+'.bin',src_dir_fd=fd,dst_dir_fd=dest)
    except OSError as error:
     if error.errno!=errno.EXDEV:raise
     self.publish(fd,name,dest,ident+'.bin');os.unlink(name,dir_fd=fd)
   except OSError:(self.bin.root/(ident+'.json')).unlink(missing_ok=True);raise
 def trash_list(self,owner):
  items=[]
  with self.lock:
   for p in self.bin.root.glob('*.json'):
    data=json.loads(p.read_text())
    if data['owner']==owner and (self.bin.root/(data['id']+'.bin')).is_file():items.append(data)
  items.sort(key=lambda x:x['time'],reverse=True);return dict(items=items[:100])
 def restore(self,owner,ident):
  self.write_check()
  self.ident(ident)
  with self.lock:
   p=self.bin.root/(ident+'.json')
   if not p.exists():raise ApiError('回收记录不存在',404)
   meta=json.loads(p.read_text())
   if meta['owner']!=owner:raise ApiError('回收记录不存在',404)
   with self.root.parent(meta['path']) as (dest,name),self.bin.directory() as source:
    try:self.publish(source,ident+'.bin',dest,name)
    except FileExistsError:raise ApiError('原位置已有同名文件，保留回收内容',409)
    os.unlink(ident+'.bin',dir_fd=source);os.unlink(ident+'.json',dir_fd=source)
 def publish(self,source,source_name,dest,name):
  try:os.link(source_name,name,src_dir_fd=source,dst_dir_fd=dest,follow_symlinks=False);return
  except OSError as error:
   if error.errno!=errno.EXDEV:raise
  temporary='.pi-console-upload-'+secrets.token_hex(16);created=False
  read=os.open(source_name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=source)
  try:
   before=os.fstat(read)
   if not stat.S_ISREG(before.st_mode):raise ApiError('仅支持普通文件')
   fs=os.fstatvfs(dest)
   if fs.f_bavail*fs.f_frsize<before.st_size+RESERVE:raise ApiError('目标磁盘可用空间不足',409)
   write=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=dest);created=True
   with os.fdopen(write,'wb') as stream:
    while chunk:=os.read(read,CHUNK):stream.write(chunk)
    stream.flush();os.fsync(stream.fileno())
   if fingerprint(os.fstat(read))!=fingerprint(before):raise ApiError('源文件复制期间发生变化',409)
   os.link(temporary,name,src_dir_fd=dest,dst_dir_fd=dest,follow_symlinks=False)
  finally:
   os.close(read)
   if created:os.unlink(temporary,dir_fd=dest)
 def batch_trash(self,owner,items,request):
  self.write_check()
  if not isinstance(request,str) or not re.fullmatch('[A-Za-z0-9-]{12,64}',request) or not isinstance(items,list) or not 1<=len(items)<=32:raise ApiError('批量操作最多 32 项')
  for item in items:
   if not isinstance(item,dict) or set(item)!={'path','ticket'} or not isinstance(item['ticket'],str):raise ApiError('无效批量文件项')
   parts(item['path'])
  if len({item['path'] for item in items})!=len(items):raise ApiError('批量文件重复')
  fingerprint_request=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest();key=hashlib.sha256((owner+':'+request).encode()).hexdigest()+'.json'
  with self.lock:
   path=self.batches.root/key
   if path.exists():
    saved=json.loads(path.read_text())
    if saved['input']!=fingerprint_request:raise ApiError('请求已用于其他批量操作',409)
    return saved['result']
   result={'completed':0,'items':[]}
   for item in items:
    try:self.trash(owner,item['path'],item['ticket']);result['completed']+=1;result['items'].append({'path':item['path'],'ok':True})
    except (ApiError,OSError):result['items'].append({'path':item['path'],'ok':False,'message':'未移动，文件已变化或不可访问'})
   save(path,{'input':fingerprint_request,'result':result});return result
