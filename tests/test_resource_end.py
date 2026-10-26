# SPDX-License-Identifier: Apache-2.0
import copy,tempfile,time,unittest
from pathlib import Path
from control import Control,ApiError
from resource_end import ResourceEnd,annotate_inventory

class ProcessBoundary:
 def __init__(self):self.closed=[];self.allowed=True;self.available=True;self.group="/system.slice/worker.service"
 def detail(self,owner,pid):return dict(pid=pid,start=123,cgroup=self.group,can_close=self.allowed,control_available=self.available,ticket='p'*64,impact='')
 def validate(self,owner,pid,start,ticket):
  if not self.allowed:raise ApiError('系统核心进程',403)
  return {}
 def terminate(self,owner,pid,start,ticket):self.validate(owner,pid,start,ticket);self.closed.append(pid)

class ResourceEndTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.commands=[]
  self.control=Control(Path(self.tmp.name),runner=lambda args:self.commands.append(args) or '')
  self.rows=[dict(id='found-app',kind='container',target='photos',name='Photos',state='running',identity='a'*64,control=False,logs=False,configured=False)]
  self.control.resources=lambda:dict(resources=copy.deepcopy(self.rows))
  self.props='Id=worker.service\nNames=worker.service\nLoadState=loaded\nActiveState=active\nMainPID=3456\nInvocationID=abc\nControlGroup=/system.slice/worker.service\nRefuseManualStop=no\nRequiredBy=\nBoundBy=\nConsistsOf=\nPropagatesStopTo=\n'
  self.processes=ProcessBoundary();self.manager=ResourceEnd(self.control,self.processes,reader=lambda args:self.props)
 def wait(self,op):
  for _ in range(100):
   op=self.control.operation('phone',op['id'])
   if op['state'] not in ('queued','running'):return op
   time.sleep(.01)
  self.fail('test operation did not finish')
 def test_new_container_can_be_confirmed_and_stopped_without_config_edit(self):
  prepared=self.manager.prepare('phone','found-app');self.assertTrue(prepared['ready'])
  op=self.manager.submit('phone',prepared['ticket'],'resource-end-1234');self.assertEqual(self.wait(op)['state'],'success')
  self.assertEqual(self.commands,[['/usr/bin/docker','--host=unix:///var/run/docker.sock','stop','--time','10','a'*64]])
 def test_other_phone_tampering_expiry_and_reused_ticket_are_rejected(self):
  p=self.manager.prepare('phone','found-app')
  for owner,ticket in [('other',p['ticket']),('phone',p['ticket']+'x')]:
   with self.assertRaises(ApiError):self.manager.submit(owner,ticket,'resource-end-1234')
  op=self.manager.submit('phone',p['ticket'],'resource-end-1234');self.wait(op)
  self.assertEqual(self.manager.submit('phone',p['ticket'],'resource-end-1234')['id'],op['id'])
  with self.assertRaises(ApiError):self.manager.submit('phone',p['ticket'],'resource-end-5678')
  self.manager.clock=lambda:time.time()+600
  with self.assertRaises(ApiError):self.manager.submit('phone',p['ticket'],'resource-end-9999')
  self.assertEqual(len(self.commands),1)
 def test_name_reuse_with_a_different_container_identity_is_rejected(self):
  p=self.manager.prepare('phone','found-app');self.rows[0]['identity']='b'*64
  with self.assertRaises(ApiError):self.manager.submit('phone',p['ticket'],'resource-end-1234')
  self.assertEqual(self.commands,[])
 def service(self,kind='user',target='worker.service'):
  self.processes.group='/user.slice/user-1000.slice/worker.service' if kind=='user' else '/system.slice/worker.service'
  self.props=self.props.replace('ControlGroup=/system.slice/worker.service','ControlGroup='+self.processes.group)
  self.rows=[dict(id='found-worker',kind=kind,target=target,name=target,state='active/running',control=False,logs=False,configured=False)]
 def test_ordinary_user_service_is_stopped_after_confirmation(self):
  self.service();self.processes.detail=lambda owner,pid:dict(pid=pid,start=123,cgroup='/user.slice/user-1000.slice/worker.service',can_close=True,control_available=True,ticket='p'*64,impact='')
  p=self.manager.prepare('phone','found-worker');self.assertEqual(p['mode'],'user-stop')
  self.assertEqual(self.wait(self.manager.submit('phone',p['ticket'],'resource-end-1234'))['state'],'success')
  self.assertEqual(self.commands,[['/usr/bin/systemctl','--user','stop','--','worker.service']])
 def test_non_core_system_application_uses_existing_pid_checked_executor(self):
  self.service('system');p=self.manager.prepare('phone','found-worker');self.assertEqual(p['mode'],'process-terminate')
  self.assertEqual(self.wait(self.manager.submit('phone',p['ticket'],'resource-end-1234'))['state'],'success')
  self.assertEqual(self.processes.closed,[3456]);self.assertEqual(self.commands,[])
 def test_core_alias_core_pid_foreign_pid_and_missing_admin_are_rejected(self):
  self.service('system')
  for props in [self.props.replace('Names=worker.service','Names=worker.service systemd-logind.service'),self.props.replace('RefuseManualStop=no','RefuseManualStop=yes')]:
   self.manager.reader=lambda args,p=props:p
   with self.assertRaises(ApiError):self.manager.prepare('phone','found-worker')
  self.manager.reader=lambda args:self.props
  self.processes.allowed=False
  with self.assertRaises(ApiError):self.manager.prepare('phone','found-worker')
  self.processes.allowed=True;self.processes.available=False
  with self.assertRaises(ApiError):self.manager.prepare('phone','found-worker')
  self.processes.available=True;self.processes.detail=lambda *args:dict(cgroup='/system.slice/other.service',can_close=True,control_available=True,pid=3456,start=123,ticket='p'*64,impact='')
  with self.assertRaises(ApiError):self.manager.prepare('phone','found-worker')
 def test_user_service_with_stop_dependants_ends_only_main_process(self):
  self.service();self.props=self.props.replace('RequiredBy=\n','RequiredBy=important.target\n')
  p=self.manager.prepare('phone','found-worker');self.assertEqual(p['mode'],'process-terminate')
 def test_changed_unit_activation_is_rejected_before_submission(self):
  self.service('system');p=self.manager.prepare('phone','found-worker');self.props=self.props.replace('InvocationID=abc','InvocationID=def')
  with self.assertRaises(ApiError):self.manager.submit('phone',p['ticket'],'resource-end-1234')
 def test_worker_rechecks_identity_after_queueing(self):
  p=self.manager.prepare('phone','found-app');jobs=[]
  self.control.enqueue=lambda owner,rid,action,request,job:jobs.append(job) or {'id':'test'}
  self.manager.submit('phone',p['ticket'],'resource-end-1234');self.rows[0]['identity']='b'*64
  with self.assertRaises(ApiError):jobs[0]()
  self.assertEqual(self.commands,[])
 def test_inventory_flags_foundational_services_read_only(self):
  self.service('system','systemd-logind.service');data=annotate_inventory({'resources':self.rows})
  self.assertFalse(data['resources'][0]['can_authorize_end'])
  self.rows[0]['target']='worker.service';self.assertTrue(annotate_inventory({'resources':self.rows})['resources'][0]['can_authorize_end'])
 def test_system_application_in_a_custom_slice_is_supported(self):
  self.service('system');self.props=self.props.replace('/system.slice/worker.service','/apps.slice/worker.service');self.processes.group='/apps.slice/worker.service'
  self.assertEqual(self.manager.prepare('phone','found-worker')['mode'],'process-terminate')
 def test_expired_authorization_is_not_executed_by_a_deferred_worker(self):
  now=[1000.];self.manager.clock=lambda:now[0];p=self.manager.prepare('phone','found-app');jobs=[]
  self.control.enqueue=lambda owner,rid,action,request,job:jobs.append(job) or {'id':'test'}
  self.manager.submit('phone',p['ticket'],'resource-end-1234');now[0]=1300.
  with self.assertRaises(ApiError):jobs[0]()
  self.assertEqual(self.commands,[])
 def test_replay_that_waited_past_expiry_cannot_bypass_consumed_nonce(self):
  now=[1000.];self.manager.clock=lambda:now[0];p=self.manager.prepare('phone','found-app');jobs=[]
  self.control.enqueue=lambda owner,rid,action,request,job:jobs.append(job) or {'id':'test'}
  self.manager.submit('phone',p['ticket'],'resource-end-1234');now[0]=1119.
  def delayed_lookup(owner,request):now[0]=1130.;return {'found':False}
  self.control.by_request=delayed_lookup
  with self.assertRaises(ApiError):self.manager.submit('phone',p['ticket'],'resource-end-5678')
  self.assertEqual(len(jobs),1)
 def test_exact_expiry_boundary_is_already_expired(self):
  now=[1000.];self.manager.clock=lambda:now[0];p=self.manager.prepare('phone','found-app');jobs=[]
  self.control.enqueue=lambda owner,rid,action,request,job:jobs.append(job) or {'id':'test'}
  self.manager.submit('phone',p['ticket'],'resource-end-1234');now[0]=1120.
  with self.assertRaises(ApiError):self.manager.submit('phone',p['ticket'],'resource-end-5678')
  self.assertEqual(len(jobs),1)
