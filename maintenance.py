#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Local deployment checks and reversible source upgrades. All commands preview by default."""
import argparse,ast,fcntl,hashlib,json,os,re,secrets,shutil,stat,subprocess,sys,tempfile,time,zipfile
from contextlib import contextmanager
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parent
EXCLUDED={'.git','.superpowers','build','dist','tools','state','data','__pycache__','.idea','.vscode','previews'}
PRIVATE=('config.json','remote-desktop/connection.json','state/alerts.json','state/control/auth.json','state/control/grants.json','state/control/events.json')
SUFFIXES={'.py','.java','.js','.cjs','.mjs','.html','.css','.xml','.md','.json','.yml','.yaml','.txt','.svg','.png','.sh'}
def sha(data):return hashlib.sha256(data).hexdigest()
def safe(path):
 for p in (path,*path.parents):
  if p.is_symlink():raise RuntimeError('Symlink path retained: '+str(p))
def source_path(name):
 p=PurePosixPath(name)
 if not name or str(p)!=name or p.is_absolute() or any(x in ('..','.') or x in EXCLUDED for x in p.parts) or '\\' in name or any(ord(c)<32 for c in name):raise ValueError('Unsafe source path')
 if name in PRIVATE or p.name.startswith('.env') or p.suffix not in SUFFIXES and p.name not in ('LICENSE','NOTICE','.gitignore','.gitattributes','.editorconfig'):raise ValueError('Private or unsupported source file')
 return p
