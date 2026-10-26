# SPDX-License-Identifier: Apache-2.0
"""Report only available measured history, with explicit sample coverage."""
import math,time

def report(points,now=None):
 now=time.time() if now is None else now
 points=[p for p in points if type(p.get('time')) in (int,float) and math.isfinite(p['time']) and now-3600<=p['time']<=now]
 points.sort(key=lambda p:p['time']);result={'samples':len(points),'from':points[0]['time'] if points else None,'to':points[-1]['time'] if points else None,'gaps':sum(b['time']-a['time']>10 for a,b in zip(points,points[1:])),'sampled_at':now,'disks':points[-1].get('disks',[]) if points else []}
 for key in ['cpu','memory','temperature']:
  values=[p[key] for p in points if type(p.get(key)) in (int,float) and math.isfinite(p[key])]
  result[key]=dict(samples=len(values),average=sum(values)/len(values) if values else None,maximum=max(values) if values else None,minimum=min(values) if values else None,current=values[-1] if values else None)
 return result
