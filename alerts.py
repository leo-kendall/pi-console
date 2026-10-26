# SPDX-License-Identifier: Apache-2.0
"""Persistent incident transitions, with consecutive samples and recovery hysteresis."""
import math,secrets,threading,time
from pathlib import Path
from control import ApiError,save,RESOURCES
from config import SETTINGS
DEFAULT={'temperature':75,'memory':90,'disk':90,'watch':[]}
def rules_valid(rules):
 if not isinstance(rules,dict) or set(rules)!=set(DEFAULT):raise ApiError('告警配置字段无效')
 for k,lo,hi in [('temperature',45,95),('memory',50,99),('disk',50,99)]:
  if type(rules[k]) not in (int,float) or not math.isfinite(rules[k]) or not lo<=rules[k]<=hi:raise ApiError('告警阈值超出允许范围')
 if not isinstance(rules['watch'],list) or len(rules['watch'])>32 or any(k not in RESOURCES for k in rules['watch']) or len(set(rules['watch']))!=len(rules['watch']):raise ApiError('告警对象不在允许范围')
 return {**rules,'watch':list(rules['watch'])}
class Alerts:
 def __init__(self,path=Path(__file__).resolve().parent/'state/alerts.json',expected_disks=None):
  import json
  self.path=Path(path);self.lock=threading.RLock();self.counters={}
  self.data=json.loads(self.path.read_text()) if self.path.exists() else {'rules':dict(DEFAULT),'active':{},'events':[],'sampled_at':None}
  self.data['expected_disks']=list(expected_disks) if expected_disks is not None else list(SETTINGS['disks'])
  self.data['rules']['watch']=[key for key in self.data['rules']['watch'] if key in RESOURCES]
  for key in list(self.data['active']):
   removed=key.startswith('service-') and key[8:] not in self.data['rules']['watch']
   for prefix in ('data-disk-','disk-'):
    if key.startswith(prefix) and key[len(prefix):] not in self.data['expected_disks']:removed=True
   if removed:self.event(key,'已移除监控对象','配置已移除此对象；此记录不表示设备已恢复','resolved',time.time())
 def snapshot(self):
  import copy
  with self.lock:return copy.deepcopy(dict(rules=self.data['rules'],active=list(self.data['active'].values()),events=self.data['events'][-128:],sampled_at=self.data['sampled_at'],services_sampled_at=self.data.get('services_sampled_at'),available_watches=[{'id':k,'name':v[0]} for k,v in RESOURCES.items()]))
 def event(self,key,title,message,state,now):
  event=dict(id=secrets.token_hex(12),key=key,title=title,message=message,state=state,time=now)
  self.data['events'].append(event);self.data['events']=self.data['events'][-128:]
  if state=='active':self.data['active'][key]=dict(event)
  else:self.data['active'].pop(key,None)
 def configure(self,rules):
  checked=rules_valid(rules)
  with self.lock:
   for key in list(self.data['active']):
    if key.startswith('service-') and key[8:] not in checked['watch']:self.event(key,'已取消监控','该服务的异常监控已关闭','resolved',time.time())
   self.data['rules']=checked;self.counters={};save(self.path,self.data)
   return self.snapshot()
 def update(self,point,resources,now=None):
  now=time.time() if now is None else now
  with self.lock:
   conditions={};rules=self.data['rules'];active=self.data['active']
   if point is not None:
    for key,title,suffix in [('temperature','处理器温度','°C'),('memory','内存使用率','%')]:
     value=point.get(key);known=type(value) in (int,float) and math.isfinite(value)
     conditions['data-'+key]=(not known,title+'读数不可用','请检查采样状态')
     if known:
      threshold=rules[key]-(5 if key in active else 0)
      conditions[key]=(value>=threshold if key not in active else value>threshold,title+'偏高',f'当前 {value:.1f}{suffix}，阈值 {rules[key]}{suffix}')
    disks={d['path']:d for d in point.get('disks',[])}
    for path in self.data['expected_disks']:
     d=disks.get(path);mounted=point.get('storage_mounts',{}).get(path,True)
     known=bool(d) and type(d.get('total')) in (int,float) and d['total']>0 and type(d.get('used')) in (int,float) and math.isfinite(d['total']) and math.isfinite(d['used']) and 0<=d['used']<=d['total'] and mounted
     conditions['data-disk-'+path]=(not known,'磁盘读数不可用',path+' 未挂载或容量采样不可用，请检查数据盘')
     if known:
      key='disk-'+path;percent=100*d['used']/d['total'];threshold=rules['disk']-(3 if key in active else 0)
      conditions[key]=(percent>threshold if key in active else percent>=threshold,'磁盘空间不足',path+f' 已用 {percent:.1f}%')
    self.data['sampled_at']=now
   if resources is not None:
    byid={r['id']:r for r in resources}
    for rid in rules['watch']:
     r=byid.get(rid);state=r['state'] if r else 'unknown';running=state=='running' or state.startswith('active/')
     conditions['service-'+rid]=(not running,(r['name'] if r else rid)+'未正常运行','当前状态：'+state)
    self.data['services_sampled_at']=now
   for key,(bad,title,message) in conditions.items():
    old=self.counters.get(key,(None,0));count=old[1]+1 if old[0]==bad else 1;self.counters[key]=(bad,count)
    if bad and key not in active and count>=3:self.event(key,title,message,'active',now)
    elif not bad and key in active and count>=2:self.event(key,title+' · 已恢复',message,'resolved',now)
    elif bad and key in active:active[key]['message']=message
   save(self.path,self.data)
 def start(self,telemetry,control,stop=None):
  stop=stop or threading.Event()
  def metrics_loop():
   while not stop.is_set():
    try:
     points=telemetry.history('5m')['points'];point=points[-1] if points else {}
     if time.time()-point.get('time',0)>20:point={}
     self.update(point,None)
    except (OSError,ValueError,KeyError,ApiError):pass
    stop.wait(15)
  def services_loop():
   while not stop.is_set():
    try:
     resources=control.resources()['resources']
     if not stop.is_set():self.update(None,resources)
    except (OSError,ValueError,KeyError,ApiError):pass
    stop.wait(60)
  threading.Thread(target=metrics_loop,name='alert-metrics',daemon=True).start()
  threading.Thread(target=services_loop,name='alert-services',daemon=True).start()
  return stop
