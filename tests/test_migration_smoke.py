# SPDX-License-Identifier: Apache-2.0
"""Run the actual server entrypoint against disposable legacy-format state."""
import hashlib,json,os,shutil,socket,subprocess,sys,tempfile,time,unittest,urllib.request
from pathlib import Path

class LegacyMigrationSmokeTests(unittest.TestCase):
 def test_actual_backend_start_preserves_legacy_pairing_alerts_and_user_files(self):
  source=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(prefix='console-migration-') as tmp,tempfile.TemporaryFile() as log:
   stage=Path(tmp)
   for p in source.glob('*.py'):shutil.copy2(p,stage/p.name)
   for directory in ('system-control','process-control','remote-desktop'):
    shutil.copytree(source/directory,stage/directory,ignore=shutil.ignore_patterns('__pycache__','connection.json'))
   state=stage/'state/control';state.mkdir(parents=True);token='disposable-legacy-migration-token';owner='legacy-device'
   (state/'auth.json').write_text(json.dumps({'devices':{hashlib.sha256(token.encode()).hexdigest():{'id':owner,'created':1700000000}},'pair':None}))
   (state/'actions.json').write_text('{}');(stage/'state/alerts.json').write_text(json.dumps({'rules':{'temperature':80,'memory':91,'disk':92,'watch':[]},'active':{},'events':[],'sampled_at':None}))
   files=stage/'data/files';files.mkdir(parents=True);(files/'retained.txt').write_text('legacy-user-file')
   (stage/'config.json').write_text(json.dumps({'name':'Migration fixture'}))
   with socket.socket() as reserve:reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
   process=subprocess.Popen([sys.executable,'-B','server.py','--port',str(port)],cwd=stage,env={**os.environ,'PI_CONSOLE_CONFIG':str(stage/'config.json')},stdout=log,stderr=log)
   opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
   def get(path):
    request=urllib.request.Request(f'http://127.0.0.1:{port}'+path,headers={'Authorization':'Bearer '+token})
    with opener.open(request,timeout=3) as response:return json.load(response)
   try:
    for _ in range(100):
     if process.poll() is not None:log.seek(0);self.fail('Isolated backend exited: '+log.read().decode(errors='replace')[-2000:])
     try:
      if get('/health')['status']=='ok':break
     except OSError:time.sleep(.05)
    else:self.fail('Isolated backend did not start')
    self.assertEqual(get('/api/session')['role'],'admin');self.assertEqual(get('/api/session')['id'],owner)
    self.assertEqual(get('/api/alerts')['rules']['temperature'],80)
    self.assertEqual(get('/api/alerts')['rules']['debounce_samples'],3)
    self.assertEqual(get('/api/files/list')['items'][0]['name'],'retained.txt')
    self.assertEqual(get('/api/status')['name'],'Migration fixture')
    self.assertIn('vnc',get('/api/desktop/capabilities')['protocols'])
    self.assertEqual((files/'retained.txt').read_text(),'legacy-user-file')
   finally:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
