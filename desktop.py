# SPDX-License-Identifier: Apache-2.0
"""Per-device Guacamole tunnels to one fixed local GNOME desktop."""
import codecs,json,secrets,socket,threading,time,re
from pathlib import Path
from control import ApiError,ROOT
from config import SETTINGS

def certificate_pin(value):
 fingerprint=value.split('=',1)[-1]
 if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){31}[0-9a-fA-F]{2}',fingerprint):raise ApiError('桌面证书指纹格式无效',503)
 return 'sha256:'+fingerprint

def instruction(*parts):return (','.join(str(len(str(p)))+'.'+str(p) for p in parts)+';').encode()
def receive(stream):
 parts=[]
 for _ in range(256):
  digits=b''
  while True:
   c=stream.read(1)
   if c==b'.':break
   if not c or not c.isdigit() or len(digits)>7:raise ApiError('桌面协议错误',502)
   digits+=c
  length=int(digits)
  if length>65536:raise ApiError('桌面指令过大',502)
  value=b''
  while len(value)<length:
   chunk=stream.read(length-len(value))
   if not chunk:raise ApiError('桌面连接中断',502)
   value+=chunk
  parts.append(value.decode())
  sep=stream.read(1)
  if sep==b';':return parts
  if sep!=b',':raise ApiError('桌面协议错误',502)
 raise ApiError('桌面参数过多',502)

class Session:
 def __init__(self,sock,owner):
  self.sock=sock;self.owner=owner;self.read_lock=threading.Lock();self.write_lock=threading.Lock();self.touched=time.monotonic();self.created=self.touched
  self.decoder=codecs.getincrementaldecoder('utf-8')();self.closed=False
 def close(self):
  self.closed=True
  try:self.sock.shutdown(socket.SHUT_RDWR)
  except OSError:pass
  self.sock.close()
 def read(self):
  if not self.read_lock.acquire(blocking=False):raise ApiError('桌面读取已在进行',409)
  try:
   self.touched=time.monotonic()
   try:data=self.sock.recv(128*1024)
   except socket.timeout:return ''
   if not data:raise ApiError('远程桌面已断开',410)
   return self.decoder.decode(data)
  finally:self.read_lock.release()
 def write(self,data):
  if not isinstance(data,str) or len(data.encode())>65536:raise ApiError('桌面输入过大')
  with self.write_lock:self.sock.sendall(data.encode());self.touched=time.monotonic()

class Desktop:
 def __init__(self):
  self.sessions={};self.lock=threading.RLock()
  threading.Thread(target=self.reap,daemon=True).start()
 def reap(self):
  while True:
   time.sleep(10)
   with self.lock:
    for sid,s in list(self.sessions.items()):
     if s.closed or time.monotonic()-s.touched>45 or time.monotonic()-s.created>8*3600:s.close();del self.sessions[sid]
 def get(self,owner,sid):
  with self.lock:
   s=self.sessions.get(sid)
   if not s or s.owner!=owner:raise ApiError('桌面会话不存在',404)
   return s
 def close(self,owner,sid):
  with self.lock:self.get(owner,sid).close();del self.sessions[sid]
 def revoke(self,owner):
  with self.lock:
   for sid,s in list(self.sessions.items()):
    if s.owner==owner:s.close();del self.sessions[sid]
 def open(self,owner,width,height):
  if type(width)!=int or type(height)!=int or not 640<=width<=2560 or not 480<=height<=1440:raise ApiError('无效桌面尺寸')
  with self.lock:
   self.revoke(owner)
   if len(self.sessions)>=2:raise ApiError('桌面会话已达上限，请先断开',409)
   connection=ROOT/'remote-desktop/connection.json'
   if connection.stat().st_mode & 0o077:raise ApiError('桌面凭据权限异常',503)
   config=json.loads(connection.read_text())
   sock=socket.create_connection(('127.0.0.1',14822),timeout=12)
   try:
    sock.sendall(instruction('select','rdp'))
    with sock.makefile('rb',buffering=0) as stream:
     args=receive(stream)
     if args[0]!='args' or 'cert-fingerprints' not in args:raise ApiError('桌面桥接版本不支持证书校验',503)
     params={'hostname':'127.0.0.1','port':'3389','username':config['username'],'password':config['password'],
      'security':'nla','ignore-cert':'false','cert-fingerprints':certificate_pin(config['fingerprint']),
      'width':str(width),'height':str(height),'dpi':'96','color-depth':'24','resize-method':'display-update','force-lossless':'true',
      'disable-audio':'true','enable-drive':'false','enable-printing':'false','server-layout':'en-us-qwerty','client-name':'Pi Console','timezone':SETTINGS['desktop_timezone']}
     for values in [('size',width,height,96),('audio',),('video',),('image','image/png','image/jpeg'),('timezone',SETTINGS['desktop_timezone'])]:sock.sendall(instruction(*values))
     sock.sendall(instruction('connect',*[k if k.startswith('VERSION_') else params.get(k,'') for k in args[1:]]))
     ready=receive(stream)
     if ready[0]!='ready':raise ApiError('远程桌面连接失败，请检查桥接日志',502)
    sock.settimeout(4);sid=secrets.token_hex(24);self.sessions[sid]=Session(sock,owner)
    return {'id':sid,'width':width,'height':height}
   except BaseException:sock.close();raise
