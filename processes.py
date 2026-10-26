# SPDX-License-Identifier: Apache-2.0
"""Process sampling and exact-PID SIGTERM, with host OS essentials read-only."""
import hashlib,hmac,json,os,pwd,re,secrets,select,signal,threading,time
from pathlib import Path
from control import ApiError
from process_identity import parse_stat,read_process,fingerprint
from process_policy import process_policy,impact,critical_reason
from process_privilege import helper_ready,invoke

class Processes:
 def __init__(self,proc=Path('/proc'),policy=process_policy):
  self.proc=Path(proc);self.uid=os.getuid();self.policy=policy;self.key=secrets.token_bytes(32)
  self.ticks=os.sysconf('SC_CLK_TCK');self.page_size=os.sysconf('SC_PAGE_SIZE');self.lock=threading.RLock();self.previous={};self.last=0;self.cached=None
 def read(self,pid):return read_process(self.proc,pid,self.page_size)
 def needs_admin(self,p):return not p.get('uids') or any(v!=self.uid for v in p['uids'])
 def fresh(self,pid):
  p=self.read(pid)
  return invoke('read',pid) if self.needs_admin(p) and helper_ready() else p
 def parents(self,p):
  result={};pid=p['ppid']
  for _ in range(64):
   if pid<=1 or pid in result:break
   try:parent=self.read(pid)
   except (OSError,ValueError,IndexError):break
   result[pid]=parent;pid=parent['ppid']
  return result
 def protected(self,records=None):return set()  # Apps and their launchers are not host OS essentials.
 def permitted(self,p,parents,protected=None):
  if not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal'):return False,'系统不支持安全进程句柄，仅供查看'
  return self.policy(p,parents,self.uid,self.protected() if protected is None else protected)
 def public(self,p,parents,uptime,total,cpu=None,protected=None):
  allowed,reason=self.permitted(p,parents,protected)
  try:owner=pwd.getpwuid(p['uids'][0]).pw_name
  except (KeyError,IndexError):owner=str((p.get('uids') or [None])[0])
  available=allowed and (not self.needs_admin(p) or helper_ready())
  return {k:p[k] for k in ['pid','ppid','name','state','start','threads','rss_bytes','virtual_bytes','exe','cgroup']}|dict(owner=owner,cpu_percent=cpu,memory_percent=100*p['rss_bytes']/total if total else None,elapsed_seconds=max(0,uptime-p['start']/self.ticks),can_close=allowed,control_available=available,requires_admin=self.needs_admin(p),impact=impact(p,parents),category='system_core' if critical_reason(p) else 'exited' if p.get('state') in ('Z','X','x') else 'application',reason=reason)
 def snapshot(self):
  with self.lock:
   now=time.monotonic()
   if self.cached and now-self.last<2.5:return self.cached
   uptime=float((self.proc/'uptime').read_text().split()[0]);mem={line.split(':')[0]:int(line.split()[1])*1024 for line in (self.proc/'meminfo').read_text().splitlines()};records={}
   for path in self.proc.iterdir():
    if not path.name.isdigit():continue
    try:p=self.read(int(path.name));records[p['pid']]=p
    except (OSError,ValueError,IndexError):continue
   protected=self.protected(records);result=[];current={};groups={}
   for p in records.values():groups[p['cgroup']]=groups.get(p['cgroup'],0)+p['rss_bytes']
   for p in records.values():
    identity=(p['pid'],p['start']);old=self.previous.get(identity);cpu=None
    if old is not None and now>self.last:cpu=max(0,(p['cpu_ticks']-old)/self.ticks/(now-self.last)*100)
    current[identity]=p['cpu_ticks'];item=self.public(p,records,uptime,mem.get('MemTotal',0),cpu,protected)
    if item['can_close']:item['app_rss_bytes']=groups[p['cgroup']]
    result.append(item)
   result.sort(key=lambda p:p['rss_bytes'],reverse=True)
   # Show all identities; low-memory applications must remain discoverable.
   shown=result
   self.previous=current;self.last=now;self.cached=dict(processes=shown,count=len(result),shown=len(shown),closable=sum(p['can_close'] for p in result),admin_helper_ready=helper_ready(),sampled_at=time.time(),interval_seconds=3,memory_total=mem.get('MemTotal'),memory_available=mem.get('MemAvailable'))
   return self.cached
 def signature(self,owner,p):
  value=json.dumps([owner,fingerprint(p)],separators=(',',':'))
  return hmac.new(self.key,value.encode(),hashlib.sha256).hexdigest()
 def detail(self,owner,pid):
  if type(pid)!=int or not 1<=pid<2**31:raise ApiError('无效进程标识')
  try:p=self.fresh(pid)
  except (OSError,ValueError,IndexError):raise ApiError('进程已退出，请刷新列表',404)
  data=self.snapshot();item=next((x for x in data['processes'] if x['pid']==pid and x['start']==p['start']),None)
  public=self.public(p,self.parents(p),float((self.proc/'uptime').read_text().split()[0]),data['memory_total'],item['cpu_percent'] if item else None)
  public['ticket']=self.signature(owner,p) if public['control_available'] else None
  if public['can_close']:public['app_rss_bytes']=next((x.get('app_rss_bytes',x['rss_bytes']) for x in data['processes'] if x['pid']==pid and x['start']==p['start']),p['rss_bytes'])
  return public
 def validate(self,owner,pid,start,ticket):
  if type(pid)!=int or type(start)!=int or not 1<=pid<2**31 or start<0 or not isinstance(ticket,str) or not re.fullmatch('[0-9a-f]{64}',ticket):raise ApiError('无效进程请求')
  try:p=self.fresh(pid)
  except (OSError,ValueError,IndexError):raise ApiError('进程已退出，请刷新列表',404)
  if p['start']!=start:raise ApiError('进程已变化，请重新打开详情',409)
  allowed,reason=self.permitted(p,self.parents(p))
  if not allowed:raise ApiError(reason,403)
  if self.needs_admin(p) and not helper_ready():raise ApiError('此应用需要管理员执行权限，请先在树莓派启用管理员进程管理',403)
  if not hmac.compare_digest(self.signature(owner,p),ticket):raise ApiError('进程详情已变化，请重新确认',409)
  return p
 def terminate(self,owner,pid,start,ticket):
  p=self.validate(owner,pid,start,ticket)
  if self.needs_admin(p):
   result=invoke('terminate',pid,start,fingerprint(p))
   if not result.get('exited'):raise ApiError('已发送正常结束请求，进程仍在运行；请刷新核实',409)
   with self.lock:self.last=0
   return
  try:fd=os.pidfd_open(pid)
  except ProcessLookupError:raise ApiError('进程已退出，请刷新列表',404)
  try:
   self.validate(owner,pid,start,ticket)
   signal.pidfd_send_signal(fd,signal.SIGTERM)
   if not select.select([fd],[],[],4)[0]:raise ApiError('已发送退出请求，进程仍在运行；请刷新核实，不会强制结束',409)
   with self.lock:self.last=0
  finally:os.close(fd)
