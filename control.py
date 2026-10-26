# SPDX-License-Identifier: Apache-2.0
"""Authenticated, bounded management of explicitly approved resources."""
import hashlib,json,os,re,secrets,subprocess,threading,time,fcntl
from contextlib import contextmanager
from pathlib import Path
from collections import deque
ROOT=Path(__file__).resolve().parent
DOCKER=['/usr/bin/docker','--host=unix:///var/run/docker.sock']
HELPER='/usr/local/bin/pi-console-control'
from config import SETTINGS
from discovery import collect_inventory,merge_inventory,run_inventory
RESOURCES=SETTINGS['resources']

class ApiError(Exception):
 def __init__(self,message,code=400):super().__init__(message);self.code=code

def digest(s):return hashlib.sha256(s.encode()).hexdigest()
from local_state import save

def execute(args):
 # File-backed bounded reader prevents arbitrary log output consuming memory.
 import tempfile
 with tempfile.TemporaryFile() as out:
  p=subprocess.Popen(args,stdout=out,stderr=out,stdin=subprocess.DEVNULL)
  try:p.wait(timeout=18)
  except subprocess.TimeoutExpired:
   p.kill();p.wait();raise ApiError('操作超时，请刷新状态核实结果',504)
  out.seek(0,2);size=out.tell();out.seek(max(0,size-65536));text=out.read(65536).decode('utf-8','replace')
  if p.returncode:raise ApiError('操作失败或权限未配置，请检查服务状态',503)
  return text

def command_for(rid,action):
 if rid not in RESOURCES or action not in ('start','stop','restart','logs','enable','disable'):raise ApiError('不允许的对象或操作')
 if action in ('enable','disable') and RESOURCES[rid][1]!='system':raise ApiError('仅允许修改指定辅助服务的启动设置')
 _,kind,name,_=RESOURCES[rid]
 if kind=='container':return DOCKER+(['logs','--tail','100',name] if action=='logs' else [action,name])
 if kind=='system':return ['/usr/bin/sudo','-n',HELPER,rid,action]
 if action=='logs':return ['/usr/bin/journalctl','--user','-u',name,'-n','100','--no-pager','-o','short-iso']
 return ['/usr/bin/systemctl','--user',action,name]

