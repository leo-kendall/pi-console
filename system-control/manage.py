#!/usr/bin/python3
# SPDX-License-Identifier: Apache-2.0
"""Install/remove only this project's bounded, root-owned service executor."""
import hashlib,json,os,stat,subprocess,sys,tempfile,argparse,pwd,re
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]
LIB=Path('/usr/local/lib/pi-console-control');STATE=Path('/var/lib/pi-console-control');RECORD=STATE/'state.json'
HELPER=Path('/usr/local/bin/pi-console-control');RULE=Path('/etc/sudoers.d/pi-console-control')
RULE_BYTES=None

def sudo_rule(user):
 if not isinstance(user,str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}',user) or pwd.getpwnam(user).pw_uid==0:raise RuntimeError('Install requires --user for an existing non-root account')
 return (user+' ALL=(root) NOPASSWD: '+str(HELPER)+'\n').encode()


def safe(path,allow_missing=False):
 for p in (path,*path.parents):
  if not p.exists() and not p.is_symlink():
   if allow_missing:continue
   raise RuntimeError('missing installed path: '+str(p))
  s=p.lstat()
  if stat.S_ISLNK(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:raise RuntimeError('unsafe path retained: '+str(p))

def sha(b):return hashlib.sha256(b).hexdigest()

def write(path,data,mode):
 safe(path,True)
 fd,tmp=tempfile.mkstemp(prefix='.pi-console-process-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:os.fchmod(f.fileno(),mode);f.write(data);f.flush();os.fsync(f.fileno())
  if path==RULE:subprocess.run(['/usr/sbin/visudo','-cf',tmp],check=True,stdout=subprocess.DEVNULL)
  os.replace(tmp,path)
 finally:Path(tmp).unlink(missing_ok=True)

def main():
 global RULE_BYTES
 parser=argparse.ArgumentParser();parser.add_argument('action',nargs='?',default='preview',choices=['preview','install','uninstall']);parser.add_argument('--user',default=os.environ.get('SUDO_USER'));args=parser.parse_args();action=args.action
 if action=='install':RULE_BYTES=sudo_rule(args.user)
 if action not in ('preview','install','uninstall'):raise RuntimeError('Use preview/install/uninstall')
 if action=='preview':
  print('Root-owned fixed auxiliary-service executor. Only display/printer controls; no arbitrary units or shell. Creates '+str(HELPER)+', '+str(LIB)+', '+str(RULE)+', '+str(STATE)+'. All removable using uninstall.');return
 if os.geteuid()!=0:raise RuntimeError('Run using sudo /usr/bin/python3 -I -B '+str(Path(__file__).resolve())+' '+action)
 targets=[HELPER,RULE]
 for p in [STATE,RECORD,LIB,*targets]:safe(p,True)
 record=json.loads(RECORD.read_text()) if RECORD.exists() else {'files':{},'version':2,'created_dirs':[]}
 if set(record)!= {'files','version','created_dirs'} or record['version']!=2 or not isinstance(record['files'],dict) or not isinstance(record['created_dirs'],list) or set(record['created_dirs'])-set(map(str,[LIB,STATE])):raise RuntimeError('Unknown installation record retained')
 if set(record['files'])-set(map(str,targets)):raise RuntimeError('Unexpected installation targets retained')
 for p in targets:
  if p.exists() and sha(p.read_bytes()) not in record['files'].get(str(p),[]):raise RuntimeError('Unowned or modified file retained: '+str(p))
 if action=='uninstall':
  # Remove the sudo capability before the executables.
  for p in [RULE,HELPER]:
   if p.exists():p.unlink()
  if str(LIB) in record['created_dirs'] and LIB.exists():
   if any(LIB.iterdir()):raise RuntimeError('Unknown files in helper directory retained; remove or move them before retrying uninstall')
   LIB.rmdir()
  if STATE.exists() and any(x!=RECORD for x in STATE.iterdir()):raise RuntimeError('Unknown files in state directory retained; recovery record retained')
  if RECORD.exists():RECORD.unlink()
  if str(STATE) in record['created_dirs'] and STATE.exists():
   if any(STATE.iterdir()):raise RuntimeError('Unknown files in state directory retained')
   STATE.rmdir()
  print('Process executor and sudo rule removed; no system services changed');return
 payloads={HELPER:(SOURCE/'system-control/helper.py').read_bytes(),RULE:RULE_BYTES}
 # Persist intended directory ownership before creating LIB; existing empty
 # directories belong to their prior owner and are retained on uninstall.
 if not STATE.exists():
  STATE.mkdir(mode=0o700);record['created_dirs'].append(str(STATE))
 # Persist both previous and intended hashes before writes for interrupted install recovery.
 for p,b in payloads.items():record['files'][str(p)]=list(dict.fromkeys(record['files'].get(str(p),[])+[sha(b)]))
 write(RECORD,(json.dumps(record,indent=2)+'\n').encode(),0o600)
 for p,b in payloads.items():write(p,b,0o755 if p==HELPER else 0o440 if p==RULE else 0o644)
 print('Auxiliary service management enabled; app refresh is enough')

if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:print('Process executor setup: '+str(e)+'; existing recovery record retained.',file=sys.stderr);raise SystemExit(1)
