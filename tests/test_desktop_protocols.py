# SPDX-License-Identifier: Apache-2.0
"""Real loopback peers exercise protocol selection, auth policy, and isolation."""
import io,json,socket,threading,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import desktop
from control import ApiError

PIN=':'.join(['AB']*32)
class ProtocolTests(unittest.TestCase):
 def test_capabilities_are_sanitized_and_configuration_only(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'remote-desktop').mkdir();p=root/'remote-desktop/connection.json'
   self.assertEqual(desktop.capabilities(root)['configuration']['state'],'unconfigured')
   p.write_text(json.dumps({'protocol':'vnc','security':'vnc','password':'SECRET','port':5901}));p.chmod(0o600)
   result=desktop.capabilities(root)
   self.assertEqual(result['configuration'],{'state':'configured','protocol':'vnc','security':'vnc','host':'127.0.0.1','port':5901,'live_verified':False})
   self.assertNotIn('SECRET',json.dumps(result));self.assertNotIn('password',json.dumps(result))
   p.chmod(0o644);self.assertEqual(desktop.capabilities(root)['configuration']['state'],'invalid')
 def test_legacy_rdp_and_explicit_tls_require_pin(self):
  p=desktop.connection_parameters({'username':'u','password':'p','fingerprint':PIN},1024,768)
  self.assertEqual(p['protocol'],'rdp');self.assertEqual(p['hostname'],'127.0.0.1');self.assertEqual(p['security'],'nla');self.assertEqual(p['ignore-cert'],'false')
  p=desktop.connection_parameters({'protocol':'rdp','host':'::1','port':3390,'security':'tls','username':'u','password':'p','fingerprint':PIN},1024,768)
  self.assertEqual((p['hostname'],p['port'],p['security']),('::1','3390','tls'))
  for c in ({'protocol':'rdp','fingerprint':''},{'protocol':'ssh'},{'protocol':'vnc','host':'8.8.8.8'}, {'protocol':'vnc','host':'localhost'}, {'protocol':'vnc','port':True},{'protocol':'vnc','port':65536},{'protocol':'vnc','security':'vencrypt'},{'protocol':'rdp','security':'rdp','fingerprint':PIN}):
   with self.subTest(config=c),self.assertRaises(ApiError):desktop.connection_parameters(c,1024,768)
 def test_vnc_password_policy_and_no_credential_disclosure(self):
  p=desktop.connection_parameters({'protocol':'vnc','security':'vnc','password':'12345678','port':5901},1024,768)
  self.assertEqual((p['port'],p['password']),('5901','12345678'));self.assertNotIn('ignore-cert',p)
  for password in ('','123456789','é'):
   with self.assertRaises(ApiError) as caught:desktop.connection_parameters({'protocol':'vnc','security':'vnc','password':password},1024,768)
   self.assertNotIn(password+'SECRET',str(caught.exception))
  p=desktop.connection_parameters({'protocol':'vnc','security':'none'},1024,768);self.assertEqual(p['password'],'')
 def test_guacamole_unicode_length_and_malformed_frame_are_bounded(self):
  self.assertEqual(desktop.receive(io.BytesIO('4.args,2.中🚀;'.encode())),['args','中🚀'])
  for frame in (b'.;',b'1.\xff;',b'1.\xe4;'):
   with self.assertRaises(ApiError):desktop.receive(io.BytesIO(frame))
 def test_private_config_rejects_symlink_world_access_and_bad_json(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'config.json';p.write_text('{"protocol":"vnc","security":"none"}');p.chmod(0o600)
   self.assertEqual(desktop.load_connection(p)['protocol'],'vnc')
   link=Path(t)/'link';link.symlink_to(p)
   with self.assertRaises(ApiError):desktop.load_connection(link)
   p.chmod(0o644)
   with self.assertRaises(ApiError):desktop.load_connection(p)
   p.chmod(0o600);p.write_text('bad SECRET')
   with self.assertRaises(ApiError) as caught:desktop.load_connection(p)
   self.assertNotIn('SECRET',str(caught.exception))
 def vnc_peer(self,types,chosen=None,version=b'RFB 003.008\n'):
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();self.addCleanup(listener.close);errors=[];seen=[]
  def serve():
   try:
    with listener.accept()[0] as s:
     s.settimeout(3);s.sendall(version);seen.append(s.recv(12))
     if version==b'RFB 003.003\n':s.sendall(int(types[0]).to_bytes(4,'big'))
     else:
      s.sendall(bytes([len(types),*types]));seen.append(s.recv(1))
   except Exception as e:errors.append(e)
  th=threading.Thread(target=serve);th.start();self.addCleanup(lambda:th.join(4))
  return listener.getsockname()[1],seen,errors,th
 def test_actual_vnc_version_and_security_negotiation(self):
  for version in (b'RFB 003.003\n',b'RFB 003.007\n',b'RFB 003.008\n'):
   with self.subTest(version=version):
    port,seen,errors,th=self.vnc_peer([2],version=version)
    result=desktop.probe_vnc({'hostname':'127.0.0.1','port':str(port),'security':'vnc'})
    th.join(4);self.assertFalse(errors);self.assertEqual(result['security'],'vnc');self.assertEqual(seen[0],version)
    if version!=b'RFB 003.003\n':self.assertEqual(seen[1],b'\x02')
 def test_vnc_does_not_downgrade_auth_or_accept_tls_variants(self):
  for types in ([1],[19],[18],[16],[1,19],[1,2],[2,19]):
   port,seen,errors,th=self.vnc_peer(types)
   with self.assertRaises(ApiError) as caught:desktop.probe_vnc({'hostname':'127.0.0.1','port':str(port),'security':'vnc'})
   self.assertIn('VNC',str(caught.exception));th.join(4);self.assertFalse(errors)
 def test_guacd_real_loopback_for_both_protocols_and_owners(self):
  for protocol in ('rdp','vnc'):
   listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();self.addCleanup(listener.close);received=[];errors=[]
   def serve():
    try:
     with listener.accept()[0] as s:
      s.settimeout(4)
      with s.makefile('rb',buffering=0) as f:
       received.append(desktop.receive(f));s.sendall(desktop.instruction('args','hostname','port','password','cert-fingerprints','VERSION_1_5_0'))
       for _ in range(6):received.append(desktop.receive(f))
       s.sendall(desktop.instruction('ready','session'));received.append(desktop.receive(f));s.sendall(desktop.instruction('sync','1'))
    except Exception as e:errors.append(e)
   th=threading.Thread(target=serve);th.start()
   with tempfile.TemporaryDirectory() as t:
    root=Path(t);(root/'remote-desktop').mkdir();p=root/'remote-desktop/connection.json';p.write_text(json.dumps({'protocol':protocol,'security':'none' if protocol=='vnc' else 'nla','username':'u','password':'p' if protocol=='rdp' else '', 'fingerprint':PIN}));p.chmod(0o600)
    real_connect=socket.create_connection
    def connect(address,timeout):
     self.assertEqual(address,('127.0.0.1',14822));return real_connect(listener.getsockname(),timeout)
    with patch('desktop.ROOT',root),patch('desktop.socket.create_connection',side_effect=connect),patch('desktop.probe_vnc',return_value={'security':'none'}):
     m=desktop.Desktop();result=m.open('alice',1024,768)
    with self.assertRaises(ApiError):m.get('mallory',result['id'])
    m.get('alice',result['id']).write('3.key,1.1,2.65;');self.assertEqual(m.get('alice',result['id']).read(),'4.sync,1.1;');m.close('alice',result['id'])
   th.join(5);self.assertFalse(errors);self.assertEqual(received[0],['select',protocol]);self.assertEqual(received[-1],['key','1','65']);self.assertEqual(received[-2][-1],'VERSION_1_5_0')
if __name__=='__main__':unittest.main()
