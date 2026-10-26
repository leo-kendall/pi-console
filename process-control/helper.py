#!/usr/bin/python3 -I
# SPDX-License-Identifier: Apache-2.0
"""Root-owned, SIGTERM-only helper. No shell, group signals or arbitrary paths."""
import os,sys,json,stat,signal,select,re
from pathlib import Path
sys.dont_write_bytecode=True
LIB=Path('/usr/local/lib/pi-console-process')

def safe(path):
 for p in (path,*path.parents):
  st=p.lstat()
  if stat.S_ISLNK(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:raise RuntimeError('unsafe helper installation')

def load_source(path):
 safe(path)
 namespace={'__name__':path.stem,'__file__':str(path)}
 exec(compile(path.read_bytes(),str(path),'exec'),namespace)
 return namespace

def terminate(pid,start,expected,read,policy,pidfd_open=os.pidfd_open,send_signal=signal.pidfd_send_signal,wait=select.select):
 def validate():
  p=read(pid)
  if p['start']!=start or fingerprint(p)!=expected:raise RuntimeError('进程身份已变化，请重新确认')
  allowed,reason=policy(p)
  if not allowed:raise RuntimeError(reason)
  if pid==os.getpid():raise RuntimeError('不能结束正在执行操作的助手')
  return p
 validate();fd=pidfd_open(pid)
 try:
  validate();send_signal(fd,signal.SIGTERM)
  if not wait([fd],[],[],4)[0]:return {'sent':True,'exited':False}
  return {'sent':True,'exited':True}
 finally:os.close(fd)


def main():
 if os.geteuid()!=0:raise RuntimeError('administrator execution required')
 for p in [LIB/'process_policy.py',LIB/'process_identity.py']:safe(p)
 # Compile the checked source bytes directly. -B disables writing caches but
 # does not stop Python loading an existing, possibly writable .pyc cache.
 identity=load_source(LIB/'process_identity.py')
 policy=load_source(LIB/'process_policy.py')
 global fingerprint
 read_process=identity['read_process'];fingerprint=identity['fingerprint']
 process_policy=policy['process_policy']
 args=sys.argv[1:]
 if len(args)==2 and args[0]=='read' and args[1].isdigit() and 1<=int(args[1])<2**31:
  result=read_process('/proc',int(args[1]))
 elif len(args)==4 and args[0]=='terminate' and all(x.isdigit() for x in args[1:3]) and 1<=int(args[1])<2**31 and 0<=int(args[2])<2**63 and re.fullmatch('[0-9a-f]{64}',args[3]):
  result=terminate(int(args[1]),int(args[2]),args[3],lambda pid:read_process('/proc',pid),process_policy)
 else:raise RuntimeError('invalid helper request')
 print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError) as e:print(json.dumps({'error':str(e)},ensure_ascii=False));raise SystemExit(1)
