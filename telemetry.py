# SPDX-License-Identifier: Apache-2.0
"""Numeric-only in-memory history; no simulated samples."""
from collections import deque
import threading,time,os
from config import SETTINGS
class Telemetry:
 def __init__(self):self.lock=threading.Lock();self.points=deque(maxlen=1201);self.previous=None
 def sample(self):
  with self.lock:
   now=time.time();cpu=list(map(int,open('/proc/stat').readline().split()[1:9]));total=sum(cpu);idle=cpu[3]+cpu[4]
   mem=dict((l.split(':')[0],int(l.split()[1])*1024) for l in open('/proc/meminfo') if len(l.split())>=2)
   net={}
   for line in open('/proc/net/dev').read().splitlines()[2:]:
    name,values=line.split(':',1);v=values.split();name=name.strip()
    if name!='lo':net[name]=(int(v[0]),int(v[8]))
   point={'time':now,'cpu':None,'memory':100*(1-mem['MemAvailable']/mem['MemTotal']),'temperature':None,'network':{}}
   try:point['temperature']=int(open('/sys/class/thermal/thermal_zone0/temp').read())/1000
   except OSError:pass
   if self.previous:
    pt,pc,pi,pn=self.previous;dt=now-pt;delta=total-pc
    if delta>0:point['cpu']=max(0,min(100,100*(1-(idle-pi)/delta)))
    if 0<dt<15:
     for name,(rx,tx) in net.items():
      if name in pn and rx>=pn[name][0] and tx>=pn[name][1]:point['network'][name]={'rx':(rx-pn[name][0])/dt,'tx':(tx-pn[name][1])/dt}
   point['disks']=[];point['storage_mounts']={}
   for path in SETTINGS['disks']:
    mounted=path=='/' or os.path.ismount(path);point['storage_mounts'][path]=mounted
    if mounted and os.path.exists(path):
     s=os.statvfs(path);point['disks'].append({'path':path,'total':s.f_blocks*s.f_frsize,'used':(s.f_blocks-s.f_bfree)*s.f_frsize})
   self.previous=(now,total,idle,net);self.points.append(point)
 def history(self,window):
  if window not in ('5m','15m','60m'):raise ValueError('window')
  cutoff=time.time()-int(window[:-1])*60
  with self.lock:return {'points':[p for p in self.points if p['time']>=cutoff]}
 def start(self):
  def loop():
   while True:
    try:self.sample()
    except (OSError,ValueError,KeyError):
     with self.lock:self.points.append({'time':time.time(),'cpu':None,'temperature':None,'memory':None,'network':{},'disks':[]});self.previous=None
    time.sleep(3)
  threading.Thread(target=loop,daemon=True).start()
