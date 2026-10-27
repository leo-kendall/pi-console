# SPDX-License-Identifier: Apache-2.0
"""Per-device Guacamole tunnels to a configured loopback RDP or VNC desktop."""
import codecs,json,secrets,socket,threading,time,re,os,stat
from pathlib import Path
from control import ApiError,ROOT
from config import SETTINGS

def certificate_pin(value):
 fingerprint=value.split('=',1)[-1]
 if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){31}[0-9a-fA-F]{2}',fingerprint):raise ApiError('桌面证书指纹格式无效',503)
 return 'sha256:'+fingerprint


def load_connection(path):
 """Open a bounded private regular file without following a last-component link."""
 try:
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  with os.fdopen(fd,'r') as f:
   meta=os.fstat(f.fileno())
   if not stat.S_ISREG(meta.st_mode) or meta.st_mode&0o077 or meta.st_uid not in (0,os.geteuid()):raise ValueError()
   data=f.read(16385)
   if len(data)>16384:raise ValueError()
   config=json.loads(data)
   if not isinstance(config,dict):raise ValueError()
   return config
 except (OSError,ValueError,UnicodeError):raise ApiError('桌面配置缺失、格式或私有权限无效',503) from None

def connection_parameters(config,width,height):
 protocol=config.get('protocol','rdp');host=config.get('host','127.0.0.1');port=config.get('port',5900 if protocol=='vnc' else 3389)
 if protocol not in ('rdp','vnc') or host not in ('127.0.0.1','::1') or type(port)!=int or not 1<=port<=65535:raise ApiError('桌面协议或本机地址端口无效',503)
 params={'protocol':protocol,'hostname':host,'port':str(port),'width':str(width),'height':str(height),'dpi':'96','color-depth':'24','force-lossless':'true','disable-audio':'true','enable-drive':'false','enable-printing':'false','client-name':'Pi Console','timezone':SETTINGS['desktop_timezone']}
 def text(key,default='',limit=1024):
  value=config.get(key,default)
  if not isinstance(value,str) or len(value)>limit or '\x00' in value:raise ApiError('桌面认证参数无效',503)
  return value
 if protocol=='rdp':
  security=config.get('security','nla')
  if security not in ('nla','tls'):raise ApiError('RDP 仅支持固定证书的 NLA 或 TLS 安全模式',503)
  params.update(username=text('username',limit=256),password=text('password'),domain=text('domain',limit=256),security=security)
  params.update({'ignore-cert':'false','cert-fingerprints':certificate_pin(text('fingerprint')),'resize-method':'display-update','server-layout':'en-us-qwerty'})
 else:
  security=config.get('security','vnc');password=text('password',limit=8)
  if security not in ('none','vnc'):raise ApiError('VNC 安全模式不支持：仅支持本机 None 或经典 VNC 密码；VeNCrypt/TLS/RA2 须另行适配',503)
  if security=='vnc' and (not password or not password.isascii()):raise ApiError('经典 VNC 密码须为 1 至 8 个 ASCII 字符',503)
  if security=='none' and password:raise ApiError('VNC 无认证模式不能同时配置密码',503)
  params.update(security=security,password=password)
 return params

def probe_vnc(params):
 """Check RFB security negotiation without submitting any password or client-init."""
 def exact(sock,n):
  data=b''
  while len(data)<n:
   chunk=sock.recv(n-len(data))
   if not chunk:raise ApiError('VNC 握手中断',503)
   data+=chunk
  return data
 try:
  with socket.create_connection((params['hostname'],int(params['port'])),timeout=4) as sock:
   version=exact(sock,12)
   if version not in (b'RFB 003.003\n',b'RFB 003.007\n',b'RFB 003.008\n'):raise ApiError('VNC RFB 协议版本不支持（需要 3.3、3.7 或 3.8）',503)
   sock.sendall(version);want=1 if params['security']=='none' else 2
   if version==b'RFB 003.003\n':offered=[int.from_bytes(exact(sock,4),'big')]
   else:
    count=exact(sock,1)[0];offered=list(exact(sock,count))
   if offered!=[want]:raise ApiError('VNC 服务认证不兼容；未降级认证。VeNCrypt/TLS/RA2 等模式当前不支持',503)
   if version!=b'RFB 003.003\n':sock.sendall(bytes([want]))
   return {'protocol':'vnc','rfb':version.decode().strip(),'security':params['security']}
 except OSError:raise ApiError('无法连接本机 VNC 服务',503) from None

def capabilities(root=None):
 """Read-only configuration metadata: never connects or returns credentials."""
 path=(ROOT if root is None else root)/'remote-desktop/connection.json'
 configured={'state':'unconfigured','live_verified':False}
 try:
  path.lstat()
 except FileNotFoundError:pass
 except OSError:configured={'state':'invalid','live_verified':False}
 else:
  try:
   params=connection_parameters(load_connection(path),1280,800)
   configured={'state':'configured','protocol':params['protocol'],'security':params['security'],'host':params['hostname'],'port':int(params['port']),'live_verified':False}
  except ApiError:configured={'state':'invalid','live_verified':False}
 return {'version':1,'protocols':['rdp','vnc'],'configuration':configured,'rdp_security':['nla','tls'],'vnc_security':['none','vnc'],'local_only':True,'clipboard':{'mode':'explicit-text','max_bytes':16384}}

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
  if not digits:raise ApiError('桌面协议错误',502)
  length=int(digits)
  if length>65536:raise ApiError('桌面指令过大',502)
  decoder=codecs.getincrementaldecoder('utf-8')();value=[]
  try:
   for _ in range(length):
    char=''
    while not char:
     byte=stream.read(1)
     if not byte:raise ApiError('桌面连接中断',502)
     char=decoder.decode(byte)
    value.append(char)
  except UnicodeError:raise ApiError('桌面 UTF-8 协议错误',502) from None
  parts.append(''.join(value))
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
   config=load_connection(connection);params=connection_parameters(config,width,height)
   if params['protocol']=='vnc':probe_vnc(params)
   sock=socket.create_connection(('127.0.0.1',14822),timeout=12)
   try:
    sock.sendall(instruction('select',params['protocol']))
    with sock.makefile('rb',buffering=0) as stream:
     args=receive(stream)
     if args[0]!='args':raise ApiError('桌面桥接协商失败',503)
     if params['protocol']=='rdp' and 'cert-fingerprints' not in args:raise ApiError('桌面桥接版本不支持证书校验',503)
     for values in [('size',width,height,96),('audio',),('video',),('image','image/png','image/jpeg'),('timezone',SETTINGS['desktop_timezone'])]:sock.sendall(instruction(*values))
     sock.sendall(instruction('connect',*[k if k.startswith('VERSION_') else params.get(k,'') for k in args[1:]]))
     ready=receive(stream)
     if ready[0]!='ready':raise ApiError('远程桌面连接失败，请检查桥接日志',502)
    sock.settimeout(4);sid=secrets.token_hex(24);self.sessions[sid]=Session(sock,owner)
    return {'id':sid,'width':width,'height':height,'protocol':params['protocol']}
   except BaseException:sock.close();raise
