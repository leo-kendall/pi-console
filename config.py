# SPDX-License-Identifier: Apache-2.0
"""Validated, local-only configuration. No commands or credentials in config."""
import json,os,re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT=Path(__file__).resolve().parent
SYSTEM_UNITS={'display':'pi-console-display.service','printer':'cups-browsed.service'}
def _unique(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('duplicate configuration key: '+key)
  result[key]=value
 return result
def load_config(path):
 data={}
 if path is not None and Path(path).exists():
  p=Path(path)
  if p.is_symlink() or p.stat().st_size>65536:raise ValueError('configuration must be a regular JSON file under 64 KiB')
  data=json.loads(p.read_text(),object_pairs_hook=_unique)
 if not isinstance(data,dict) or set(data)-{'name','resources','storage_roots','disks','desktop_timezone','file_roots'}:raise ValueError('unknown configuration fields')
 name=data.get('name','Pi Console')
 if not isinstance(name,str) or not 1<=len(name)<=64 or any(ord(c)<32 for c in name):raise ValueError('invalid server name')
 timezone=data.get('desktop_timezone','UTC')
 if not isinstance(timezone,str) or not re.fullmatch(r'[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*',timezone) or len(timezone)>64:raise ValueError('invalid desktop timezone')
 try:ZoneInfo(timezone)
 except ZoneInfoNotFoundError as exc:raise ValueError('unknown desktop timezone; check system tzdata') from exc
 resources=data.get('resources',{})
 if not isinstance(resources,dict) or len(resources)>32:raise ValueError('invalid resource allowlist')
 checked={}
 for key,item in resources.items():
  if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',key) or not isinstance(item,dict) or set(item)!={'name','kind','target','impact'}:raise ValueError('invalid resource definition')
  label,kind,target,impact=(item[k] for k in ('name','kind','target','impact'))
  if any(not isinstance(v,str) or not v or len(v)>256 or any(ord(c)<32 for c in v) for v in (label,kind,target,impact)):raise ValueError('invalid resource fields')
  if kind not in ('user','container','system'):raise ValueError('invalid resource kind')
  pattern=r'[A-Za-z0-9][A-Za-z0-9_.@-]{0,120}\.service' if kind!='container' else r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}'
  if not re.fullmatch(pattern,target):raise ValueError('invalid resource target')
  if kind=='system' and SYSTEM_UNITS.get(key)!=target:raise ValueError('only fixed auxiliary system units are supported')
  checked[key]=(label,kind,target,impact)
 roots=data.get('storage_roots',{'home':str(Path.home()),'data':str(ROOT/'data'),'cache':str(Path.home()/'.cache')})
 if not isinstance(roots,dict) or not roots or len(roots)>16:raise ValueError('invalid storage roots')
 for key,value in roots.items():
  if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',key) or not isinstance(value,str) or not Path(value).is_absolute() or '\x00' in value:raise ValueError('storage roots must be absolute paths')
 disks=data.get('disks',['/'])
 if not isinstance(disks,list) or not disks or len(disks)>16 or any(not isinstance(p,str) or not Path(p).is_absolute() or '\x00' in p for p in disks) or len(set(disks))!=len(disks):raise ValueError('disks must be unique absolute mount paths')
 file_roots=data.get('file_roots',{})
 if not isinstance(file_roots,dict) or len(file_roots)>16:raise ValueError('invalid file roots')
 for key,entry in file_roots.items():
  if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9-]{0,31}',key) or key=='default' or not isinstance(entry,dict) or set(entry)!={'name','path','writable'}:raise ValueError('invalid file root')
  if not isinstance(entry['name'],str) or not 1<=len(entry['name'])<=64 or any(ord(c)<32 for c in entry['name']) or not isinstance(entry['path'],str) or not Path(entry['path']).is_absolute() or '\x00' in entry['path'] or type(entry['writable'])!=bool:raise ValueError('invalid file root fields')
  path=Path(entry['path'])
  if '..' in path.parts or entry['writable'] and (str(path) in ('/','/etc','/boot','/usr','/var','/var/lib','/home') or any(path==Path(p) or Path(p) in path.parents for p in ('/etc','/boot','/usr','/proc','/sys','/dev','/run','/bin','/sbin','/lib'))):raise ValueError('system file roots cannot be writable')
 return {'name':name,'resources':checked,'storage_roots':{k:Path(v) for k,v in roots.items()},'disks':disks,'desktop_timezone':timezone,'file_roots':file_roots}

SETTINGS=load_config(Path(os.environ.get('PI_CONSOLE_CONFIG',str(ROOT/'config.json'))))
