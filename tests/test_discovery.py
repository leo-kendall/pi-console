# SPDX-License-Identifier: Apache-2.0
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from discovery import collect_inventory,merge_inventory,run_inventory,InventoryError
from control import Control,ApiError

class DiscoveryTests(unittest.TestCase):
 def fixture(self):
  self.outputs={
   ('user','list-units'):[{'unit':'worker.service','active':'active','sub':'running','description':'Background worker'}],
   ('user','list-unit-files'):[{'unit_file':'worker.service','state':'enabled'},{'unit_file':'new-app.service','state':'disabled'}],
   ('system','list-units'):[{'unit':'systemd-journald.service','active':'active','sub':'running','description':'Journal'}],
   ('system','list-unit-files'):[{'unit_file':'systemd-journald.service','state':'static'}],
   ('container','ps'):[{'id':'a'*64,'name':'new-photos','state':'running','status':'Up 1 minute','image':'photos:latest'}]}
  def runner(args):
   scope='container' if args[0].endswith('/docker') else 'user' if '--user' in args else 'system'
   command='ps' if scope=='container' else 'list-unit-files' if 'list-unit-files' in args else 'list-units'
   value=self.outputs[(scope,command)]
   if isinstance(value,Exception):raise value
   return '\n'.join(json.dumps(x) for x in value) if scope=='container' else json.dumps(value)
  return runner
 def test_detects_loaded_and_newly_installed_services_and_containers(self):
  data=collect_inventory(self.fixture());rows={(r['kind'],r['target']):r for r in data['resources']}
  self.assertEqual(len(rows),4)
  self.assertEqual(rows['user','new-app.service']['state'],'not-loaded')
  self.assertEqual(rows['container','new-photos']['state'],'running')
  self.assertTrue(all(not r['control'] and not r['logs'] for r in rows.values()))
  self.assertFalse(data['discovery']['partial'])
 def test_new_and_removed_objects_are_reflected_on_next_scan(self):
  runner=self.fixture();first=collect_inventory(runner)
  stable=next(r['id'] for r in first['resources'] if r['target']=='worker.service')
  self.outputs['container','ps']=[]
  self.outputs['user','list-unit-files'].append({'unit_file':'just-installed.service','state':'disabled'})
  second=collect_inventory(runner);targets={r['target'] for r in second['resources']}
  self.assertIn('just-installed.service',targets);self.assertNotIn('new-photos',targets)
  self.assertEqual(stable,next(r['id'] for r in second['resources'] if r['target']=='worker.service'))
 def test_permission_failure_does_not_hide_other_sources_or_expose_stderr(self):
  runner=self.fixture();self.outputs['container','ps']=RuntimeError('private diagnostic must never be returned')
  data=collect_inventory(runner)
  self.assertTrue(data['discovery']['partial']);self.assertTrue(any(r['kind']=='user' for r in data['resources']))
  self.assertNotIn('private diagnostic',json.dumps(data))
 def test_bad_records_are_skipped_and_marked_partial(self):
  runner=self.fixture();self.outputs['user','list-units'] += [{'unit':'../unsafe.service','active':'active'},None]
  data=collect_inventory(runner)
  self.assertTrue(data['discovery']['partial']);self.assertFalse(any('../' in r['target'] for r in data['resources']))
 def test_configured_permissions_are_preserved_only_for_the_exact_target_and_kind(self):
  data=collect_inventory(self.fixture())
  allowed={'id':'worker','name':'My worker','kind':'user','target':'worker.service','state':'active/running','control':True,'logs':True,'impact':'Jobs stop'}
  result=merge_inventory([allowed],data);rows=result['resources']
  matching=[r for r in rows if r['kind']=='user' and r['target']=='worker.service']
  self.assertEqual(len(matching),1);self.assertEqual(matching[0]['id'],'worker');self.assertTrue(matching[0]['control'])
  self.assertTrue(all(not r['control'] for r in rows if r['id']!='worker'))
 def test_discovery_cannot_grant_control_through_the_action_api(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Control(Path(tmp),runner=lambda args:'',inventory_runner=self.fixture())
   found=next(r for r in c.resources()['resources'] if r['target']=='new-photos')
   with self.assertRaises(ApiError):c.action('operator',found['id'],'stop','discovery-request-123')
 def test_duplicate_configured_aliases_retain_both_authorized_ids(self):
  one={'id':'primary','name':'Primary','kind':'container','target':'new-photos','state':'running','control':True,'logs':True,'impact':'Stops app'}
  two={**one,'id':'secondary','name':'Secondary'}
  rows=merge_inventory([one,two],collect_inventory(self.fixture()))['resources']
  self.assertEqual({r['id'] for r in rows if r['target']=='new-photos'},{'primary','secondary'})
 def test_inventory_listing_never_uses_the_action_command_runner(self):
  calls=[]
  with tempfile.TemporaryDirectory() as tmp:
   c=Control(Path(tmp),runner=lambda args:calls.append(args) or '',inventory_runner=self.fixture())
   with patch('control.RESOURCES',{'worker':('My worker','user','worker.service','Stops jobs')}):
    rows=c.resources()['resources']
   row=next(r for r in rows if r['id']=='worker')
   self.assertEqual(row['state'],'active/running');self.assertTrue(row['control']);self.assertEqual(calls,[])
 def test_unreadable_source_does_not_claim_configured_container_was_removed(self):
  runner=self.fixture();self.outputs['container','ps']=PermissionError()
  with tempfile.TemporaryDirectory() as tmp:
   c=Control(Path(tmp),inventory_runner=runner)
   with patch('control.RESOURCES',{'photos':('Photos','container','new-photos','Stops app')}):rows=c.resources()['resources']
   self.assertEqual(next(r for r in rows if r['id']=='photos')['state'],'unavailable')
 def test_reader_rejects_truncated_output_and_times_out_its_own_child(self):
  with self.assertRaises(InventoryError):run_inventory([sys.executable,'-c','print("x"*2048)'],max_bytes=128)
  with self.assertRaises(InventoryError):run_inventory([sys.executable,'-c','import time;time.sleep(10)'],timeout=.1)
 def test_long_unicode_inventory_fits_android_response_limit(self):
  runner=self.fixture()
  for kind in ('user','system'):
   self.outputs[kind,'list-unit-files']=[]
   self.outputs[kind,'list-units']=[{'unit':f'job-{i:04d}-'+('x'*220)+'.service','active':'active','sub':'running','description':'服务说明'*45} for i in range(500)]
  self.outputs['container','ps']=[]
  data=merge_inventory([],collect_inventory(runner))
  self.assertLessEqual(len(json.dumps(data,ensure_ascii=False).encode()),768*1024)
  self.assertTrue(data['discovery']['truncated']);self.assertTrue(data['discovery']['partial'])
if __name__=='__main__':unittest.main()
