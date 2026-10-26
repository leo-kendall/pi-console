# SPDX-License-Identifier: Apache-2.0
"""Manage only a receipt-owned, loopback-only optional guacd container."""
import argparse,json,subprocess
from pathlib import Path
from local_state import save
D=['/usr/bin/docker','--host=unix:///var/run/docker.sock'];NAME='pi-console-guacd';IMAGE='guacamole/guacd@sha256:8974eaa9ba32f713daf311e7cc8cd7e4cdfba1edea39eed75524e78ef4b08f4f'
ROOT=Path(__file__).resolve().parent;STATE=ROOT/'state/desktop-bridge.json'
def cmd(*args,check=True):return subprocess.run(D+list(args),check=check,text=True,capture_output=True)
def info():
 r=cmd('inspect',NAME,check=False)
 if r.returncode:return None
 v=json.loads(r.stdout)[0]
 if v['Config'].get('Labels',{}).get('dev.piconsole')!='desktop-v2' or v['Config']['Image']!=IMAGE:raise RuntimeError('Refusing foreign container')
 return v
def receipt():
 if STATE.is_symlink():raise RuntimeError('Unsafe bridge receipt')
 if not STATE.exists():return None
 data=json.loads(STATE.read_text())
 if set(data)!={'name','image','label','image_new_for_project'} or data['name']!=NAME or data['image']!=IMAGE or data['label']!='desktop-v2' or type(data['image_new_for_project'])!=bool:raise RuntimeError('Unknown bridge receipt retained')
 return data
def main():
 parser=argparse.ArgumentParser();parser.add_argument('action',nargs='?',default='status',choices=['install','uninstall','status']);parser.add_argument('--remove-image',action='store_true');args=parser.parse_args()
 v=info();record=receipt()
 if args.action=='install':
  if v and not record:raise RuntimeError('Container without ownership receipt retained')
  if v and v['State']['Status']=='running':print('Bridge already running');return
  if record is None:
   record={'name':NAME,'image':IMAGE,'label':'desktop-v2','image_new_for_project':cmd('image','inspect',IMAGE,check=False).returncode!=0};save(STATE,record)
  if v:cmd('rm','-f',NAME)
  cmd('run','--detach','--name',NAME,'--label','dev.piconsole=desktop-v2','--restart','unless-stopped','--network','host','--read-only',
      '--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--tmpfs','/home/guacd:rw,nosuid,size=8m,uid=1000,gid=1000','--cap-drop','ALL','--security-opt','no-new-privileges:true',
      '--memory','512m','--pids-limit','128','--health-cmd','nc -z 127.0.0.1 14822','--entrypoint','/opt/guacamole/sbin/guacd',IMAGE,'-f','-b','127.0.0.1','-l','14822','-p','/tmp/guacd.pid','-L','warning')
  print('Bridge installed on 127.0.0.1:14822')
 elif args.action=='uninstall':
  if record is None:
   if v:raise RuntimeError('Container without ownership receipt retained')
   print('No bridge receipt; no resources removed');return
  if v:cmd('rm','-f',NAME)
  if args.remove_image and record['image_new_for_project']:
   r=cmd('image','rm',IMAGE,check=False)
   if r.returncode and 'No such image' not in r.stderr:raise RuntimeError('Image still in use or removal failed; receipt retained')
  STATE.unlink();print('Bridge removed; pre-existing and shared images retained')
 else:print(json.dumps({'present':v is not None,'state':v['State']['Status'] if v else 'absent','receipt':record is not None}))
if __name__=='__main__':main()
