# SPDX-License-Identifier: Apache-2.0
import sys,tempfile,unittest,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from control import Control,command_for,ApiError
from health import report
from fixtures import configure_resources
configure_resources()

class ToolTests(unittest.TestCase):
 def test_operation_history_is_device_scoped(self):
  with tempfile.TemporaryDirectory() as d:
   c=Control(Path(d),runner=lambda a:'')
   a=c.action('a','proxy','start','test-history-owner-a');b=c.action('b','codex','start','test-history-owner-b')
   self.assertEqual([x['id'] for x in c.operations_for('a')['operations']],[a['id']]);self.assertNotIn('owner',c.operations_for('a')['operations'][0])
   while c.busy:time.sleep(.01)
 def test_startup_only_fixed_auxiliary_units(self):
  self.assertEqual(command_for('display','enable')[-2:],['display','enable'])
  for rid in ['proxy','codex','photos','ssh']:
   with self.assertRaises(ApiError):command_for(rid,'disable')
 def test_health_ignores_missing_and_nonfinite_readings(self):
  d=report([{'time':10,'cpu':20,'memory':70,'temperature':None,'disks':[]},{'time':13,'cpu':float('nan'),'memory':80,'temperature':40,'disks':[]}],now=13)
  self.assertEqual(d['cpu']['average'],20);self.assertEqual(d['memory']['maximum'],80);self.assertEqual(d['temperature']['samples'],1)
  self.assertEqual(report([],now=20)['cpu']['samples'],0)
