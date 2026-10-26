# SPDX-License-Identifier: Apache-2.0
import json,socket,tempfile,threading,unittest,sys,os,subprocess,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from control import Control
from desktop import Desktop
from processes import Processes
from alerts import Alerts
from files import Files
import base64,hashlib
from fixtures import configure_resources
from resource_end import ResourceEnd
configure_resources()

class ApiTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.calls=[];server.CONTROL=Control(Path(self.tmp.name),runner=lambda a:self.calls.append(a) or '',inventory_runner=lambda a:'[]')
  server.ALERTS=Alerts(Path(self.tmp.name)/'alerts.json');server.FILES=Files(Path(self.tmp.name)/'data')
  server.RESOURCE_END=ResourceEnd(server.CONTROL,server.PROCESSES)
  server.DESKTOP=Desktop();self.s=server.LocalServer(('127.0.0.1',0),server.Handler);self.t=threading.Thread(target=self.s.serve_forever,daemon=True);self.t.start()
 def tearDown(self):self.s.shutdown();self.s.server_close();self.t.join();self.tmp.cleanup()
 def request(self,data):
  with socket.create_connection(self.s.server_address) as s:
   s.sendall(data);s.shutdown(socket.SHUT_WR);out=b''
   while chunk:=s.recv(4096):out+=chunk
  return out
 def test_unauthenticated_control_and_logs_denied(self):
  for path in ['/api/status','/api/history?window=5m','/api/resources','/api/logs/proxy','/api/desktop/read/unknown','/api/processes','/api/processes/1','/api/alerts','/api/files/list','/api/files/trash','/api/operations','/api/startup','/api/health-report','/api/backup']:
   r=self.request(('GET '+path+' HTTP/1.1\r\nHost: localhost\r\n\r\n').encode());self.assertIn(b'401 Unauthorized',r)
  self.assertEqual(self.calls,[])
 def test_ambiguous_framing_refused(self):
  for headers in ['Content-Length: 0\r\nContent-Length: 0\r\n','Transfer-Encoding: chunked\r\n','Content-Length: -1\r\n']:
   r=self.request(('POST /api/pair HTTP/1.1\r\nHost: localhost\r\n'+headers+'\r\n').encode());self.assertIn(b'400 Bad Request',r)
 def test_resource_confirmation_requires_pairing_and_does_not_execute_on_prepare(self):
  for path in ['/api/resources/prepare-end','/api/resources/end']:
   r=self.request(('POST '+path+' HTTP/1.1\r\nHost: localhost\r\nContent-Length: 2\r\n\r\n{}').encode());self.assertIn(b'401 Unauthorized',r)
  status,data=self.authenticated('POST','/api/resources/prepare-end',{'resource':'found-missing'})
  self.assertEqual(status,200);self.assertFalse(data['ready']);self.assertEqual(self.calls,[])
  self.assertEqual(self.authenticated('POST','/api/resources/end',{'ticket':'invalid','request':'test-end-request-1234'})[0],409)
 def test_resource_confirmation_and_end_roundtrip_uses_checked_container_identity(self):
  server.CONTROL.resources=lambda:{'resources':[dict(id='found-demo',kind='container',target='demo',name='Demo',state='running',identity='c'*64)]}
  code,prepared=self.authenticated('POST','/api/resources/prepare-end',{'resource':'found-demo'})
  self.assertEqual(code,200);self.assertTrue(prepared['ready']);self.assertEqual(self.calls,[])
  code,op=self.authenticated('POST','/api/resources/end',{'ticket':prepared['ticket'],'request':'test-http-end-1234'})
  self.assertEqual(code,200)
  for _ in range(100):
   code,result=self.authenticated('GET','/api/actions/'+op['id'])
   if result['state'] not in ('queued','running'):break
   time.sleep(.01)
  self.assertEqual(result['state'],'success')
  self.assertEqual(self.calls,[['/usr/bin/docker','--host=unix:///var/run/docker.sock','stop','--time','10','c'*64]])
 def test_pair_once_http(self):
  code=server.CONTROL.new_code();body=json.dumps({'code':code}).encode();raw=b'POST /api/pair HTTP/1.1\r\nHost: localhost\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
  self.assertIn(b'200 OK',self.request(raw));self.assertIn(b'401 Unauthorized',self.request(raw))
 def authenticated(self,method,path,body=None):
  if not hasattr(self,'token'):self.token=server.CONTROL.pair(server.CONTROL.new_code())['token']
  data=json.dumps(body).encode() if body is not None else b''
  raw=(method+' '+path+' HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer '+self.token+'\r\nContent-Length: '+str(len(data))+'\r\n\r\n').encode()+data
  response=self.request(raw);head,payload=response.split(b'\r\n\r\n',1)
  return int(head.split()[1]),json.loads(payload)
 def test_process_http_protection_and_close_test_child(self):
  old=server.PROCESSES;self.addCleanup(setattr,server,'PROCESSES',old)
  status,info=self.authenticated('GET','/api/processes/1');self.assertEqual(status,200);self.assertFalse(info['can_close'])
  status,result=self.authenticated('POST','/api/processes/terminate',{'pid':1,'start':info['start'],'ticket':'0'*64,'request':'test-protected-process'});self.assertEqual(status,403)
  server.PROCESSES=Processes(policy=lambda *args:(True,'测试子进程'))
  child=subprocess.Popen(['/usr/bin/sleep','30']);self.addCleanup(lambda: child.poll() is None and (child.kill(),child.wait()))
  status,info=self.authenticated('GET','/api/processes/'+str(child.pid));self.assertEqual(status,200);self.assertTrue(info['can_close'])
  data={key:info[key] for key in ('pid','start','ticket')};data['request']='test-process-request-123'
  status,op=self.authenticated('POST','/api/processes/terminate',data);self.assertEqual(status,200)
  for _ in range(100):
   status,result=self.authenticated('GET','/api/actions/'+op['id'])
   if result['state'] not in ('queued','running'):break
   time.sleep(.02)
  self.assertEqual(result['state'],'success');self.assertIsNotNone(child.poll())
  status,result=self.authenticated('GET','/api/actions/by-request/test-process-request-123');self.assertTrue(result['found']);self.assertEqual(result['operation']['id'],op['id'])
 def test_alert_backup_schema_and_no_credentials(self):
  status,data=self.authenticated('GET','/api/backup');self.assertEqual(status,200);self.assertEqual(set(data),{'schema','alert_rules'})
  status,result=self.authenticated('POST','/api/backup',{'schema':1,'alert_rules':data['alert_rules'],'token':'bad'});self.assertEqual(status,400)
  status,result=self.authenticated('POST','/api/backup',data);self.assertEqual(status,200)
  for path in ['/api/alerts','/api/operations','/api/startup','/api/health-report']:
   status,data=self.authenticated('GET',path);self.assertEqual(status,200)
 def test_file_roundtrip_and_trash_via_authenticated_api(self):
  status,start=self.authenticated('POST','/api/files/upload/start',{'directory':'','name':'中文 file.txt','size':5});self.assertEqual(status,200)
  status,result=self.authenticated('POST','/api/files/upload/chunk',{'id':start['id'],'offset':0,'data':'aGVsbG8='});self.assertEqual(status,200)
  status,op=self.authenticated('POST','/api/files/upload/finish',{'id':start['id'],'sha256':hashlib.sha256(b'hello').hexdigest(),'request':'test-file-upload-finish'});self.assertEqual(status,200)
  for _ in range(100):
   status,result=self.authenticated('GET','/api/actions/'+op['id'])
   if result['state'] not in ('queued','running'):break
   time.sleep(.01)
  self.assertEqual(result['state'],'success')
  status,info=self.authenticated('POST','/api/files/stat',{'path':'中文 file.txt'});self.assertEqual(status,200)
  status,result=self.authenticated('POST','/api/files/read',{'path':info['path'],'offset':0,'ticket':info['ticket']});self.assertEqual(base64.b64decode(result['data']),b'hello')
  status,result=self.authenticated('POST','/api/files/list',{'path':'../'});self.assertEqual(status,400)
  status,result=self.authenticated('POST','/api/startup',{'resource':'proxy','action':'disable','request':'test-no-core-startup'});self.assertEqual(status,400)
 def test_invalid_history_window(self):
  self.assertEqual(self.authenticated('GET','/api/history?window=999m')[0],400)
if __name__=='__main__':unittest.main()
