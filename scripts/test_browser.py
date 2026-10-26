#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run simulated UI checks in an isolated Firefox profile (Node 22+ required)."""
import os,shutil,socket,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEFAULTS=['test_setup_ui.mjs','test_ui.mjs','test_resource_layout_ui.mjs','test_discovery_ui.mjs','test_resource_end_ui.mjs','test_desktop_edge_ui.mjs']

def main():
 browser=os.environ.get('PI_FIREFOX') or shutil.which('firefox')
 if not browser:raise SystemExit('Firefox not found; set PI_FIREFOX to its executable.')
 for port in (18777,19226):
  with socket.socket() as probe:
   probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
   try:probe.bind(('127.0.0.1',port))
   except OSError:raise SystemExit(f'Test port {port} is in use; no existing process was changed.')
 with tempfile.TemporaryDirectory(prefix='pi-console-browser-') as profile,tempfile.TemporaryFile() as log:
  children=[]
  try:
   children.append(subprocess.Popen([sys.executable,'-B','scripts/preview_ui.py'],cwd=ROOT,stdout=log,stderr=log))
   children.append(subprocess.Popen([browser,'--headless','--no-remote','--profile',profile,'--remote-debugging-port','19226','about:blank'],cwd=ROOT,stdout=log,stderr=log))
   for port in (18777,19226):
    for _ in range(150):
     if any(p.poll() is not None for p in children):raise RuntimeError('Preview server or Firefox exited before tests started.')
     try:
      with socket.create_connection(('127.0.0.1',port),timeout=.2):break
     except OSError:time.sleep(.1)
    else:raise RuntimeError(f'Test port {port} did not become ready.')
   for name in sys.argv[1:] or DEFAULTS:
    subprocess.run(['node',str(ROOT/'scripts'/name)],cwd=ROOT,check=True,timeout=120)
  except BaseException:
   log.seek(0);print(log.read().decode(errors='replace')[-3000:],file=sys.stderr);raise
  finally:
   for child in children:child.terminate()
   for child in children:
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:child.kill();child.wait()
if __name__=='__main__':main()
