# SPDX-License-Identifier: Apache-2.0
"""Bounded snapshot-follow; no long-lived child or caller-supplied command.

Cursors are opaque, owner/resource bound, and expire after five minutes.
Snapshot tails cannot distinguish a byte-identical replacement from no change.
"""
from collections import OrderedDict
import re,secrets,threading,time
from control import ApiError

class LiveLogs:
 def __init__(self,control):
  self.control=control;self.lock=threading.RLock();self.sessions=OrderedDict();self.rates=OrderedDict()
 def tail(self,owner,resource,cursor=None):
  if not isinstance(owner,str) or not owner or not isinstance(resource,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',resource):raise ApiError('无效日志对象')
  if cursor is not None and (not isinstance(cursor,str) or not re.fullmatch('[0-9a-f]{48}',cursor)):raise ApiError('无效日志游标')
  with self.lock:
   now=time.monotonic();identity=(owner,resource)
   for token,record in list(self.sessions.items()):
    if now-record['time']>300:del self.sessions[token]
   previous=self.sessions.get(cursor)
   if previous and previous['identity']!=identity:raise ApiError('日志游标不属于当前设备或对象',409)
   if identity in self.rates and now-self.rates[identity]<1.5:raise ApiError('日志读取过于频繁，请稍后重试',429)
   self.rates[identity]=now;self.rates.move_to_end(identity)
   while len(self.rates)>256:self.rates.popitem(last=False)
   # Re-check the underlying permission on EVERY accepted poll, including unchanged tails.
   data=self.control.logs(resource)
   text=str(data.get('text','')).encode('utf-8',errors='replace')[-65536:].decode('utf-8',errors='ignore')
   lines=[line[:4096] for line in text.splitlines()][-256:]
   reset=previous is None;delta=lines
   if previous is not None:
    old=previous['lines']
    if lines==old:delta=[]
    elif not old:delta=lines
    else:
     overlap=next((n for n in range(min(len(old),len(lines)),0,-1) if old[-n:]==lines[:n]),0)
     reset=not bool(overlap);delta=lines[overlap:] if overlap else lines
   token=secrets.token_hex(24)
   self.sessions[token]={'identity':identity,'lines':lines,'time':now}
   if previous is not None:self.sessions.pop(cursor,None)
   while len(self.sessions)>128:self.sessions.popitem(last=False)
   return {'lines':list(delta),'cursor':token,'reset':reset,'sampled_at':data.get('sampled_at',time.time()),'poll_after_ms':2000,'bounded':True}
