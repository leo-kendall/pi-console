# SPDX-License-Identifier: Apache-2.0
"""Optional root-owned process executor, installed only by a local admin."""
import json,os,stat,subprocess,time
from pathlib import Path
from control import ApiError,ROOT
HELPER=Path('/usr/local/bin/pi-console-process')
LIB=Path('/usr/local/lib/pi-console-process')
SOURCES={HELPER:ROOT/'process-control/helper.py',LIB/'process_policy.py':ROOT/'process_policy.py',LIB/'process_identity.py':ROOT/'process_identity.py'}
_checked=0.;_ready=False

def helper_ready():
 global _checked,_ready
 if time.monotonic()-_checked<1:return _ready
 _checked=time.monotonic();_ready=False
 try:
  for target,source in SOURCES.items():
   for p in (target,*target.parents):
    st=p.lstat()
    if stat.S_ISLNK(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:return False
   if target.read_bytes()!=source.read_bytes():return False
  _ready=True
 except OSError:pass
 return _ready

def invoke(*args):
 if not helper_ready():raise ApiError('此应用需要管理员执行权限，请先在树莓派启用管理员进程管理',403)
 try:
  r=subprocess.run(['/usr/bin/sudo','-n',str(HELPER),*map(str,args)],capture_output=True,text=True,timeout=10,stdin=subprocess.DEVNULL)
  data=json.loads(r.stdout)
  if r.returncode or 'error' in data:raise ApiError(data.get('error','管理员进程操作失败'),409)
  return data
 except (OSError,subprocess.TimeoutExpired,ValueError):raise ApiError('管理员执行权限尚未就绪，请检查一次性授权',503)
