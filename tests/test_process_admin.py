# SPDX-License-Identifier: Apache-2.0
import importlib.util,os,signal,subprocess,sys,time,unittest,tempfile,py_compile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from processes import Processes
from process_identity import read_process,fingerprint
from process_policy import process_policy
from control import ApiError
p=Path(__file__).resolve().parents[1]/'process-control/helper.py'
s=importlib.util.spec_from_file_location('process_admin_helper',p);helper=importlib.util.module_from_spec(s);s.loader.exec_module(helper);helper.fingerprint=fingerprint

class ProcessAdminTests(unittest.TestCase):
 def record(self,**changes):
  p=dict(pid=3456,ppid=1,name='immich',exe='/usr/bin/node',uids=[0]*4,cgroup='/system.slice/docker-'+'a'*64+'.scope',flags=0,state='S',start=123,rss_bytes=1000,virtual_bytes=2000,threads=2)
  p.update(changes);return p
 def manager(self,p):
  m=Processes();m.uid=1000;m.read=lambda pid:dict(p);m.parents=lambda p:{};m.snapshot=lambda:{'processes':[],'memory_total':8*1024**3};return m
 def test_admin_requirement_is_separate_from_system_read_only(self):
  m=self.manager(self.record())
  with patch('processes.helper_ready',return_value=False):
   d=m.detail('device',3456)
   self.assertTrue(d['can_close']);self.assertFalse(d['control_available']);self.assertTrue(d['requires_admin']);self.assertEqual(d['category'],'application');self.assertIsNone(d['ticket'])
 def test_privileged_identity_is_used_for_ticket_and_executor(self):
  p=self.record();m=self.manager(p)
  with patch('processes.helper_ready',return_value=True),patch('processes.invoke',side_effect=lambda action,*args:dict(p) if action=='read' else {'exited':True}) as invoke:
   d=m.detail('device',3456);self.assertTrue(d['control_available']);m.terminate('device',3456,123,d['ticket'])
   self.assertIn(('terminate',3456,123,fingerprint(p)),[call.args for call in invoke.call_args_list])
 def test_root_helper_rejects_core_before_opening_pidfd(self):
  p=self.record(pid=1,name='systemd')
  with patch.object(os,'close') as close:
   with self.assertRaises(RuntimeError):helper.terminate(1,123,fingerprint(p),lambda pid:p,process_policy,pidfd_open=lambda pid:self.fail('protected PID opened'))
   close.assert_not_called()
 def test_root_helper_rechecks_identity_and_role_after_open(self):
  original=self.record();changed=self.record(cgroup='/system.slice/systemd-logind.service');rows=iter([original,changed]);fd=os.open('/dev/null',os.O_RDONLY)
  with self.assertRaises(RuntimeError):helper.terminate(3456,123,fingerprint(original),lambda pid:next(rows),process_policy,pidfd_open=lambda pid:fd,send_signal=lambda *args:self.fail('role change was signalled'))
  with self.assertRaises(OSError):os.fstat(fd)
 def test_root_helper_uses_actual_pidfd_and_only_sigterm_on_test_child(self):
  child=subprocess.Popen(['/usr/bin/sleep','30'])
  try:
   p=read_process('/proc',child.pid)
   result=helper.terminate(child.pid,p['start'],fingerprint(p),lambda pid:read_process('/proc',pid),process_policy)
   self.assertTrue(result['sent']);self.assertTrue(result['exited']);child.wait(timeout=2);self.assertEqual(child.returncode,-signal.SIGTERM)
  finally:
   if child.poll() is None:child.kill();child.wait()
 def test_admin_ticket_cannot_be_reused_by_another_device(self):
  p=self.record();m=self.manager(p)
  with patch('processes.helper_ready',return_value=True),patch('processes.invoke',return_value=p):
   ticket=m.signature('one',p)
   with self.assertRaises(ApiError):m.validate('two',p['pid'],p['start'],ticket)
 def test_checked_source_is_used_even_with_a_matching_poisoned_bytecode_cache(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'module.py';path.write_text('VALUE="EVIL"\n');stamp=path.stat().st_mtime_ns
   py_compile.compile(str(path),doraise=True)
   path.write_text('VALUE="SAFE"\n');os.utime(path,ns=(stamp,stamp))
   with patch.object(helper,'safe',return_value=None):self.assertEqual(helper.load_source(path)['VALUE'],'SAFE')
if __name__=='__main__':unittest.main()
