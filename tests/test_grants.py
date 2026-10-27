# SPDX-License-Identifier: Apache-2.0
import importlib.util,tempfile,unittest
from pathlib import Path
from control import Control,ApiError

class GrantTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.c=Control(Path(self.temp.name),runner=lambda a:'')
  self.admin=self.c.pair(self.c.new_code())['device'];self.viewer=self.c.pair(self.c.new_code('viewer'))['device']
  self.rows=[dict(id='found-photo',kind='container',target='photos',identity='a'*64,name='Photos',state='running')]
  self.c.grants.catalog=lambda:self.rows
 def test_phone_grants_persist_exact_container_identity_without_global_config_mutation(self):
  self.c.grants.set(self.admin,'found-photo',['stop','logs'],'a'*64)
  command=self.c.command('found-photo','stop');self.assertEqual(command[-2:],['stop','a'*64])
  self.assertEqual(Control(self.c.root).grants.entries()['found-photo']['identity'],'a'*64)
  self.rows[0]['identity']='b'*64
  with self.assertRaises(ApiError):self.c.command('found-photo','stop')
 def test_grant_revocation_takes_effect_and_viewer_cannot_authorize(self):
  with self.assertRaises(ApiError):self.c.grants.set(self.viewer,'found-photo',['stop'],'a'*64)
  self.c.grants.set(self.admin,'found-photo',['logs'],'a'*64)
  with self.assertRaises(ApiError):self.c.command('found-photo','restart')
  self.c.grants.remove(self.admin,'found-photo')
  with self.assertRaises(ApiError):self.c.command('found-photo','logs')
 def test_system_core_services_remain_readonly_and_shell_syntax_refused(self):
  from grants import unit_commands
  for unit in ['systemd-journald.service','NetworkManager.service','dbus.service','user@1000.service','gnome-shell.service','init.service','x;touch hacked.service','../bad.service']:
   with self.subTest(unit=unit),self.assertRaises((ApiError,ValueError)):unit_commands('system',unit,'stop',lambda a:'')
 def test_user_unit_alias_and_dependency_to_core_cannot_be_stopped(self):
  from grants import unit_commands
  def reader(args):return 'Id=ordinary.service\nNames=ordinary.service NetworkManager.service\nLoadState=loaded\nRefuseManualStop=no\n'
  with self.assertRaises((ApiError,ValueError)):unit_commands('user','ordinary.service','stop',reader)
  def reader(args):return 'Id=ordinary.service\nNames=ordinary.service\nLoadState=loaded\nRequiredBy=systemd-logind.service\n'
  with self.assertRaises((ApiError,ValueError)):unit_commands('user','ordinary.service','stop',reader)
 def test_runtime_permissions_can_be_narrowed_without_editing_config(self):
  self.c.grants.set(self.admin,'found-photo',['stop'],'a'*64)
  result=self.c.grants.apply({'resources':self.rows})['resources'][0]
  self.assertTrue(result['control']);self.assertEqual(result['allowed_actions'],['stop']);self.assertFalse(result['logs'])
 def test_stale_grant_can_be_revoked_after_resource_disappears(self):
  self.c.grants.set(self.admin,'found-photo',['stop'],'a'*64)
  self.rows=[]
  self.c.grants.remove(self.admin,'found-photo')
  with self.assertRaises(ApiError):self.c.command('found-photo','stop')
 def test_revoking_ungranted_discovery_rows_never_exhausts_grant_storage(self):
  for i in range(129):
   self.rows=[dict(id='found-'+str(i),kind='container',target='app'+str(i),identity='a'*64,name='App')]
   self.c.grants.remove(self.admin,'found-'+str(i))
  self.assertIsInstance(self.c.grants.list(self.admin)['grants'],list)
  self.rows=[dict(id='found-valid',kind='container',target='valid',identity='a'*64,name='Valid')]
  self.c.grants.set(self.admin,'found-valid',['logs'],'a'*64)
  self.assertEqual(self.c.command('found-valid','logs')[-1],'a'*64)
 def test_inventory_timeout_is_an_actionable_api_error(self):
  from discovery import InventoryError
  from grants import unit_commands
  def timeout(args):raise InventoryError('timed out')
  with self.assertRaises(ApiError):unit_commands('user','ordinary.service','stop',timeout)