def atomic(path,data,mode=0o600):
 safe(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 fd,name=tempfile.mkstemp(prefix='.pi-console-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as out:os.fchmod(out.fileno(),mode);out.write(data);out.flush();os.fsync(out.fileno())
  os.replace(name,path)
 finally:Path(name).unlink(missing_ok=True)
def save(path,data):atomic(path,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())

def read_bundle(path):
 files={}
 with zipfile.ZipFile(path) as archive:
  entries=archive.infolist()
  if len(entries)>1200 or sum(e.file_size for e in entries)>64*1024**2:raise ValueError('Source archive exceeds limits')
  seen=set()
  for entry in entries:
   if entry.filename in seen:raise ValueError('Duplicate source archive entry')
   seen.add(entry.filename)
   if entry.is_dir():continue
   if not entry.filename.startswith('pi-console/'):raise ValueError('Unexpected source archive layout')
   name=entry.filename.removeprefix('pi-console/')
   if name=='SOURCE_MANIFEST.sha256':continue
   source_path(name)
   mode=(entry.external_attr>>16)&0o170000
   if mode not in (0,stat.S_IFREG) or entry.file_size>4*1024**2:raise ValueError('Unsafe source archive member')
   files[name]=archive.read(entry)
  manifest=archive.read('pi-console/SOURCE_MANIFEST.sha256')
  if len(manifest)>256*1024:raise ValueError('Source manifest exceeds limits')
  expected={}
  for line in manifest.decode().splitlines():
   match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
   if not match or match[2] in expected:raise ValueError('Invalid source manifest')
   expected[match[2]]=match[1]
  if expected!={name:sha(data) for name,data in files.items()}:raise ValueError('Source manifest mismatch')
 if not {'server.py','control.py'}<=set(files):raise ValueError('Source archive lacks required backend files')
 for name,data in files.items():
  if name.endswith('.py'):ast.parse(data,filename=name)
 return files

class Maintenance:
 def __init__(self,root=ROOT):
  self.root=Path(root).absolute();safe(self.root);self.directory=self.root/'state/maintenance'
 @contextmanager
 def locked(self):
  safe(self.directory);self.directory.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(self.directory,0o700)
  fd=os.open(self.directory/'lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'a+') as stream:fcntl.flock(stream,fcntl.LOCK_EX);yield
 def doctor(self):
  checks=[{'id':'python','ok':sys.version_info>=(3,11),'detail':'Python 3.11+ required'},{'id':'systemd','ok':bool(shutil.which('systemctl')),'detail':'User systemd required for managed service'},{'id':'docker','ok':bool(shutil.which('docker')),'optional':True,'detail':'Optional container support'},{'id':'source','ok':all((self.root/n).is_file() for n in ('server.py','control.py')),'detail':'Backend source files'},{'id':'write','ok':os.access(self.root,os.W_OK),'detail':'Checkout writable by deployment user'}]
  for name in PRIVATE:
   p=self.root/name
   if p.exists() or p.is_symlink():checks.append({'id':'private:'+name,'ok':not p.is_symlink() and p.is_file() and not p.stat().st_mode&0o077,'detail':'Private configuration should be a regular owner-only file'})
  pending=self.directory/'current.json'
  if pending.exists():
   safe(pending);receipt=json.loads(pending.read_text());checks.append({'id':'upgrade','ok':receipt.get('phase')!='applying','detail':'Use rollback to recover an interrupted upgrade' if receipt.get('phase')=='applying' else 'No interrupted source upgrade'})
  return {'checks':checks,'ok':all(c['ok'] for c in checks if not c.get('optional'))}
 def uninstall_preview(self):
  return {'preview':True,'unit':'pi-console.service','managed':(self.root/'state/install.json').is_file(),'user_data_retained':True,'optional_components':[name for name in ('state/remote-desktop.json','state/desktop-bridge.json') if (self.root/name).exists()],'instructions':'manage.py uninstall --apply removes only its own user service. Runtime data, private backups and source are retained; optional root helpers require their own uninstall commands.'}
 def checked_files(self,bundle):
  files=read_bundle(bundle)
  for name in files:
   p=self.root/name;safe(p)
   if p.exists() and not p.is_file():raise RuntimeError('Existing non-file retained: '+name)
  return files
 def preview(self,bundle):
  files=self.checked_files(bundle)
  return {'preview':True,'files':len(files),'changed':sum(not(self.root/name).exists() or (self.root/name).read_bytes()!=data for name,data in files.items()),'bytes':sum(map(len,files.values())),'private_backup':True,'data_retained':True,'service_restart':False}
 def _receipt(self,ident):
  if not isinstance(ident,str) or not re.fullmatch('[0-9]{8}T[0-9]{6}-[0-9a-f]{12}',ident):raise ValueError('Invalid backup ID')
  path=self.directory/'backups'/ident;safe(path)
  receipt=json.loads((path/'receipt.json').read_text())
  if receipt.get('version')!=1 or receipt.get('root')!=str(self.root) or receipt.get('id')!=ident or not isinstance(receipt.get('files'),dict):raise ValueError('Invalid backup receipt')
  for name,row in receipt['files'].items():
   source_path(name);safe(self.root/name)
   if set(row)!={'before','after','mode'}:raise ValueError('Invalid file receipt')
   if row['before'] is not None:
    p=path/'source'/name;safe(p)
    if sha(p.read_bytes())!=row['before']:raise RuntimeError('Backup source has changed; retained for recovery')
  return path,receipt
 def _restore(self,ident):
  backup,receipt=self._receipt(ident)
  # Validate every path/hash before changing any file.
  for name,row in receipt['files'].items():
   p=self.root/name;safe(p)
   current=sha(p.read_bytes()) if p.exists() and p.is_file() else None
   if current not in (row['before'],row['after']):raise RuntimeError('Changed source retained: '+name)
  for name,row in receipt['files'].items():
   p=self.root/name
   if row['before'] is None:p.unlink(missing_ok=True)
   else:atomic(p,(backup/'source'/name).read_bytes(),row['mode'])
  receipt['phase']='rolled-back';save(backup/'receipt.json',receipt);save(self.directory/'current.json',receipt)
  return {'rolled_back':True,'backup':ident,'data_retained':True}
 def rollback(self,ident,runner=None):
  with self.locked():
   # Full preflight before stopping an optional managed service.
   self._receipt(ident)
   if runner:runner('stop')
   try:return self._restore(ident)
   finally:
    if runner:runner('start')
 def upgrade(self,bundle,runner=None):
  files=self.checked_files(bundle)
  with self.locked():
   current=self.directory/'current.json'
   if current.exists() and json.loads(current.read_text()).get('phase')=='applying':raise RuntimeError('Interrupted upgrade retained; run rollback first')
   ident=time.strftime('%Y%m%dT%H%M%S',time.gmtime())+'-'+secrets.token_hex(6);backup=self.directory/'backups'/ident;safe(backup);backup.mkdir(mode=0o700,parents=True)
   receipt={'version':1,'root':str(self.root),'id':ident,'phase':'prepared','files':{}}
   for name,data in files.items():
    p=self.root/name;safe(p);old=p.read_bytes() if p.exists() else None
    receipt['files'][name]={'before':sha(old) if old is not None else None,'after':sha(data),'mode':stat.S_IMODE(p.stat().st_mode) if p.exists() else 0o644}
    if old is not None:atomic(backup/'source'/name,old)
   for name in PRIVATE:
    p=self.root/name;safe(p)
    if p.exists():
     if not p.is_file() or p.stat().st_size>4*1024**2:raise RuntimeError('Private configuration cannot be backed up safely')
     atomic(backup/'private'/name,p.read_bytes())
   save(backup/'receipt.json',receipt)
   if runner:runner('stop')
   receipt['phase']='applying';save(backup/'receipt.json',receipt);save(current,receipt)
   try:
    for name,data in files.items():atomic(self.root/name,data,receipt['files'][name]['mode'])
    if runner:runner('start')
    receipt['phase']='applied';save(backup/'receipt.json',receipt);save(current,receipt)
   except BaseException:
    self._restore(ident)
    if runner:
     try:runner('start')
     except Exception:pass
    raise
   return {'upgraded':True,'backup':ident,'files':len(files),'data_retained':True}

def service_runner(root):
 # Restart is permitted only for this checkout's installation receipt.
 from manage import Installer
 installer=Installer(root=root);receipt=installer.read()
 if receipt is None:raise RuntimeError('Managed service receipt required for --restart')
 installer.check(receipt)
 def run(action):
  installer.command(action,'pi-console.service')
  if action=='start':
   for _ in range(30):
    result=subprocess.run(['/usr/bin/systemctl','--user','is-active','pi-console.service'],capture_output=True,timeout=5)
    if result.returncode==0:
     import urllib.request
     try:
      with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:18765/health',timeout=2) as response:
       if response.status==200 and json.load(response).get('status')=='ok':return
     except (OSError,ValueError):pass
    time.sleep(.2)
   raise RuntimeError('Backend did not become healthy after restart')
 return run

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT)
 parser.add_argument('action',choices=['doctor','uninstall-preview','upgrade','rollback']);parser.add_argument('artifact',nargs='?');parser.add_argument('--apply',action='store_true');parser.add_argument('--restart',action='store_true');args=parser.parse_args();m=Maintenance(args.root)
 if args.action=='doctor':result=m.doctor()
 elif args.action=='uninstall-preview':result=m.uninstall_preview()
 elif not args.artifact:parser.error('upgrade requires source ZIP; rollback requires backup ID')
 elif args.action=='upgrade':result=m.upgrade(args.artifact,runner=service_runner(m.root) if args.restart else None) if args.apply else m.preview(args.artifact)
 elif not args.apply:
  m._receipt(args.artifact);result={'preview':True,'backup':args.artifact,'data_retained':True}
 else:result=m.rollback(args.artifact,runner=service_runner(m.root) if args.restart else None)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,zipfile.BadZipFile,KeyError,SyntaxError,subprocess.SubprocessError) as error:raise SystemExit(str(error))