def locked_auth(function):
 def wrapped(self,*args,**kwargs):
  with self.lock:
   fd=os.open(self.root/'auth.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
   with os.fdopen(fd,'a+') as lockfile:
    fcntl.flock(lockfile,fcntl.LOCK_EX)
    return function(self,*args,**kwargs)
 return wrapped

class Control:
 def __init__(self,root=ROOT/'state/control',runner=execute,recover=True,inventory_runner=run_inventory):
  self.root=Path(root);self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
  self.lock=threading.RLock();self.runner=runner;self.inventory_runner=inventory_runner;self.attempts=deque();self.action_times={};self.busy=set()
  self.auth=self.read('auth.json',{'devices':{},'pair':None})
  self.operations=self.read('actions.json',{})
  if recover:
   for op in self.operations.values():
    if op['state'] in ('queued','running'):op['state']='uncertain';op['message']='服务重启，需刷新状态核实'
   self.persist_ops()
 def read(self,name,default):
  p=self.root/name
  if p.exists():return json.loads(p.read_text())
  return default
 def persist_ops(self):save(self.root/'actions.json',self.operations)
 @locked_auth
 def new_code(self):
  with self.lock:
   # CLI shares state with running server; readers reload auth under lock.
   self.auth=self.read('auth.json',self.auth);code=secrets.token_hex(4).upper()
   self.auth['pair']={'hash':digest(code),'expires':time.time()+600}
   save(self.root/'auth.json',self.auth);return code
 @locked_auth
 def pair(self,code):
  with self.lock:
   now=time.time()
   while self.attempts and self.attempts[0]<now-60:self.attempts.popleft()
   if len(self.attempts)>=5:raise ApiError('尝试过多，请一分钟后重试',429)
   self.attempts.append(now);self.auth=self.read('auth.json',self.auth);p=self.auth.get('pair')
   if not isinstance(code,str) or len(code)>32 or not p or p['expires']<now or not secrets.compare_digest(p['hash'],digest(code.strip().upper())):raise ApiError('配对码无效或已过期',401)
   if len(self.auth['devices'])>=16:raise ApiError('设备数量已达上限，请先撤销旧设备')
   token=secrets.token_urlsafe(32);owner=secrets.token_hex(12)
   self.auth['devices'][digest(token)]={'id':owner,'created':now};self.auth['pair']=None
   save(self.root/'auth.json',self.auth);return {'token':token,'device':owner}
 @locked_auth
 def authenticate(self,token):
  with self.lock:
   self.auth=self.read('auth.json',self.auth)
   if not isinstance(token,str) or len(token)>256:raise ApiError('请先配对设备',401)
   data=self.auth['devices'].get(digest(token))
   if not data:raise ApiError('请先配对设备',401)
   return data['id']
 @locked_auth
 def revoke(self,owner):
  with self.lock:
   self.auth=self.read('auth.json',self.auth)
   self.auth['devices']={k:v for k,v in self.auth['devices'].items() if v['id']!=owner}
   save(self.root/'auth.json',self.auth)
 @locked_auth
 def revoke_all(self):
  self.auth={'devices':{},'pair':None}
  save(self.root/'auth.json',self.auth)
 def by_request(self,owner,request):
  with self.lock:
   for op in self.operations.values():
    if op['owner']==owner and op['request']==request:return {'found':True,'operation':dict(op)}
   return {'found':False}
 def operations_for(self,owner):
  with self.lock:
   rows=sorted((v for v in self.operations.values() if v['owner']==owner),key=lambda x:x['created'],reverse=True)[:100]
   return {'operations':[{k:v for k,v in row.items() if k!='owner'} for row in rows]}
 def startup(self):
  result=[]
  source=ROOT/'system-control/helper.py'
  helper=Path(HELPER)
  available=helper.is_file() and helper.read_bytes()==source.read_bytes()
  for rid in [key for key,value in RESOURCES.items() if value[1]=='system']:
   label,kind,name,impact=RESOURCES[rid]
   try:
    raw=self.runner(['/usr/bin/systemctl','show',name,'-p','UnitFileState','-p','LoadState'])
    values=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
    loaded=values.get('LoadState')!='not-found';state=values.get('UnitFileState','unknown')
   except Exception:loaded=False;state='unknown'
   result.append(dict(id=rid,name=label,unit=name,state=state,control=available and loaded and state in ('enabled','disabled'),impact=impact))
  return {'units':result,'helper_ready':available or not result}
 def resources(self):
  inventory=collect_inventory(self.inventory_runner)
  found={(r['kind'],r['target']):r for r in inventory['resources']};result=[]
  for rid,(label,kind,name,impact) in RESOURCES.items():
   sources=[s for s in inventory['discovery']['sources'] if s['kind']==kind]
   complete=all(s['available'] and not s.get('invalid_records') for s in sources) and not inventory['discovery']['truncated']
   state=found.get((kind,name),{}).get('state','not-found' if complete else 'unavailable')
   enabled=kind!='system' or Path(HELPER).is_file()
   result.append(dict(id=rid,name=label,kind=kind,target=name,state=state,impact=impact,control=enabled and state not in ('not-found','unavailable'),logs=enabled))
  return merge_inventory(result,inventory)
 def logs(self,rid):return {'text':self.runner(command_for(rid,'logs'))[-65536:],'sampled_at':time.time()}
 def action(self,owner,rid,action,request):
  args=command_for(rid,action)
  if action=='logs' or not isinstance(request,str) or not re.fullmatch(r'[a-zA-Z0-9-]{12,64}',request):raise ApiError('无效请求标识')
  return self.enqueue(owner,rid,action,request,lambda:self.runner(args))
 def enqueue(self,owner,rid,action,request,execute_job):
  if not isinstance(request,str) or not re.fullmatch(r'[a-zA-Z0-9-]{12,64}',request):raise ApiError('无效请求标识')
  with self.lock:
   for op in self.operations.values():
    if op['owner']==owner and op['request']==request:
     if op['resource']!=rid or op['action']!=action:raise ApiError('请求标识已用于其他操作',409)
     return dict(op)
   now=time.time()
   if now-self.action_times.get(owner,0)<2:raise ApiError('操作过快，请稍候',429)
   if rid in self.busy:raise ApiError('此对象已有操作进行中',409)
   if len(self.operations)>=256:
    completed=[k for k,v in self.operations.items() if v['state'] not in ('queued','running')]
    if not completed:raise ApiError('操作队列已满',429)
    del self.operations[completed[0]]
   oid=secrets.token_hex(16);op=dict(id=oid,owner=owner,resource=rid,action=action,request=request,state='queued',message='等待执行',created=now)
   self.operations[oid]=op;self.persist_ops();self.action_times[owner]=now;self.busy.add(rid)
   threading.Thread(target=self.perform,args=(oid,execute_job),daemon=True).start();return dict(op)
 def perform(self,oid,execute_job):
  with self.lock:op=self.operations[oid];op['state']='running';op['message']='执行中';self.persist_ops()
  try:execute_job();state='success';message='操作完成，请查看最新状态'
  except Exception as e:state='uncertain';message=str(e) if isinstance(e,ApiError) else '执行异常，请刷新状态核实'
  with self.lock:op.update(state=state,message=message,updated=time.time());self.busy.discard(op['resource']);self.persist_ops()
 def operation(self,owner,oid):
  with self.lock:
   op=self.operations.get(oid)
   if not op or op['owner']!=owner:raise ApiError('操作不存在',404)
   return dict(op)
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['pair','revoke-all']);args=parser.parse_args();c=Control(recover=False)
 if args.action=='pair':print('配对码（10分钟有效，仅使用一次）：'+c.new_code())
 else:
  c.revoke_all()
  print('已撤销所有设备')
