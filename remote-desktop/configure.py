#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Preview/configure an existing local desktop. Never installs or alters services."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop import connection_parameters,load_connection,probe_vnc
from control import ApiError

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('action',choices=('preview','configure','probe'),nargs='?',default='preview')
 parser.add_argument('--output',type=Path,default=Path(__file__).with_name('connection.json'))
 args=parser.parse_args()
 try:
  if args.action=='probe':config=load_connection(args.output)
  else:
   raw=sys.stdin.read(16385)
   if len(raw)>16384:raise ValueError()
   config=json.loads(raw)
   if not isinstance(config,dict):raise ValueError()
  params=connection_parameters(config,1280,800)
  if args.action=='configure':
   # O_EXCL refuses existing files and symlinks; unrelated setups stay intact.
   fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
   try:
    with os.fdopen(fd,'w') as f:
     json.dump(config,f,ensure_ascii=False);f.write('\n');f.flush();os.fsync(f.fileno())
   except BaseException:
    args.output.unlink();raise
  elif args.action=='probe':
   if params['protocol']=='vnc':print(json.dumps(probe_vnc(params)));return 0
   print(json.dumps({'protocol':'rdp','state':'requires-guacd-connect','detail':'Use authenticated desktop/open to verify TLS pin and credentials with guacd; preview does not authenticate.'}));return 0
  print(json.dumps({'action':args.action,'protocol':params['protocol'],'host':params['hostname'],'port':int(params['port']),'security':params['security'],'credential_file':'created-private' if args.action=='configure' else 'unchanged','services':'unchanged','firewall':'unchanged','packages':'unchanged','note':'Existing server must listen on loopback. No desktop or bridge installer was executed.'}))
  return 0
 except (ApiError,OSError,ValueError,UnicodeError):
  print('Desktop configuration refused: check private JSON, protocol, loopback target and authentication; existing files and services retained.',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
