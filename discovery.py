# SPDX-License-Identifier: Apache-2.0
"""Read-only, bounded inventory. Discovery never grants control permissions."""
import hashlib,json,re,subprocess,tempfile,time
from concurrent.futures import ThreadPoolExecutor

MAX_OBJECTS=1000
class InventoryError(Exception):pass

def run_inventory(args,timeout=4,max_bytes=512*1024):
 with tempfile.TemporaryFile() as out:
  try:
   process=subprocess.Popen(args,stdout=out,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL)
   try:process.wait(timeout=timeout)
   except subprocess.TimeoutExpired:
    process.kill();process.wait();raise InventoryError('inventory timed out')
   if process.returncode:raise InventoryError('inventory unavailable')
   if out.tell()>max_bytes:raise InventoryError('inventory too large')
   out.seek(0);return out.read(max_bytes+1).decode('utf-8')
  except (OSError,UnicodeError) as exc:raise InventoryError('inventory unavailable') from exc

def _text(value,limit=256):
 return ''.join(c for c in str(value) if ord(c)>=32)[:limit]

def _row(kind,target,state,description='',**extra):
 return dict(id='found-'+hashlib.sha256((kind+':'+target).encode()).hexdigest()[:24],
  name=target,kind=kind,target=target,state=state,description=_text(description),
  impact='自动发现，尚未加入控制授权清单。',control=False,logs=False,configured=False,discovered=True,**extra)

def collect_inventory(runner=run_inventory):
 common=['--type=service','--no-legend','--no-pager','--output=json']
 jobs=[]
 for kind in ('user','system'):
  base=['/usr/bin/systemctl']+(['--user'] if kind=='user' else [])
  jobs.extend([(kind,'units',base+['list-units','--all','--plain',*common]),
               (kind,'files',base+['list-unit-files',*common])])
 template='{"id":{{json .ID}},"name":{{json .Names}},"state":{{json .State}},"status":{{json .Status}},"image":{{json .Image}}}'
 jobs.append(('container','containers',['/usr/bin/docker','--host=unix:///var/run/docker.sock','ps','-a','--no-trunc','--format',template]))
 def read(job):
  kind,source,args=job
  try:
   raw=runner(args)
   values=[json.loads(line) for line in raw.splitlines() if line.strip()] if kind=='container' else json.loads(raw)
   if not isinstance(values,list):raise ValueError()
   return values,True
  except Exception:return [],False
 with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(read,jobs))
 rows={};sources=[];partial=False;truncated=False
 # Installed files first, then overwrite their state with loaded-unit data.
 for index in (1,3,0,2,4):
  kind,source,_=jobs[index];values,available=results[index];invalid=0
  sources.append(dict(kind=kind,source=source,available=available))
  if not available:partial=True;continue
  for item in values:
   if not isinstance(item,dict):invalid+=1;continue
   target=item.get('name' if kind=='container' else 'unit_file' if source=='files' else 'unit')
   pattern=r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}' if kind=='container' else r'[A-Za-z0-9][A-Za-z0-9_.@:\\-]{0,240}\.service'
   if not isinstance(target,str) or not re.fullmatch(pattern,target):invalid+=1;continue
   key=kind,target
   if key not in rows and len(rows)>=MAX_OBJECTS:truncated=True;continue
   if source=='files':
    runtime_available=results[0 if kind=='user' else 2][1]
    rows[key]=_row(kind,target,'not-loaded' if runtime_available else 'unknown',unit_file_state=_text(item.get('state','unknown')))
   elif kind=='container':rows[key]=_row(kind,target,_text(item.get('state','unknown')),_text(item.get('status','')),image=_text(item.get('image','')),identity=_text(item.get('id',''),64))
   else:
    previous=rows.get(key,{})
    rows[key]=_row(kind,target,'not-found' if item.get('load')=='not-found' else _text(item.get('active','unknown'))+'/'+_text(item.get('sub','unknown')),item.get('description',''),unit_file_state=previous.get('unit_file_state','unknown'))
  if invalid:partial=True;sources[-1]['invalid_records']=invalid
 return dict(resources=list(rows.values()),sampled_at=time.time(),discovery=dict(supported=True,partial=partial or truncated,truncated=truncated,limit=MAX_OBJECTS,sources=sources))

def merge_inventory(configured,inventory):
 discovered={(r['kind'],r['target']):dict(r) for r in inventory['resources']}
 keys={(r['kind'],r['target']) for r in configured};used={r['id'] for r in configured}
 rows=[{**discovered.get((r['kind'],r['target']),{}),**r,'configured':True,'discovered':(r['kind'],r['target']) in discovered} for r in configured]
 for key,row in discovered.items():
  if key in keys:continue
  salt=0
  while row['id'] in used:
   salt+=1;row['id']='found-'+hashlib.sha256((repr(key)+':'+str(salt)).encode()).hexdigest()[:24]
  used.add(row['id']);rows.append(row)
 rank={'container':0,'user':1,'system':2}
 ordered=sorted(rows,key=lambda r:(not r.get('configured',False),rank.get(r['kind'],3),r['target'].lower(),r['id']))
 # Leave room for metadata and remain below the Android client's 1 MiB cap.
 size=8192;bounded=[];metadata=dict(inventory['discovery'])
 for row in ordered:
  cost=len(json.dumps(row,ensure_ascii=False).encode())+2
  if size+cost>768*1024 and not row.get('configured'):
   metadata.update(truncated=True,partial=True);continue
  bounded.append(row);size+=cost
 return {**inventory,'resources':bounded,'discovery':metadata}
