# SPDX-License-Identifier: Apache-2.0
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alerts import Alerts
from processes import Processes
from telemetry import Telemetry
from control import ApiError
class MonitoringTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'alerts.json'
 def point(self,v):return {'temperature':v,'memory':20,'disks':[]}
 def test_configurable_debounce_recovery_and_old_rules_roundtrip(self):
  a=Alerts(self.path,expected_disks=[]);old=a.snapshot()['rules'];a.configure({**old,'debounce_samples':2,'recovery_samples':3})
  a.update(self.point(80),None,1);self.assertFalse(a.snapshot()['active']);a.update(self.point(80),None,2);self.assertEqual(a.snapshot()['events'][-1]['state'],'active')
  for t in [3,4]:a.update(self.point(40),None,t)
  self.assertTrue(a.snapshot()['active']);a.update(self.point(40),None,5);self.assertEqual(a.snapshot()['events'][-1]['state'],'resolved');self.assertTrue(a.snapshot()['events'][-1]['recovered'])
  a.configure({k:old[k] for k in ('temperature','memory','disk','watch')});self.assertEqual(a.snapshot()['rules']['debounce_samples'],2)
  b=Alerts(self.path,expected_disks=[]);self.assertEqual(b.snapshot()['rules']['recovery_samples'],3)
 def test_invalid_extended_rules_atomic_and_configuration_is_not_recovery(self):
  a=Alerts(self.path,expected_disks=[]);old=a.snapshot()['rules']
  for extra in [{'debounce_samples':True},{'debounce_samples':0},{'recovery_samples':21},{'quiet_hours':{}}]:
   with self.assertRaises(ApiError):a.configure({**old,**extra})
   self.assertEqual(a.snapshot()['rules'],old)
  a.event('service-photos','test','bad','active',1);a.configure(old);self.assertFalse(a.snapshot()['events'][-1]['recovered'])
 def test_old_persistent_schema_migrates_without_losing_incidents(self):
  self.path.write_text(json.dumps({'rules':{'temperature':75,'memory':90,'disk':90,'watch':[]},'active':{},'events':[],'sampled_at':None}))
  a=Alerts(self.path,expected_disks=[]);self.assertEqual(a.snapshot()['rules']['debounce_samples'],3);self.assertEqual(a.snapshot()['rules']['recovery_samples'],2)
 def test_history_identity_bounds_and_numeric_only(self):
  p=Processes();self.assertTrue(hasattr(p,'history'),'per-process identity history is required')
  with self.assertRaises(ApiError):p.history(True,1)
  import os
  pid=os.getpid();record=p.read(pid);r=p.history(pid,record['start']);self.assertEqual(r['pid'],pid);self.assertTrue(r['points']);self.assertNotIn('exe',r['points'][0]);self.assertNotIn('name',r['points'][0])
  with self.assertRaises(ApiError):p.history(pid,record['start']+1)
  r['points'].clear();self.assertTrue(p.history(pid,record['start'])['points'])
 def test_telemetry_history_does_not_expose_mutable_samples(self):
  t=Telemetry();t.points.append({'time':__import__('time').time(),'cpu':10,'network':{'eth0':{'rx':1,'tx':2}}})
  r=t.history('5m');r['points'][0]['network']['eth0']['rx']=999
  self.assertEqual(t.history('5m')['points'][0]['network']['eth0']['rx'],1)

class SamplingBoundaryTests(unittest.TestCase):
 def test_missing_readings_break_recovery_debounce(self):
  with tempfile.TemporaryDirectory() as folder:
   a=Alerts(Path(folder)/'rules.json',expected_disks=[])
   for t in [1,2,3]:a.update({'temperature':80,'memory':20},None,t)
   a.update({'temperature':40,'memory':20},None,4)
   a.update({'temperature':None,'memory':20},None,5)
   a.update({'temperature':40,'memory':20},None,6)
   self.assertTrue(any(x['key']=='temperature' for x in a.snapshot()['active']))
   a.update({'temperature':40,'memory':20},None,7)
   self.assertFalse(any(x['key']=='temperature' for x in a.snapshot()['active']))
 def test_cpu_and_network_restart_or_delay_produce_gap(self):
  import io
  t=Telemetry();sample={'cpu':'cpu 100 0 0 100 0 0 0 0\n','net':'head\nhead\n eth0: 100 0 0 0 0 0 0 0 100 0 0 0 0 0 0 0\n'}
  def proc_open(path,*args,**kwargs):
   if path=='/proc/stat':return io.StringIO(sample['cpu'])
   if path=='/proc/meminfo':return io.StringIO('MemTotal: 100\nMemAvailable: 50\n')
   if path=='/proc/net/dev':return io.StringIO(sample['net'])
   raise FileNotFoundError(path)
  with patch('builtins.open',proc_open),patch('telemetry.SETTINGS',{'disks':[]}),patch('telemetry.time.time',return_value=100) as clock:
   t.sample();self.assertIsNone(t.points[-1]['cpu'])
   clock.return_value=103;sample['cpu']='cpu 110 0 0 110 0 0 0 0\n';sample['net']=sample['net'].replace('100','400');t.sample()
   self.assertEqual(t.points[-1]['cpu'],50);self.assertEqual(t.points[-1]['network']['eth0']['rx'],100)
   clock.return_value=130;sample['cpu']='cpu 120 0 0 120 0 0 0 0\n';t.sample();self.assertIsNone(t.points[-1]['cpu']);self.assertEqual(t.points[-1]['network'],{})
   clock.return_value=133;sample['cpu']='cpu 5 0 0 5 0 0 0 0\n';sample['net']=sample['net'].replace('400','2');t.sample();self.assertIsNone(t.points[-1]['cpu']);self.assertEqual(t.points[-1]['network'],{})
