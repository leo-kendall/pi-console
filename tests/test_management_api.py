# SPDX-License-Identifier: Apache-2.0
"""HTTP boundary checks use only disposable identities and file spaces."""
import base64,hashlib,json,socket,tempfile,threading,time,unittest
from pathlib import Path
import server
from control import Control
from desktop import Desktop
from file_spaces import FileSpaces

class ManagementApiTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.previous={k:getattr(server,k) for k in ('CONTROL','DESKTOP','FILES','LIVE_LOGS')};self.addCleanup(self.restore)
  self.control=server.CONTROL=Control(self.root/'control',runner=lambda args: (_ for _ in ()).throw(AssertionError('No live commands allowed')))
  from live_logs import LiveLogs
  server.LIVE_LOGS=LiveLogs(self.control)
  server.DESKTOP=Desktop();external=self.root/'external';external.mkdir();(external/'sample.txt').write_text('read only')
  server.FILES=FileSpaces(self.root/'data',{'media':{'name':'媒体','path':str(external),'writable':False}})
  self.admin=self.pair('admin');self.viewer=self.pair('viewer');self.operator=self.pair('operator')
  self.http=server.LocalServer(('127.0.0.1',0),server.Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
 def restore(self):
  for name,value in self.previous.items():setattr(server,name,value)
 def tearDown(self):self.http.shutdown();self.http.server_close();self.thread.join()
 def pair(self,role):return self.control.pair(self.control.new_code(role))
 def call(self,device,method,path,data=None):
  body=json.dumps(data).encode() if data is not None else b''
  headers=f'{method} {path} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {device["token"]}\r\nContent-Length: {len(body)}\r\n\r\n'.encode()
  with socket.create_connection(self.http.server_address,timeout=4) as conn:
   conn.sendall(headers+body);conn.shutdown(socket.SHUT_WR);response=b''
   while chunk:=conn.recv(65536):response+=chunk
  head,payload=response.split(b'\r\n\r\n',1);return int(head.split()[1]),json.loads(payload)
 def test_device_privileges_and_revocation_are_enforced_at_http_boundary(self):
  self.assertEqual(self.call(self.viewer,'GET','/api/session')[1]['role'],'viewer')
  self.assertEqual(self.call(self.viewer,'GET','/api/devices')[0],403)
  self.assertEqual(self.call(self.viewer,'POST','/api/devices/role',{'device':self.viewer['device'],'role':'admin'})[0],403)
  self.assertEqual(self.call(self.viewer,'POST','/api/devices/rename',{'device':self.viewer['device'],'name':'只读手机'})[0],200)
  self.assertEqual(self.call(self.operator,'POST','/api/devices/pair-code',{'role':'admin'})[0],403)
  self.assertEqual(self.call(self.admin,'POST','/api/devices/revoke',{'device':self.viewer['device']})[0],200)
  self.assertEqual(self.call(self.viewer,'GET','/api/session')[0],401)
 def test_grants_are_bound_to_container_identity_and_revocation_narrows_actions(self):
  rows=[dict(id='found-demo',kind='container',target='demo',name='Demo',identity='b'*64)]
  self.control.grants.catalog=lambda:rows
  data={'resource':'found-demo','rights':['stop','logs'],'identity':'b'*64}
  self.assertEqual(self.call(self.operator,'POST','/api/grants/set',data)[0],403)
  self.assertEqual(self.call(self.admin,'POST','/api/grants/set',data)[0],200)
  self.assertEqual(self.control.command('found-demo','stop')[-1],'b'*64)
  rows[0]['identity']='c'*64
  self.assertEqual(self.call(self.admin,'POST','/api/grants/set',data)[0],409)
  self.assertEqual(self.call(self.admin,'POST','/api/grants/remove',{'resource':'found-demo'})[0],200)
  self.assertEqual(self.call(self.viewer,'GET','/api/grants')[0],403)
 def test_named_roots_resume_offsets_and_repeated_chunks_through_real_http(self):
  self.assertEqual(len(self.call(self.viewer,'GET','/api/files/roots')[1]['roots']),2)
  self.assertEqual(self.call(self.viewer,'POST','/api/files/list',{'root':'media','path':''})[1]['items'][0]['name'],'sample.txt')
  self.assertEqual(self.call(self.viewer,'POST','/api/files/trash/list',{'root':'media'})[0],200)
  self.assertEqual(self.call(self.viewer,'POST','/api/files/trash',{'root':'media','path':'sample.txt','ticket':'invalid','request':'viewer-trash-attempt'})[0],403)
  start={'root':'media','directory':'','name':'blocked.txt','size':6,'request':'file-test-upload-0001'}
  self.assertEqual(self.call(self.operator,'POST','/api/files/upload/start',start)[0],403)
  start['root']='default'
  self.assertEqual(self.call(self.viewer,'POST','/api/files/upload/start',start)[0],403)
  status,upload=self.call(self.operator,'POST','/api/files/upload/start',start);self.assertEqual(status,200)
  chunk={'root':'default','id':upload['id'],'offset':0,'data':base64.b64encode(b'abcdef').decode()}
  for _ in range(2):self.assertEqual(self.call(self.operator,'POST','/api/files/upload/chunk',chunk)[1]['offset'],6)
  self.assertEqual(self.call(self.viewer,'POST','/api/files/upload/status',{'id':upload['id']})[0],404)
  self.assertEqual(self.call(self.operator,'POST','/api/files/upload/start',start)[1]['offset'],6)
  status,op=self.call(self.operator,'POST','/api/files/upload/finish',{'id':upload['id'],'sha256':hashlib.sha256(b'abcdef').hexdigest(),'request':'finish-api-upload-0001'})
  self.assertEqual(status,200)
  for _ in range(100):
   op=self.call(self.operator,'GET','/api/actions/'+op['id'])[1]
   if op['state'] not in ('queued','running'):break
   time.sleep(.01)
  self.assertEqual(op['state'],'success');self.assertEqual((self.root/'data/files/blocked.txt').read_bytes(),b'abcdef')
 def test_live_logs_router_allows_viewers_but_rechecks_device_identity(self):
  self.control.grants.catalog=lambda:[dict(id='found-log',kind='container',target='log',identity='d'*64,name='Log')]
  self.control.grants.set(self.admin['device'],'found-log',['logs'],'d'*64)
  self.control.runner=lambda args:'INFO isolated test\n'
  self.assertEqual(self.call(self.viewer,'POST','/api/logs/tail',{'resource':'found-log'})[0],200)
  self.control.revoke_device(self.admin['device'],self.viewer['device'])
  self.assertEqual(self.call(self.viewer,'POST','/api/logs/tail',{'resource':'found-log'})[0],401)
  self.assertEqual(self.call(self.admin,'POST','/api/processes/history',{'pid':'invalid','start':0})[0],400)
