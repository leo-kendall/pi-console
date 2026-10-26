# SPDX-License-Identifier: Apache-2.0
"""Minimal /proc metadata and PID-reuse resistant identity; no secrets read."""
import hashlib,json,os
from pathlib import Path


def parse_stat(text,page_size):
 end=text.rfind(')');begin=text.index('(');f=text[end+2:].split()
 return dict(pid=int(text[:begin].strip()),name=text[begin+1:end][:80],state=f[0],ppid=int(f[1]),flags=int(f[6]),cpu_ticks=int(f[11])+int(f[12]),threads=int(f[17]),start=int(f[19]),virtual_bytes=int(f[20]),rss_bytes=max(0,int(f[21]))*page_size)


def read_process(proc,pid,page_size=None):
 p=Path(proc)/str(pid);page_size=page_size or os.sysconf('SC_PAGE_SIZE')
 v=parse_stat((p/'stat').read_text(),page_size)
 lines=(p/'status').read_text().splitlines();v['uids']=[int(n) for line in lines if line.startswith('Uid:') for n in line.split()[1:]]
 v['cgroup']=(p/'cgroup').read_text().splitlines()[0].split(':',2)[-1][:1024]
 try:
  v['exe']=os.readlink(p/'exe')[:1024];st=os.stat(p/'exe');v['trusted_exe']=st.st_uid==0 and not(st.st_mode&0o022)
 except OSError:v['exe']='';v['trusted_exe']=False
 after=parse_stat((p/'stat').read_text(),page_size)
 if after['start']!=v['start']:raise ProcessLookupError()
 return v


def fingerprint(p):
 value=[p[k] for k in ('pid','start','uids','exe','cgroup','flags','name')]
 return hashlib.sha256(json.dumps(value,separators=(',',':')).encode()).hexdigest()
