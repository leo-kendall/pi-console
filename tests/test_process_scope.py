# SPDX-License-Identifier: Apache-2.0
import unittest
from processes import process_policy

class RequestedProcessScopeTests(unittest.TestCase):
 def record(self,**changes):
  p=dict(pid=100,ppid=22,start=123,state='S',name='node',exe='/usr/bin/node',uids=[1000]*4,cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/my-app.service',flags=0)
  p.update(changes);return p
 def test_codex_immich_and_other_apps_are_not_system_core(self):
  cases=[dict(name='codex',exe='/opt/codex',cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/codex-remote-control.service'),dict(name='node',exe='/usr/bin/node'),dict(name='immich',exe='',uids=[0]*4,cgroup='/system.slice/docker-'+'a'*64+'.scope'),dict(name='postgres',exe='/usr/bin/postgres',uids=[999]*4,cgroup='/system.slice/postgresql.service'),dict(name='python',exe='/usr/bin/python3',uids=[0]*4,cgroup='/system.slice/application-agent.service'),dict(name='tailscaled',exe='',uids=[0]*4,cgroup='/system.slice/tailscaled.service'),dict(name='bash',exe='/usr/bin/bash'),dict(name='tmux: server',exe='/usr/bin/tmux'),dict(name='python3',exe='/usr/bin/python3',cgroup='/user.slice/user-1000.slice/user@1000.service/app.slice/pi-console.service')]
  for x in cases:
   with self.subTest(x=x):self.assertTrue(process_policy(self.record(**x),{},1000,set())[0])
 def test_codex_ancestors_and_children_are_not_blanket_protected(self):
  parent=self.record(pid=22,name='codex',exe='/opt/codex')
  self.assertTrue(process_policy(self.record(),{22:parent},1000,{100,22})[0])
 def test_actual_os_core_is_read_only(self):
  for x in [dict(pid=1,name='systemd'),dict(name='kworker/0:1',exe='',flags=0x00200000),dict(name='systemd',exe='/usr/lib/systemd/systemd',cgroup='/user.slice/user-1000.slice/user@1000.service/init.scope'),dict(name='dbus-broker',exe='/usr/bin/dbus-broker',cgroup='/system.slice/dbus.service'),dict(name='gnome-shell',exe='/usr/bin/gnome-shell',cgroup='/user.slice/user-1000.slice/user@1000.service/session.slice/org.gnome.Shell@ubuntu.service'),dict(name='systemd-udevd',cgroup='/system.slice/systemd-udevd.service'),dict(name='NetworkManager',exe='/usr/sbin/NetworkManager',uids=[0]*4,cgroup='/system.slice/NetworkManager.service'),dict(name='python',exe='',cgroup='/system.slice/systemd-logind.service')]:
   with self.subTest(x=x):self.assertFalse(process_policy(self.record(**x),{},1000,set())[0])
 def test_container_process_name_does_not_inherit_host_core_role(self):
  self.assertTrue(process_policy(self.record(name='systemd',exe='/usr/lib/systemd/systemd',uids=[0]*4,cgroup='/system.slice/docker-'+'a'*64+'.scope'),{},1000,set())[0])
 def test_names_and_dbus_activation_do_not_make_applications_core(self):
  for x in [dict(name='gnome-shell',exe='/home/demo/gnome-shell',trusted_exe=False),dict(name='gsd-example',exe='/home/demo/gsd-example',trusted_exe=False),dict(name='dbus-daemon',exe='/usr/bin/dbus-daemon',trusted_exe=True),dict(name='goa-daemon',exe='/usr/libexec/goa-daemon',trusted_exe=True,cgroup='/user.slice/user-1000.slice/user@1000.service/session.slice/dbus.service')]:
   with self.subTest(x=x):self.assertTrue(process_policy(self.record(**x),{},1000,set())[0])
 def test_real_graphical_session_scope_and_session_daemon(self):
  for name in ['gdm-wayland-session','gnome-session-init-worker','Xorg','Xwayland']:
   self.assertFalse(process_policy(self.record(name=name,exe='/usr/libexec/'+name,trusted_exe=True,cgroup='/user.slice/user-1000.slice/session-2.scope'),{},1000,set())[0])
  self.assertTrue(process_policy(self.record(name='dbus-daemon',exe='/usr/bin/dbus-daemon',trusted_exe=True,cgroup='/user.slice/user-1000.slice/user@1000.service/session.slice/at-spi-dbus-bus.service'),{},1000,set())[0])
 def test_actual_host_wifi_foundation_is_read_only(self):
  for unit,name in [('wpa_supplicant.service','wpa_supplicant'),('iwd.service','iwd'),('dhcpcd.service','dhcpcd')]:
   self.assertFalse(process_policy(self.record(name=name,exe='/usr/sbin/'+name,uids=[0]*4,cgroup='/system.slice/'+unit),{},1000,set())[0])
if __name__=='__main__':unittest.main()
