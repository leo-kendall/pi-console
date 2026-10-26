# SPDX-License-Identifier: Apache-2.0
import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import bridge_manage as bridge

class BridgeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.state=Path(self.tmp.name)/'state.json'
  self.calls=[];self.container=None
 def command(self,*args,**kwargs):
  self.calls.append(args)
  if args[0]=='inspect':return subprocess.CompletedProcess(args,0,json.dumps([self.container])) if self.container else subprocess.CompletedProcess(args,1,'','absent')
  if args[:2]==('image','inspect'):return subprocess.CompletedProcess(args,0,'[]')
  return subprocess.CompletedProcess(args,0,'','')
 def invoke(self,*args):
  with patch.object(bridge,'STATE',self.state),patch.object(bridge,'cmd',side_effect=self.command),patch('sys.argv',['bridge_manage.py',*args]):bridge.main()
 def test_existing_image_is_not_removed_even_with_explicit_flag(self):
  self.invoke('install');self.assertFalse(json.loads(self.state.read_text())['image_new_for_project'])
  self.calls.clear();self.invoke('uninstall','--remove-image');self.assertFalse(any(a[:2]==('image','rm') for a in self.calls))
 def test_missing_receipt_does_not_remove_container_or_image(self):
  self.container={'Config':{'Labels':{'dev.piconsole':'desktop-v2'},'Image':bridge.IMAGE},'State':{'Status':'running'}}
  with self.assertRaises(RuntimeError):self.invoke('uninstall')
  self.assertFalse(any(a[0]=='rm' or a[:2]==('image','rm') for a in self.calls))
