# SPDX-License-Identifier: Apache-2.0
"""Opt-in real guacd + synthetic loopback RFB peer. No host desktop is contacted.
PI_DESKTOP_GUACD_IMAGE must name an already cached immutable image; no pulls.
"""
import base64,json,os,secrets,socket,ssl,struct,subprocess,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import desktop

@unittest.skipUnless(os.environ.get('PI_DESKTOP_GUACD_IMAGE'),'opt-in cached guacd transport test')
class RealGuacdTests(unittest.TestCase):
 def test_real_rdp_tls_negotiation_refuses_wrong_certificate_pin(self):
  image=os.environ['PI_DESKTOP_GUACD_IMAGE'];self.assertIn('@sha256:',image)
  docker=['docker','--host=unix:///var/run/docker.sock'];subprocess.run(docker+['image','inspect',image],stdout=subprocess.DEVNULL,check=True)
  name='pi-console-transport-test-'+secrets.token_hex(6)
  with socket.socket() as reservation:reservation.bind(('127.0.0.1',0));guac_port=reservation.getsockname()[1]
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(12);self.addCleanup(listener.close)
  seen=[];errors=[];done=threading.Event()
  def exact(sock,n):
   data=b''
   while len(data)<n:
    chunk=sock.recv(n-len(data))
    if not chunk:raise EOFError()
    data+=chunk
   return data
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);key=root/'key.pem';cert=root/'cert.pem'
   subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=isolated-rdp.invalid','-days','1','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
   def rdp():
    try:
     with listener.accept()[0] as raw:
      raw.settimeout(12);header=exact(raw,4);self.assertEqual(header[:2],b'\x03\x00');request=exact(raw,int.from_bytes(header[2:],'big')-4)
      # Genuine X.224 connection request with an RDP Negotiation Request.
      self.assertEqual(request[1],0xe0);self.assertEqual(request[-8:-4],b'\x01\x00\x08\x00');seen.append(('requested',int.from_bytes(request[-4:],'little')))
      raw.sendall(b'\x03\x00\x00\x13\x0e\xd0\x00\x00\x12\x34\x00\x02\x00\x08\x00\x01\x00\x00\x00')
      with context.wrap_socket(raw,server_side=True) as secure:
       try:seen.append(('after_tls',secure.recv(4096)))
       except (ssl.SSLError,ConnectionResetError):seen.append(('after_tls',b''))
    except (ssl.SSLError,ConnectionResetError):seen.append(('after_tls',b''))
    except Exception as e:errors.append(repr(e))
    finally:done.set()
   peer=threading.Thread(target=rdp,daemon=True);peer.start()
   child=subprocess.Popen(docker+['run','--rm','--pull=never','--name',name,'--network','host','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--tmpfs','/tmp:rw,noexec,nosuid,size=32m','--entrypoint','/opt/guacamole/sbin/guacd',image,'-f','-b','127.0.0.1','-l',str(guac_port),'-p','/tmp/guacd.pid','-L','warning'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   manager=None;opened=None
   try:
    for _ in range(100):
     try:
      with socket.create_connection(('127.0.0.1',guac_port),timeout=.1):break
     except OSError:
      if child.poll() is not None:raise AssertionError('isolated guacd exited')
      time.sleep(.05)
    else:raise AssertionError('isolated guacd did not start')
    (root/'remote-desktop').mkdir();p=root/'remote-desktop/connection.json';p.write_text(json.dumps({'protocol':'rdp','security':'tls','port':listener.getsockname()[1],'username':'synthetic','password':'never-send-this','fingerprint':':'.join(['AB']*32)}));p.chmod(0o600)
    real_connect=socket.create_connection
    def connect(address,timeout):return real_connect(('127.0.0.1',guac_port) if address==('127.0.0.1',14822) else address,timeout)
    with patch('desktop.ROOT',root),patch('desktop.socket.create_connection',side_effect=connect):manager=desktop.Desktop();opened=manager.open('rdp-test',1024,768)
    self.assertTrue(done.wait(15),'RDP TLS peer completed');peer.join(2);self.assertFalse(errors,errors)
    self.assertIn(('requested',1),seen,'TLS-only negotiation, no standard RDP fallback')
    self.assertIn(('after_tls',b''),seen,'wrong certificate pin rejected before MCS or credentials')
   finally:
    if manager and opened:manager.close('rdp-test',opened['id'])
    listener.close();subprocess.run(docker+['rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);child.wait(timeout=10)
 def test_real_vnc_framebuffer_keys_mouse_and_clipboard(self):
  for security in ('none','vnc'):
   with self.subTest(security=security):self.roundtrip(security)
 def roundtrip(self,security):
  image=os.environ['PI_DESKTOP_GUACD_IMAGE'];self.assertIn('@sha256:',image)
  docker=['docker','--host=unix:///var/run/docker.sock'];subprocess.run(docker+['image','inspect',image],stdout=subprocess.DEVNULL,check=True)
  name='pi-console-transport-test-'+secrets.token_hex(6)
  with socket.socket() as reservation:reservation.bind(('127.0.0.1',0));guac_port=reservation.getsockname()[1]
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(3);listener.settimeout(10);self.addCleanup(listener.close)
  port=listener.getsockname()[1];seen=[];errors=[];done=threading.Event()
  def exact(s,n):
   data=b''
   while len(data)<n:
    chunk=s.recv(n-len(data))
    if not chunk:raise EOFError()
    data+=chunk
   return data
  def rfb():
   try:
    # First connection is the policy probe, second is guacd's actual session.
    for probe in (True,False):
     with listener.accept()[0] as s:
      s.settimeout(10);s.sendall(b'RFB 003.008\n');self.assertEqual(exact(s,12),b'RFB 003.008\n');s.sendall(b'\x01'+(b'\x01' if security=='none' else b'\x02'));self.assertEqual(exact(s,1),b'\x01' if security=='none' else b'\x02')
      if probe:continue
      if security=='vnc':
       challenge=bytes(range(16));s.sendall(challenge)
       # Reference OpenSSL DES, using the RFB bit-reversed password key.
       key=bytes(int(f'{b:08b}'[::-1],2) for b in b'password').hex()
       reference=subprocess.run(['openssl','enc','-des-ecb','-provider','legacy','-provider','default','-nopad','-K',key],input=challenge,capture_output=True,check=True).stdout
       self.assertEqual(exact(s,16),reference)
      s.sendall(b'\0\0\0\0');exact(s,1)
      pixel=struct.pack('>BBBBHHHBBB3x',32,24,0,1,255,255,255,16,8,0);label=b'Isolated synthetic desktop'
      s.sendall(struct.pack('>HH',640,480)+pixel+struct.pack('>I',len(label))+label)
      frame_sent=False
      while not done.is_set():
       kind=exact(s,1)[0]
       if kind==0:exact(s,19)
       elif kind==2:header=exact(s,3);exact(s,struct.unpack('>H',header[1:])[0]*4)
       elif kind==3:
        exact(s,9)
        if not frame_sent:s.sendall(struct.pack('>BBH',0,0,1)+struct.pack('>HHHHi',0,0,16,16,0)+b'\x40\x80\xc0\0'*256);frame_sent=True
       elif kind==4:
        data=exact(s,7);seen.append(('key',data[0],struct.unpack('>I',data[3:])[0]))
       elif kind==5:
        data=exact(s,5);seen.append(('mouse',data[0],*struct.unpack('>HH',data[1:])))
       elif kind==6:
        header=exact(s,7);text=exact(s,struct.unpack('>I',header[3:])[0]);seen.append(('clipboard',text));s.sendall(b'\x03\0\0\0'+struct.pack('>I',6)+b'remote');done.set()
       else:raise AssertionError('unexpected RFB client message '+str(kind))
   except (EOFError,OSError):
    if not done.is_set():errors.append('RFB peer ended before clipboard')
   except Exception as e:errors.append(repr(e))
  peer=threading.Thread(target=rfb,daemon=True);peer.start()
  child=subprocess.Popen(docker+['run','--rm','--pull=never','--name',name,'--network','host','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--tmpfs','/tmp:rw,noexec,nosuid,size=32m','--entrypoint','/opt/guacamole/sbin/guacd',image,'-f','-b','127.0.0.1','-l',str(guac_port),'-p','/tmp/guacd.pid','-L','warning'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   for _ in range(100):
    try:
     with socket.create_connection(('127.0.0.1',guac_port),timeout=.1):break
    except OSError:
     if child.poll() is not None:raise AssertionError('isolated guacd exited')
     time.sleep(.05)
   else:raise AssertionError('isolated guacd did not start')
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'remote-desktop').mkdir();p=root/'remote-desktop/connection.json';p.write_text(json.dumps({'protocol':'vnc','security':security,'password':'password' if security=='vnc' else '', 'port':port}));p.chmod(0o600)
    real_connect=socket.create_connection
    def connect(address,timeout):return real_connect(('127.0.0.1',guac_port) if address==('127.0.0.1',14822) else address,timeout)
    with patch('desktop.ROOT',root),patch('desktop.socket.create_connection',side_effect=connect):
     manager=desktop.Desktop();opened=manager.open('test-device',1024,768)
    session=manager.get('test-device',opened['id']);session.sock.settimeout(10)
    try:
     with session.sock.makefile('rb',buffering=0) as stream:
      for _ in range(100):
       event=desktop.receive(stream)
       if event[0]=='size' and event[1]=='0':self.assertEqual(event[2:4],['640','480']);break
       if event[0]=='error':raise AssertionError('real guacd error '+repr(event))
       if event[0]=='sync':session.write(desktop.instruction('sync',event[1]).decode())
      else:raise AssertionError('no framebuffer geometry')
      session.write((desktop.instruction('key',97,1)+desktop.instruction('key',97,0)+desktop.instruction('mouse',10,20,1)+desktop.instruction('mouse',10,20,0)+desktop.instruction('clipboard',0,'text/plain')+desktop.instruction('blob',0,base64.b64encode(b'explicit').decode())+desktop.instruction('end',0)).decode())
      self.assertTrue(done.wait(10),'input reached RFB peer');self.assertIn(('key',1,97),seen);self.assertIn(('key',0,97),seen);self.assertIn(('mouse',1,10,20),seen);self.assertIn(('clipboard',b'explicit'),seen)
    finally:manager.close('test-device',opened['id'])
   peer.join(3);self.assertFalse(errors,errors)
  finally:
   done.set();listener.close();subprocess.run(docker+['rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);child.wait(timeout=10)
if __name__=='__main__':unittest.main()
