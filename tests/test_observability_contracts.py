# SPDX-License-Identifier: Apache-2.0
"""Integration seams: actual Control command construction and fixture /proc, no live services."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from control import Control,ApiError
from live_logs import LiveLogs
from processes import Processes
from fixtures import configure_resources
try:
 from observability_api import dispatch
except ImportError:dispatch=None
class ContractTests(unittest.TestCase):
 def setUp(self):
  configure_resources();self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
 def test_logs_wire_schema_and_no_command_injection(self):
  self.assertIsNotNone(dispatch,'strict API integration dispatcher is required')
  calls=[];control=Control(self.root,runner=lambda argv:calls.append(argv) or 'INFO fixture\nERROR fixture\n');logs=LiveLogs(control)
  result=dispatch('/api/logs/tail',json.loads('{"resource":"photos","cursor":null}'),'device',logs,None)
  self.assertEqual(result['lines'],['INFO fixture','ERROR fixture']);json.dumps(result,allow_nan=False)
  self.assertEqual(calls,[['/usr/bin/docker','--host=unix:///var/run/docker.sock','logs','--tail','100','test-photos']])
  for body in [{'resource':'photos','command':'id'},{'resource':'photos;id'},{'resource':'/etc/shadow'},{'resource':'ungranted'}]:
   with self.assertRaises(ApiError):dispatch('/api/logs/tail',body,'device',logs,None)
  self.assertEqual(len(calls),1)
 def write_proc(self,pid,start,ticks=0):
  path=self.root/str(pid);path.mkdir(exist_ok=True);fields=['S','1','0','0','0','0','0','0','0','0','0',str(ticks),'0','0','0','0','0','2','0',str(start),'40960','2']
  (path/'stat').write_text(str(pid)+' (fixture task) '+' '.join(fields));(path/'status').write_text('Uid:\t1000\t1000\t1000\t1000\n');(path/'cgroup').write_text('0::/fixture\n')
 def test_process_history_wire_identity_gap_and_no_metadata(self):
  self.assertIsNotNone(dispatch,'strict API integration dispatcher is required')
  (self.root/'uptime').write_text('1000 0');(self.root/'meminfo').write_text('MemTotal: 100000 kB\nMemAvailable: 50000 kB\n');self.write_proc(45,100)
  p=Processes(proc=self.root);clock=patch('processes.time.monotonic',return_value=100);now=clock.start();self.addCleanup(clock.stop)
  first=dispatch('/api/processes/history',{'pid':45,'start':100},'device',None,p);self.assertEqual(first['points'][0]['rss_bytes'],8192)
  now.return_value=104;self.write_proc(45,100,40);second=dispatch('/api/processes/history',{'pid':45,'start':100},'device',None,p);self.assertEqual(len(second['points']),2);self.assertEqual(second['points'][1]['cpu_percent'],10)
  self.write_proc(45,200)
  with self.assertRaises(ApiError):dispatch('/api/processes/history',{'pid':45,'start':100},'device',None,p)
  with self.assertRaises(ApiError):dispatch('/api/processes/history',{'pid':45,'start':200,'signal':9},'device',None,p)
  self.assertEqual(set(first['points'][0]),{'time','cpu_percent','rss_bytes','memory_percent'})
 def test_process_storage_bounded_retention_and_exit(self):
  (self.root/'uptime').write_text('1000 0');(self.root/'meminfo').write_text('MemTotal: 100000 kB\nMemAvailable: 50000 kB\n')
  for pid in range(10,80):self.write_proc(pid,100)
  p=Processes(proc=self.root)
  for pid in range(10,80):p.history(pid,100)
  self.assertLessEqual(len(p.histories),64)
  for n in range(1000):p._record_histories([],n*3,100)
  self.assertLessEqual(len(p.histories[(79,100)]['points']),301)
  __import__('shutil').rmtree(self.root/'79');self.assertTrue(p.history(79,100)['ended'])
  p._record_histories([],5000,__import__('time').monotonic()+1000);self.assertEqual(len(p.histories),0)
 def test_utf8_log_budget_and_cursor_data_never_leaks(self):
  logs=LiveLogs(Control(self.root,runner=lambda argv:('😀'*10000+'\n')*300))
  result=logs.tail('device','photos');self.assertLessEqual(sum(len(s.encode()) for s in result['lines']),65536)
  self.assertNotIn('device',json.dumps(result));self.assertEqual(set(result),{'lines','cursor','reset','sampled_at','poll_after_ms','bounded'})
