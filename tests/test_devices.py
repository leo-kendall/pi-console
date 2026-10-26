# SPDX-License-Identifier: Apache-2.0
import json,tempfile,time,unittest
from pathlib import Path
from control import Control,ApiError

class DeviceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.control=Control(Path(self.temp.name));self.admin=self.pair('admin');self.viewer=self.pair('viewer')
 def pair(self,role):return self.control.pair(self.control.new_code(role))
 def test_role_bound_to_code_and_legacy_devices_keep_existing_access(self):
  c=self.control;self.assertEqual(c.session(self.viewer['device'])['role'],'viewer')
  with self.assertRaises(ApiError):c.require(self.viewer['device'],'operator')
  c.require(self.admin['device'],'admin')
  raw=json.loads((c.root/'auth.json').read_text());raw['devices'][next(iter(raw['devices']))].pop('role');(c.root/'auth.json').write_text(json.dumps(raw))
  self.assertEqual(c.session(self.admin['device'])['role'],'admin')
 def test_device_inventory_and_audit_never_return_auth_hashes_codes_or_tokens(self):
  c=self.control;raw=(c.root/'auth.json').read_text();hashes=list(json.loads(raw)['devices'])
  result=json.dumps(c.devices(self.admin['device']))
  for value in [*hashes,self.viewer['token'],self.admin['token']]:self.assertNotIn(value,result)
  self.assertEqual(len(c.devices(self.admin['device'])['devices']),2)
  with self.assertRaises(ApiError):c.devices(self.viewer['device'])
 def test_self_rename_and_admin_role_change_are_bounded_and_persist(self):
  c=self.control;c.update_device(self.viewer['device'],self.viewer['device'],name='我的平板')
  self.assertEqual(c.session(self.viewer['device'])['name'],'我的平板')
  with self.assertRaises(ApiError):c.update_device(self.viewer['device'],self.viewer['device'],role='admin')
  with self.assertRaises(ApiError):c.update_device(self.admin['device'],self.admin['device'],role='viewer')
  c.update_device(self.admin['device'],self.viewer['device'],role='operator')
  self.assertEqual(Control(c.root).session(self.viewer['device'])['role'],'operator')
  for invalid in ['','x'*65,'bad\nname']:
   with self.assertRaises(ApiError):c.update_device(self.viewer['device'],self.viewer['device'],name=invalid)
 def test_revoked_device_cannot_read_or_execute_and_last_seen_updates(self):
  c=self.control;owner=c.authenticate(self.viewer['token']);self.assertEqual(owner,self.viewer['device'])
  row=next(d for d in c.devices(self.admin['device'])['devices'] if d['id']==owner);self.assertGreater(row['last_seen'],0)
  c.revoke_device(self.admin['device'],owner)
  with self.assertRaises(ApiError):c.authenticate(self.viewer['token'])
  with self.assertRaises(ApiError):c.require(owner,'viewer')
  events=c.audit(self.admin['device'])['events'];self.assertTrue(any(e['action']=='device-revoke' for e in events))
 def test_route_permissions_deny_writes_even_when_read_actions_use_post(self):
  c=self.control;owner=self.viewer['device']
  for method,path in [('GET','/api/status'),('POST','/api/files/list'),('POST','/api/files/read'),('POST','/api/logs/tail')]:c.authorize_route(owner,method,path)
  for method,path in [('POST','/api/actions'),('POST','/api/files/upload/start'),('POST','/api/processes/terminate'),('POST','/api/devices/pair-code'),('GET','/api/devices'),('GET','/api/grants')]:
   with self.subTest(path=path),self.assertRaises(ApiError):c.authorize_route(owner,method,path)
