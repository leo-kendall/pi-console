# SPDX-License-Identifier: Apache-2.0
import os,sys,tempfile,threading,time,unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alerts import Alerts
from storage import Storage
class ReviewRegressions(unittest.TestCase):
 def test_missing_disk_and_unmounted_volume_alert(self):
  with tempfile.TemporaryDirectory() as d:
   a=Alerts(Path(d)/'a.json',expected_disks=['/','/srv/data'])
   point={'time':10,'temperature':40,'memory':40,'disks':[]}
   for t in (10,11,12):a.update(point,None,t)
   self.assertTrue(any(x['key']=='data-disk-/' for x in a.snapshot()['active']))
   point['disks']=[{'path':'/','total':100,'used':1},{'path':'/srv/data','total':100,'used':1}];point['storage_mounts']={'/':True,'/srv/data':False}
   for t in (13,14,15):a.update(point,None,t)
   self.assertTrue(any(x['key']=='data-disk-/srv/data' for x in a.snapshot()['active']))
 def test_slow_services_do_not_starve_metric_sampling(self):
  with tempfile.TemporaryDirectory() as d:
   a=Alerts(Path(d)/'a.json');release=threading.Event();started=threading.Event()
   class Telemetry:
    def history(self,*args):return {'points':[{'time':time.time(),'temperature':40,'memory':40,'disks':[]}]}
   class Control:
    def resources(self):started.set();release.wait(2);raise OSError('slow probe')
   stop=a.start(Telemetry(),Control())
   try:
    self.assertTrue(started.wait(1));deadline=time.time()+.4
    while a.snapshot()['sampled_at'] is None and time.time()<deadline:time.sleep(.01)
    self.assertIsNotNone(a.snapshot()['sampled_at'])
   finally:
    if stop is not None:stop.set()
    release.set()
 def test_storage_hidden_items_are_not_silently_lost(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'.large').write_bytes(b'x'*1000);s=Storage({'home':p},{'preview':p/'cache'});data=s.scan('home');self.assertTrue(any(x['name']=='.large' and x['bytes']==1000 for x in data['items']) or not data['complete'])
