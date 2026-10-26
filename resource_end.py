# SPDX-License-Identifier: Apache-2.0
"""Per-operation confirmation for discovered applications; no durable grants."""
import base64,hashlib,hmac,json,re,secrets,threading,time
from control import ApiError,DOCKER
from discovery import run_inventory
from process_policy import CORE_UNITS

def protected_unit(name):
 return name in CORE_UNITS or name in {'dbus.service','dbus-broker.service','gnome-shell.service','gnome-session.service'} or name.startswith(('user@','gnome-session','org.gnome.Shell@','gdm-'))

def annotate_inventory(data):
 rows=[]
 for source in data['resources']:
  row=dict(source)
  running=row.get('state','').startswith('active') or row.get('state') in ('running','paused','restarting')
  protected=row['kind']!='container' and protected_unit(row['target'])
  row.update(can_authorize_end=running and not protected,end_reason='系统基础组件保持只读' if protected else '当前没有可结束的运行对象' if not running else '可在 App 内确认授权后结束此对象')
  rows.append(row)
 return {**data,'resources':rows}

class ResourceEnd:
 def __init__(self,control,processes,reader=run_inventory,clock=time.time):
  self.control=control;self.processes=processes;self.reader=reader;self.clock=clock
  self.key=secrets.token_bytes(32);self.lock=threading.RLock();self.used={}
 def _find(self,rid):
  rows=self.control.resources()['resources']
  row=next((r for r in rows if r['id']==rid),None)
  if not row:raise ApiError('对象已不存在，请刷新列表',409)
  return row
 def _inspect(self,owner,rid):
  row=self._find(rid);kind,target=row['kind'],row['target']
  result=dict(rid=rid,kind=kind,target=target,name=row['name'],pid=0,start=0,proc_ticket='',unit_id='',invocation='')
  if kind=='container':
   identity=row.get('identity','')
   if not re.fullmatch('[0-9a-f]{64}',identity):raise ApiError('容器身份不可用，请更新后端并刷新',409)
   if row['state'] not in ('running','paused','restarting'):raise ApiError('容器当前未运行',409)
   return {**result,'mode':'container-stop','identity':identity,'description':'将正常停止这个容器，其应用请求和任务会中断。仅授权本次操作。'}
  if kind not in ('user','system') or protected_unit(target):raise ApiError('系统基础组件保持只读',403)
  properties=['Id','Names','LoadState','ActiveState','MainPID','InvocationID','ControlGroup','RefuseManualStop','RequiredBy','BoundBy','ConsistsOf','PropagatesStopTo']
  args=['/usr/bin/systemctl']+(['--user'] if kind=='user' else [])+['show','--no-pager','--property='+','.join(properties),'--',target]
  try:values=dict(line.split('=',1) for line in self.reader(args).splitlines() if '=' in line)
  except Exception as exc:raise ApiError('无法核验服务身份，请刷新或检查读取权限',409) from exc
  canonical=values.get('Id','');names=set(values.get('Names','').split())|{canonical,target}
  if not canonical or any(protected_unit(n) for n in names) or values.get('RefuseManualStop')=='yes':raise ApiError('系统基础组件或禁止手动停止的服务保持只读',403)
  if values.get('LoadState')!='loaded' or values.get('ActiveState')!='active':raise ApiError('服务当前没有可结束的运行对象',409)
  try:pid=int(values.get('MainPID','0'))
  except ValueError:raise ApiError('服务主进程身份不可用',409)
  if pid<=1:raise ApiError('没有可结束的应用主进程',409)
  p=self.processes.detail(owner,pid);group=p.get('cgroup','');expected=values.get('ControlGroup','')
  if not expected.startswith('/') or canonical not in expected.split('/') or not (group==expected or group.startswith(expected+'/')):raise ApiError('服务与主进程身份不匹配，请重新确认',409)
  if not p.get('can_close'):raise ApiError(p.get('reason','系统基础进程保持只读'),403)
  if not p.get('control_available'):raise ApiError('此应用需要管理员进程权限，请先在服务器安装或更新进程管理助手',403)
  propagated=any(values.get(k,'').strip() for k in ('RequiredBy','BoundBy','ConsistsOf','PropagatesStopTo'))
  mode='user-stop' if kind=='user' and not propagated else 'process-terminate'
  description='将正常停止这个用户服务，相关任务会中断。仅授权本次操作。' if mode=='user-stop' else '仅向已核验的主进程发送正常结束请求。服务管理器可能自动重启它；这不会关闭开机启动。仅授权本次操作。'
  return {**result,'mode':mode,'identity':str(pid)+':'+str(p['start']),'pid':pid,'start':p['start'],'proc_ticket':p['ticket'],'unit_id':canonical,'invocation':values.get('InvocationID',''),'description':description+(' '+p['impact'] if p.get('impact') else '')}
 def _encode(self,payload):
  body=base64.urlsafe_b64encode(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()).decode().rstrip('=')
  return body+'.'+hmac.new(self.key,body.encode(),hashlib.sha256).hexdigest()
 def _decode(self,owner,ticket):
  try:
   if not isinstance(ticket,str) or len(ticket)>8192:raise ValueError()
   body,signature=ticket.rsplit('.',1)
   if not hmac.compare_digest(hmac.new(self.key,body.encode(),hashlib.sha256).hexdigest(),signature):raise ValueError()
   payload=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
   if payload['owner']!=owner or not self.clock()<payload['expires']<=self.clock()+121:raise ValueError()
   return payload
  except (ValueError,KeyError,TypeError,UnicodeError):raise ApiError('本次授权已失效，请重新打开确认',409)
 def prepare(self,owner,rid):
  if not isinstance(rid,str) or not re.fullmatch('[a-zA-Z0-9-]{1,64}',rid):raise ApiError('无效对象',400)
  inspected=self._inspect(owner,rid)
  payload={**inspected,'owner':owner,'expires':self.clock()+120,'nonce':secrets.token_hex(16)}
  return dict(ready=True,resource=rid,name=inspected['name'],target=inspected['target'],mode=inspected['mode'],description=inspected['description'],ticket=self._encode(payload))
 def _fresh(self,owner,payload):
  fresh=self._inspect(owner,payload['rid'])
  if any(fresh[k]!=payload[k] for k in ('kind','target','identity','mode','pid','start','unit_id','invocation')):raise ApiError('对象身份或运行状态已变化，请重新确认',409)
  if payload['kind']!='container':self.processes.validate(owner,payload['pid'],payload['start'],payload['proc_ticket'])
 def submit(self,owner,ticket,request):
  if not isinstance(request,str) or not re.fullmatch('[a-zA-Z0-9-]{12,64}',request):raise ApiError('无效请求标识')
  payload=self._decode(owner,ticket)
  with self.lock:
   if self.clock()>=payload['expires']:raise ApiError('本次授权已过期，请重新确认',409)
   prior=self.control.by_request(owner,request)
   action='terminate' if payload['mode']=='process-terminate' else 'stop'
   if prior['found']:
    operation=prior['operation']
    if operation['resource']!=payload['rid'] or operation['action']!=action:raise ApiError('请求标识已用于其他操作',409)
    return operation
   now=self.clock()
   if now>=payload['expires']:raise ApiError('本次授权已过期，请重新确认',409)
   self.used={k:v for k,v in self.used.items() if v>now}
   if payload['nonce'] in self.used:raise ApiError('本次授权已使用，请查询原操作',409)
   if len(self.used)>=1024:raise ApiError('操作过多，请稍后重试',429)
   self._fresh(owner,payload)
   if self.clock()>=payload['expires']:raise ApiError('本次授权已过期，请重新确认',409)
   self.used[payload['nonce']]=payload['expires']
   def perform():
    if self.clock()>=payload['expires']:raise ApiError('本次授权已过期，请重新确认',409)
    self._fresh(owner,payload)
    if self.clock()>=payload['expires']:raise ApiError('本次授权已过期，请重新确认',409)
    if payload['mode']=='container-stop':self.control.runner(DOCKER+['stop','--time','10',payload['identity']])
    elif payload['mode']=='user-stop':self.control.runner(['/usr/bin/systemctl','--user','stop','--',payload['unit_id']])
    else:self.processes.terminate(owner,payload['pid'],payload['start'],payload['proc_ticket'])
   return self.control.enqueue(owner,payload['rid'],action,request,perform)
