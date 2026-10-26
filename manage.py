#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Preview/install/remove only this checkout's systemd user service."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from local_state import save

ROOT=Path(__file__).resolve().parent
def systemctl(args):subprocess.run(args,check=True,stdin=subprocess.DEVNULL,timeout=25)
def digest(data):return hashlib.sha256(data).hexdigest()
def safe(path):
 for p in (path,*path.parents):
  if p.is_symlink():raise RuntimeError('symlink path retained: '+str(p))
def unit_text(root):
 if any(c in str(root) for c in '\n\r%$"\\'):raise RuntimeError('checkout path contains unsupported systemd characters')
 quoted=json.dumps(str(root),ensure_ascii=False)
 return ('[Unit]\nDescription=Pi Console private server\nAfter=network.target\n\n[Service]\nType=simple\nWorkingDirectory='+quoted+'\nExecStart=/usr/bin/python3 -B '+json.dumps(str(root/'server.py'),ensure_ascii=False)+'\nEnvironment=PYTHONDONTWRITEBYTECODE=1\nRestart=on-failure\nRestartSec=5\nUMask=0077\n\n[Install]\nWantedBy=default.target\n').encode()
class Installer:
 def __init__(self,root=ROOT,home=None,runner=systemctl):
  self.root=Path(root).absolute();self.home=Path.home() if home is None else Path(home)
  self.unit=self.home/'.config/systemd/user/pi-console.service';self.enabled=self.unit.parent/'default.target.wants/pi-console.service'
  self.record=self.root/'state/install.json';self.runner=runner
 def command(self,*args):return self.runner(['/usr/bin/systemctl','--user',*args])
 def read(self):
  safe(self.record)
  if not self.record.exists():return None
  data=json.loads(self.record.read_text())
  if set(data)!={'version','root','unit_sha256','created_dirs'} or data['version']!=1 or data['root']!=str(self.root):raise RuntimeError('unknown install receipt retained')
  allowed={self.home/'.config',self.home/'.config/systemd',self.unit.parent,self.enabled.parent}
  if not isinstance(data['created_dirs'],list) or any(Path(p) not in allowed for p in data['created_dirs']):raise RuntimeError('invalid directory receipt retained')
  return data
 def check(self,record):
  safe(self.unit);safe(self.enabled.parent)
  if self.unit.exists() and (not record or digest(self.unit.read_bytes())!=record['unit_sha256']):raise RuntimeError('unowned or changed unit retained')
  if self.enabled.exists() or self.enabled.is_symlink():
   if not record or not self.enabled.is_symlink() or os.readlink(self.enabled)!=str(self.unit):raise RuntimeError('unowned or changed enable link retained')
 def install(self):
  if os.geteuid()==0:raise RuntimeError('Install the backend as a regular Linux user, without sudo')
  record=self.read();self.check(record);content=unit_text(self.root)
  created=record['created_dirs'] if record else [str(p) for p in [self.home/'.config',self.home/'.config/systemd',self.unit.parent,self.enabled.parent] if not p.exists()]
  safe(self.root/'state');save(self.record,dict(version=1,root=str(self.root),unit_sha256=digest(content),created_dirs=created))
  self.unit.parent.mkdir(parents=True,exist_ok=True);self.enabled.parent.mkdir(parents=True,exist_ok=True)
  save_bytes(self.unit,content)
  if not self.enabled.is_symlink():self.enabled.symlink_to(self.unit)
  self.command('daemon-reload');self.command('start','pi-console.service')
 def user_data(self):
  safe(self.root/'data');safe(self.root/'state')
  data=self.root/'data'
  if data.exists():
   if not data.is_dir():return True
   if any(p.name not in ('files','trash','uploads') for p in data.iterdir()):return True
   for folder in data.iterdir():
    safe(folder)
    if not folder.is_dir():return True
    if any(p.is_file() or p.is_symlink() for p in folder.rglob('*')):return True
  state=self.root/'state'
  if state.exists():
   if not state.is_dir():return True
   for p in state.iterdir():
    if p.name not in ('install.json','alerts.json','control'):return True
    safe(p)
    if p.name=='control':
     if not p.is_dir() or any(x.name not in ('auth.json','auth.lock','actions.json') or not x.is_file() or x.is_symlink() for x in p.iterdir()):return True
    elif not p.is_file():return True
  return any((self.root/'state'/name).exists() for name in ('remote-desktop.json','desktop-bridge.json'))
 def uninstall(self,purge=False):
  record=self.read()
  if record is None:raise RuntimeError('no installation receipt; existing resources retained')
  self.check(record)
  if purge and self.user_data():raise RuntimeError('user files or optional component receipts retained; remove them explicitly before purge')
  self.command('stop','pi-console.service')
  if purge and self.user_data():raise RuntimeError('new user files appeared during stop; runtime retained')
  self.check(record)
  self.enabled.unlink(missing_ok=True);self.unit.unlink(missing_ok=True);self.command('daemon-reload')
  for value in reversed(record['created_dirs']):
   p=Path(value)
   if p.exists() and not any(p.iterdir()):p.rmdir()
  self.record.unlink()
  if purge:
   for name in ('state','data'):
    p=self.root/name
    if p.exists():shutil.rmtree(p)
def save_bytes(path,data):
 safe(path)
 temp=path.with_name(path.name+'.pending')
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 finally:temp.unlink(missing_ok=True)
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['preview','install','uninstall'],nargs='?',default='preview');parser.add_argument('--apply',action='store_true');parser.add_argument('--purge-runtime',action='store_true');args=parser.parse_args();installer=Installer()
 if not args.apply:
  print('Preview only: '+args.action+' '+str(installer.unit)+' and its enable link. No reverse-proxy files are changed. Use --apply to execute.');return
 if args.action=='install':installer.install()
 elif args.action=='uninstall':installer.uninstall(args.purge_runtime)
 else:raise RuntimeError('preview has no apply action')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit(str(e))
