#!/usr/bin/python3 -I
# SPDX-License-Identifier: Apache-2.0
"""Root-owned fixed service controls; no shell and no caller-controlled units."""
import os,subprocess,sys
UNITS={'display':'pi-console-display.service','printer':'cups-browsed.service'}
def command(args):
 if len(args)!=2 or args[0] not in UNITS or args[1] not in ('start','stop','restart','logs','enable','disable'):raise ValueError('operation refused')
 unit=UNITS[args[0]]
 if args[1]=='logs':return ['/usr/bin/journalctl','-u',unit,'-n','100','--no-pager','-o','short-iso']
 return ['/usr/bin/systemctl',args[1],unit]
if __name__=='__main__':
 try:
  args=command(sys.argv[1:])
  if os.geteuid()!=0:raise ValueError('administrator required')
  r=subprocess.run(args,stdin=subprocess.DEVNULL,timeout=15,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'})
  raise SystemExit(r.returncode)
 except (ValueError,subprocess.TimeoutExpired) as e:print(str(e),file=sys.stderr);raise SystemExit(1)
