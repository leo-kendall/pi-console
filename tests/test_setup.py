# SPDX-License-Identifier: Apache-2.0
import json,socket,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import server
from control import Control


class SetupApiTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.calls=[]
  control=Control(self.root/'control',runner=lambda a:self.calls.append(a))
  self.patch=patch.object(server,'CONTROL',control);self.patch.start();self.addCleanup(self.patch.stop)
  self.control=control;self.http=server.LocalServer(('127.0.0.1',0),server.Handler)
  self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.http.shutdown();self.http.server_close();self.thread.join()
 def request(self,path,method='GET',token=''):
  raw=(method+' '+path+' HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer '+token+'\r\nContent-Length: 0\r\n\r\n').encode()
  with socket.create_connection(self.http.server_address) as stream:
   stream.sendall(raw);stream.shutdown(socket.SHUT_WR);parts=[]
   while data:=stream.recv(4096):parts.append(data)
  head,body=b''.join(parts).split(b'\r\n\r\n',1)
  return int(head.split()[1]),json.loads(body)
 def test_identity_is_public_and_contains_no_host_or_auth_configuration(self):
  code,data=self.request('/api/connection')
  self.assertEqual(code,200);self.assertEqual(data,{'app':'pi-console','protocol':1})
  self.assertEqual(self.calls,[])
 def test_configuration_checks_require_pairing_and_reject_writes(self):
  self.assertEqual(self.request('/api/setup')[0],401)
  token=self.control.pair(self.control.new_code())['token']
  code,data=self.request('/api/setup',token=token)
  self.assertEqual(code,200);self.assertIsInstance(data['checks'],list)
  self.assertEqual(self.request('/api/setup','POST',token)[0],404)
  self.assertEqual(self.request('/api/connection','POST',token)[0],404)
  self.assertEqual(self.calls,[])


class SetupReportTests(unittest.TestCase):
 def report(self,root):
  from setup_checks import report
  return report(root,resources={},admin_ready=False)
 def test_missing_optional_features_are_not_reported_as_connection_failure(self):
  with tempfile.TemporaryDirectory() as d:
   data=self.report(Path(d));checks={c['id']:c for c in data['checks']}
  self.assertEqual(checks['desktop']['state'],'optional')
  self.assertEqual(checks['process_admin']['state'],'optional')
  self.assertEqual(checks['resources']['state'],'optional')
 def test_desktop_configuration_is_checked_without_echoing_secrets_or_opening_a_session(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'remote-desktop/connection.json';p.parent.mkdir()
   p.write_text(json.dumps({'username':'private-person','password':'secret-desktop-password','fingerprint':':'.join(['ab']*32)}));p.chmod(0o600)
   with patch('socket.create_connection',side_effect=AssertionError('must not open desktop')):
    data=self.report(root)
   desktop=next(c for c in data['checks'] if c['id']=='desktop')
   self.assertEqual(desktop['state'],'configured')
   self.assertNotIn('private-person',json.dumps(data));self.assertNotIn('secret-desktop-password',json.dumps(data));self.assertNotIn(str(root),json.dumps(data))
   p.chmod(0o644);self.assertEqual(next(c for c in self.report(root)['checks'] if c['id']=='desktop')['state'],'attention')
   p.chmod(0o600);p.write_text('{broken');self.assertEqual(next(c for c in self.report(root)['checks'] if c['id']=='desktop')['state'],'attention')
 def test_symlink_and_oversized_desktop_configuration_are_not_read_as_ready(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'remote-desktop/connection.json';p.parent.mkdir();other=root/'private';other.write_text('{}');p.symlink_to(other)
   self.assertEqual(next(c for c in self.report(root)['checks'] if c['id']=='desktop')['state'],'attention')
   p.unlink();p.write_text('x'*65537);p.chmod(0o600)
   self.assertEqual(next(c for c in self.report(root)['checks'] if c['id']=='desktop')['state'],'attention')
