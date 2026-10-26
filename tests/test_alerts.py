# SPDX-License-Identifier: Apache-2.0
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alerts import Alerts
from control import ApiError
from fixtures import configure_resources
configure_resources()

class AlertTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'alerts.json';self.a=Alerts(self.path,expected_disks=('/',))
 def point(self,temp=40,memory=40):return {'temperature':temp,'memory':memory,'time':100,'disks':[{'path':'/','used':10,'total':100}]}
 def test_activation_hysteresis_and_dedup(self):
  for n in range(2):self.a.update(self.point(temp=80),None,100+n)
  self.assertEqual(self.a.snapshot()['active'],[])
  self.a.update(self.point(temp=80),None,102);self.assertEqual(len(self.a.snapshot()['active']),1)
  self.a.update(self.point(temp=73),None,103);self.assertEqual(len(self.a.snapshot()['active']),1)
  for t in (104,105):self.a.update(self.point(temp=60),None,t)
  self.assertEqual(self.a.snapshot()['active'],[]);self.assertEqual(len(self.a.snapshot()['events']),2)
 def test_active_survives_restart(self):
  for t in (100,101,102):self.a.update(self.point(memory=95),None,t)
  other=Alerts(self.path);other.update(self.point(memory=95),None,103)
  self.assertEqual(len(other.snapshot()['active']),1);self.assertEqual(len(other.snapshot()['events']),1)
 def test_unknown_reading_is_not_recovery(self):
  for t in (100,101,102):self.a.update(self.point(temp=80),None,t)
  for t in (103,104,105):self.a.update(self.point(temp=None),None,t)
  self.assertTrue(any(x['key']=='temperature' for x in self.a.snapshot()['active']))
  self.assertTrue(any(x['key']=='data-temperature' for x in self.a.snapshot()['active']))
 def test_service_requires_fresh_samples(self):
  r=[{'id':'photos','state':'exited','name':'相册'}]
  self.a.update(self.point(),r,100)
  for t in (101,102,103):self.a.update(self.point(),None,t)
  self.assertFalse(any(x['key']=='service-photos' for x in self.a.snapshot()['active']))
  self.a.update(self.point(),r,104);self.a.update(self.point(),r,105)
  self.assertTrue(any(x['key']=='service-photos' for x in self.a.snapshot()['active']))
 def test_invalid_rules_and_atomic_validation(self):
  old=self.a.snapshot()['rules']
  for rules in [{'temperature':1},{'temperature':float('nan')},{'watch':['ssh']},{'memory':True},{'temperature':80,'secret':'bad'}]:
   with self.assertRaises(ApiError):self.a.configure(rules)
   self.assertEqual(self.a.snapshot()['rules'],old)
 def test_removed_disk_does_not_keep_alerting_after_restart(self):
  a=Alerts(self.path,expected_disks=['/','/srv/old-disk'])
  for t in (1,2,3):a.update(self.point(),None,t)
  self.assertTrue(any(e['key']=='data-disk-/srv/old-disk' for e in a.snapshot()['active']))
  b=Alerts(self.path,expected_disks=['/'])
  for t in (4,5,6):b.update(self.point(),None,t)
  self.assertFalse(any('old-disk' in e['key'] for e in b.snapshot()['active']))
 def test_removed_resource_watch_is_reconciled(self):
  from unittest.mock import patch
  self.a.data['rules']['watch']=['photos'];self.a.update(self.point(),[],1);self.a.update(self.point(),[],2);self.a.update(self.point(),[],3)
  with patch.dict('alerts.RESOURCES',{},clear=True):
   b=Alerts(self.path,expected_disks=['/']);self.assertEqual(b.snapshot()['rules']['watch'],[]);self.assertFalse(any(e['key']=='service-photos' for e in b.snapshot()['active']))
