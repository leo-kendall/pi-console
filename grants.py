# SPDX-License-Identifier: Apache-2.0
"""Persistent phone-managed grants for discovered, exact resource identities."""
import importlib.util,re,stat
from pathlib import Path
from control import ApiError,DOCKER,ROOT,RESOURCES,HELPER
from discovery import collect_inventory
from local_state import save
spec=importlib.util.spec_from_file_location('pi_console_unit_policy',ROOT/'system-control/helper.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

def unit_commands(kind,target,action,reader):
 try:return policy.unit_command(kind,target,action,reader)
 except (ValueError,OSError):raise ApiError('服务属于系统基础、依赖系统基础，或无法核验身份，保持只读',403)

class Grants:
 def __init__(self,control):self.control=control;self.path=control.root/'grants.json';self.catalog=lambda:collect_inventory(control.inventory_runner)['resources']
 def entries(self):
  data=self.control.read('grants.json',{})
  if not isinstance(data,dict) or len(data)>128:raise ApiError('授权文件格式异常',503)
  return data
 def helper_ready(self):
  try:
   p=Path(HELPER)
   for item in (p,*p.parents):
    info=item.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:return False
   return p.read_bytes()==(ROOT/'system-control/helper.py').read_bytes()
  except OSError:return False
 def find(self,rid):
  if not isinstance(rid,str) or not re.fullmatch('[a-zA-Z0-9-]{1,64}',rid):raise ApiError('无效授权对象')
  rows=self.catalog();base=RESOURCES.get(rid)
  row=next((r for r in rows if (r['kind'],r['target'])==(base[1],base[2])),None) if base else next((r for r in rows if r['id']==rid),None)
  if not row:raise ApiError('对象已不存在，请刷新后重新授权',409)
  return dict(row,id=rid)
 def set(self,owner,rid,rights,identity=''):
  self.control.require(owner,'admin')
  if not isinstance(rights,list) or len(rights)>4 or any(not isinstance(r,str) or r not in ('start','stop','restart','logs') for r in rights) or len(set(rights))!=len(rights):raise ApiError('无效授权动作')
  row=self.find(rid)
  if row['kind']=='container':
   if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{64}',identity) or row.get('identity')!=identity:raise ApiError('容器身份已变化，请刷新后重新授权',409)
  else:
   for action in rights:unit_commands(row['kind'],row['target'],action,self.control.inventory_runner)
   identity=row['target']
  entry={k:row[k] for k in ('kind','target','name')};entry.update(identity=identity,rights=sorted(rights))
  with self.control.lock:
   entries=self.entries()
   if rid not in entries and len(entries)>=128:raise ApiError('授权对象数量已达上限',429)
   entries[rid]=entry;save(self.path,entries);self.control._audit(owner,'grant-set',rid)
  return {'ok':True,'resource':rid,'rights':entry['rights'],'requires_helper':row['kind']=='system' and not self.helper_ready()}
 def remove(self,owner,rid):
  self.control.require(owner,'admin');row=self.find(rid)
  # Empty overrides also narrow a grant supplied by config.json.
  with self.control.lock:
   entries=self.entries();entries[rid]={k:row[k] for k in ('kind','target','name')}|{'identity':row.get('identity',row['target']),'rights':[]};save(self.path,entries);self.control._audit(owner,'grant-remove',rid)
  return {'ok':True}
 def list(self,owner):
  self.control.require(owner,'admin');return {'grants':[dict(resource=rid,**entry) for rid,entry in self.entries().items()],'system_helper_ready':self.helper_ready()}
 def command(self,rid,action):
  entry=self.entries().get(rid)
  if not entry or action not in entry['rights']:raise ApiError('此动作尚未授权',403)
  row=self.find(rid)
  if (row['kind'],row['target'])!=(entry['kind'],entry['target']):raise ApiError('对象身份已变化，需重新授权',409)
  if row['kind']=='container':
   if row.get('identity')!=entry['identity']:raise ApiError('容器已替换，需重新授权',409)
   return DOCKER+(['logs','--timestamps','--tail','100',entry['identity']] if action=='logs' else [action,entry['identity']])
  args=unit_commands(row['kind'],row['target'],action,self.control.inventory_runner)
  if row['kind']=='system':
   if not self.helper_ready():raise ApiError('请在服务器安装或更新系统服务执行器',403)
   return ['/usr/bin/sudo','-n',HELPER,'--unit',row['target'],action]
  return args
 def apply(self,data):
  entries=self.entries();rows=[]
  for source in data['resources']:
   row=dict(source);entry=entries.get(row['id'])
   if entry:
    matched=(row['kind'],row['target'])==(entry['kind'],entry['target']) and (row['kind']!='container' or row.get('identity')==entry['identity'])
    available=matched and (row['kind']!='system' or self.helper_ready())
    rights=entry['rights'] if available else []
    row.update(granted=matched,allowed_actions=[a for a in rights if a!='logs'],control=bool(set(rights)-{'logs'}),logs='logs' in rights,authorization_reason='' if available else '身份已变化或系统执行器未就绪')
   else:row['allowed_actions']=['start','stop','restart'] if row.get('control') else []
   rows.append(row)
  return {**data,'resources':rows}
