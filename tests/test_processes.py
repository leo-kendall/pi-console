# SPDX-License-Identifier: Apache-2.0
import os,sys,signal,subprocess,time,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from processes import Processes,process_policy,parse_stat
from control import ApiError
class ProcessTests(unittest.TestCase):
 def record(self,**changes):
  p=dict(pid=1234,ppid=22,start=100,uids=[1000]*4,exe='/snap/firefox/9035/usr/lib/firefox/firefox',cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-abc.scope',trusted_exe=True,state='S',name='firefox',flags=0)
  p.update(changes);return p
 def test_owner_apps_and_scripts_do_not_need_an_executable_allowlist(self):
  self.assertTrue(process_policy(self.record(),{},1000,set())[0])
  self.assertTrue(process_policy(self.record(),{22:self.record(pid=22,name='gnome-shell',exe='/usr/bin/gnome-shell')},1000,set())[0])
  for changes in [dict(exe='/usr/bin/python3'),dict(exe='/home/demo/.venv/bin/python',trusted_exe=False),dict(exe='/usr/bin/flameshot'),dict(exe='/usr/bin/cc-switch'),dict(exe='/home/demo/my-app',trusted_exe=False),dict(exe='/usr/bin/sleep',cgroup='/user.slice/user-1000.slice/session-123.scope'),dict(exe='/usr/bin/node',cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/my-worker.service'),dict(exe='/usr/bin/localsearch-3',cgroup='/user.slice/user-1000.slice/user@1000.service/background.slice/localsearch-3.service')]:
   with self.subTest(changes=changes):self.assertTrue(process_policy(self.record(**changes),{},1000,set())[0])
  for changes in [dict(state='Z')]:
   self.assertFalse(process_policy(self.record(**changes),{},1000,set())[0])
  self.assertTrue(process_policy(self.record(),{},1000,{1234})[0])
 def test_app_workers_and_codex_workers_can_close(self):
  parent=self.record(pid=22)
  self.assertTrue(process_policy(self.record(),{22:parent},1000,set())[0])
  parent=self.record(pid=22,exe='/usr/bin/codex',name='codex')
  self.assertTrue(process_policy(self.record(),{22:parent},1000,set())[0])
 def test_only_os_and_desktop_foundations_remain_read_only(self):
  for changes in [dict(exe='/usr/bin/gnome-shell',name='gnome-shell',cgroup='/user.slice/user-1000.slice/user@1000.service/session.slice/org.gnome.Shell@ubuntu.service'),dict(exe='/usr/bin/dbus-daemon',cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/dbus.service')]:
   with self.subTest(changes=changes):self.assertFalse(process_policy(self.record(**changes),{},1000,set())[0])
 def test_terminal_parent_does_not_block_an_independent_user_job(self):
  for name in ['bash','sshd','tmux: server']:
   parent=self.record(pid=22,name=name,exe='/usr/bin/'+name.split(':')[0])
   self.assertTrue(process_policy(self.record(exe='/usr/bin/python3',name='python3'),{22:parent},1000,set())[0])
 def test_optional_desktop_settings_database_can_close(self):
  p=self.record(exe='/usr/libexec/dconf-service',name='dconf-service',cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/dconf.service')
  self.assertTrue(process_policy(p,{},1000,set())[0])
 def test_ticket_is_refused_if_process_moves_into_a_protected_unit(self):
  manager=Processes();original=self.record(exe='/usr/bin/python3',name='python3')
  ticket=manager.signature('test-owner',original)
  # Identity survives, but the executable's role changes to infrastructure.
  manager.read=lambda pid:dict(original,cgroup='/system.slice/systemd-logind.service')
  manager.parents=lambda p:{};manager.protected=lambda:set()
  manager.uid=1000
  with self.assertRaises(ApiError):manager.validate('test-owner',original['pid'],original['start'],ticket)
 def test_remote_launcher_is_not_blanket_protected(self):
  with tempfile.TemporaryDirectory() as tmp:
   records={10:self.record(pid=10,ppid=1,exe='/usr/bin/node',name='node'),11:self.record(pid=11,ppid=10,exe='/opt/codex',name='codex')}
   for pid in records:(Path(tmp)/str(pid)).mkdir()
   manager=Processes(proc=Path(tmp));manager.uid=1000
   def read(pid):
    if pid not in records:raise ProcessLookupError()
    return records[pid]
   manager.read=read
   self.assertNotIn(10,manager.protected())
   self.assertTrue(manager.permitted(records[10],{})[0])
 def test_proc_stat_handles_spaces_and_parentheses(self):
  fields=['S','22']+['0']*50;fields[11]='20';fields[12]='10';fields[17]='3';fields[19]='100';fields[20]='4096';fields[21]='2'
  p=parse_stat('1234 (web ) worker) '+' '.join(fields),4096)
  self.assertEqual(p['name'],'web ) worker');self.assertEqual(p['rss_bytes'],8192);self.assertEqual(p['cpu_ticks'],30);self.assertEqual(p['start'],100)
 def test_only_exact_snapshot_can_be_signalled(self):
  manager=Processes(policy=lambda *args:(True,'测试子进程'))
  child=subprocess.Popen(['/usr/bin/sleep','30']);self.addCleanup(lambda: child.poll() is None and (child.kill(),child.wait()))
  info=manager.detail('test-owner',child.pid)
  for owner,start,ticket in [('other',info['start'],info['ticket']),('test-owner',info['start']+1,info['ticket']),('test-owner',info['start'],'0'*64)]:
   with self.assertRaises(ApiError):manager.terminate(owner,child.pid,start,ticket)
   self.assertIsNone(child.poll())
  manager.terminate('test-owner',child.pid,info['start'],info['ticket']);self.assertIsNotNone(child.poll())
 def test_core_and_unknown_process_not_controllable(self):
  p=Processes().detail('owner',1);self.assertFalse(p['can_close']);self.assertIsNone(p['ticket'])
 def test_snapshots_do_not_expose_command_line_or_environment(self):
  p=Processes().snapshot();self.assertIn('processes',p)
  for item in p['processes']:
   self.assertNotIn('cmdline',item);self.assertNotIn('environ',item)
if __name__=='__main__':unittest.main()
