#!/usr/bin/python3 -I
# SPDX-License-Identifier: Apache-2.0
"""Root-owned service controls with independent core/alias/dependency checks."""
import os,re,subprocess,sys,tempfile,time
UNITS={'display':'pi-console-display.service','printer':'cups-browsed.service'}
CORE={'init.service','dbus.service','dbus-broker.service','NetworkManager.service','wpa_supplicant.service','iwd.service','dhcpcd.service','dhclient.service','gdm.service','gdm3.service','display-manager.service','gnome-shell.service','polkit.service','accounts-daemon.service','rtkit-daemon.service'}
def protected(unit):
 return unit in CORE or unit.startswith(('systemd-','user@','user-runtime-dir@','gnome-session','org.gnome.Shell@','gdm-')) or unit.endswith(('.target','.mount','.automount','.device','.swap'))
def read_unit(args):
 with tempfile.TemporaryFile() as out:
  result=subprocess.run(args,stdout=out,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,timeout=4,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'})
  out.seek(0);data=out.read(65537)
  if result.returncode or len(data)>65536:raise ValueError('unit properties unavailable')
  return data.decode('utf-8','strict')
def unit_command(kind,unit,action,reader=read_unit):
 if kind not in ('user','system') or not isinstance(unit,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@:\\-]{0,240}\.service',unit) or action not in ('start','stop','restart','logs'):raise ValueError('unit/action refused')
 prefix=['/usr/bin/systemctl']+(['--user'] if kind=='user' else [])
 if action!='logs' and protected(unit):raise ValueError('core unit is read-only')
 seen=set();pending=[unit];started=time.monotonic()
 while pending:
  target=pending.pop()
  if target in seen:continue
  if len(seen)>=32 or time.monotonic()-started>6:raise ValueError('dependency inspection exceeds bounds')
  seen.add(target)
  if action!='logs' and protected(target):raise ValueError('core dependency is read-only')
  fields='Id,Names,LoadState,RefuseManualStop,RefuseManualStart,RequiredBy,BoundBy,ConsistsOf,PropagatesStopTo'
  values=dict(line.split('=',1) for line in reader(prefix+['show','--no-pager','--property='+fields,'--',target]).splitlines() if '=' in line)
  canonical=values.get('Id','');names=set(values.get('Names','').split())|{canonical,target}
  if not canonical or values.get('LoadState')!='loaded':raise ValueError('unit is not loaded')
  if action!='logs':
   if any(protected(n) for n in names) or values.get('RefuseManualStop')=='yes' or action in ('start','restart') and values.get('RefuseManualStart')=='yes':raise ValueError('unit or alias is read-only')
   for key in ('RequiredBy','BoundBy','ConsistsOf','PropagatesStopTo'):pending.extend(values.get(key,'').split())
  if target==unit:resolved=canonical
 if action=='logs':return ['/usr/bin/journalctl']+(['--user'] if kind=='user' else [])+['-u',resolved,'-n','100','--no-pager','-o','short-iso']
 return prefix+[action,'--',resolved]
def command(args,reader=read_unit):
 if len(args)==3 and args[0]=='--unit':return unit_command('system',args[1],args[2],reader)
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
