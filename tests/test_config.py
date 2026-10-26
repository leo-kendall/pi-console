# SPDX-License-Identifier: Apache-2.0
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from config import load_config

class ConfigurationTests(unittest.TestCase):
 def read(self,value):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config.json';p.write_text(json.dumps(value));return load_config(p)
 def test_default_does_not_authorize_service_controls(self):
  cfg=load_config(None);self.assertEqual(cfg['resources'],{});self.assertEqual(cfg['disks'],['/'])
 def test_desktop_timezone_is_portable_and_user_configurable(self):
  self.assertEqual(load_config(None).get('desktop_timezone'),'UTC')
  self.assertEqual(self.read({'desktop_timezone':'Europe/Berlin'})['desktop_timezone'],'Europe/Berlin')
  for zone in ['NoSuch/Zone','../etc/passwd','/etc/localtime','UTC\n',None,123]:
   with self.subTest(zone=zone),self.assertRaises(ValueError):self.read({'desktop_timezone':zone})
 def test_named_resources_are_validated_without_shell(self):
  cfg=self.read({'resources':{'photos':{'name':'Photos','kind':'container','target':'photos-server','impact':'Photo requests stop'}}})
  self.assertEqual(cfg['resources']['photos'][2],'photos-server')
  for value in ['x;id','x\nrestart','--help','a/b']:
   with self.assertRaises(ValueError):self.read({'resources':{'x':{'name':'Test','kind':'user','target':value,'impact':'test'}}})
 def test_unknown_fields_and_types_fail_closed(self):
  for value in [{'secret':'mistyped'},{'disks':'/'},{'resources':[]},{'resources':{'x':{'name':'x','kind':'system','target':'ssh.service','impact':'x'}}},{'disks':['relative']}]:
   with self.subTest(value=value),self.assertRaises(ValueError):self.read(value)
 def test_alternative_users_paths_do_not_use_author_home(self):
  cfg=self.read({'storage_roots':{'home':'/home/alex','data':'/mnt/files'},'disks':['/','/mnt/files']})
  self.assertEqual(cfg['storage_roots']['home'],Path('/home/alex'));self.assertEqual(cfg['disks'],['/','/mnt/files'])
 def test_default_directories_follow_the_running_user(self):
  with patch('config.Path.home',return_value=Path('/home/operator')):
   cfg=load_config(None)
  self.assertEqual(cfg['storage_roots']['home'],Path('/home/operator'))
  self.assertEqual(cfg['storage_roots']['cache'],Path('/home/operator/.cache'))
 def test_duplicate_json_keys_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config.json';p.write_text('{"resources":{},"resources":{}}')
   with self.assertRaises(ValueError):load_config(p)
