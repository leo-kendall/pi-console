# SPDX-License-Identifier: Apache-2.0
import sys,tempfile,unittest,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from control import Control, ApiError, command_for
from fixtures import configure_resources
configure_resources()

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.calls=[]
  self.c=Control(Path(self.tmp.name),runner=lambda args:self.calls.append(args) or 'ok')
 def tearDown(self):
  for _ in range(100):
   if not self.c.busy:break
   time.sleep(.01)
 def test_revoke_all_uses_shared_auth_lock(self):
  import fcntl,os
  code=self.c.new_code();token=self.c.pair(code)['token']
  self.c.revoke_all()
  with self.assertRaises(ApiError):self.c.authenticate(token)
  # Other code paths must see the same file-lock-protected state.
  other=Control(self.c.root,recover=False)
  with self.assertRaises(ApiError):other.authenticate(token)
 def test_separate_server_state_does_not_accept_another_servers_token(self):
  other=Control(Path(self.tmp.name)/'other-server')
  token=self.c.pair(self.c.new_code())['token']
  with self.assertRaises(ApiError):other.authenticate(token)
  other_token=other.pair(other.new_code())['token']
  with self.assertRaises(ApiError):self.c.authenticate(other_token)
  reopened=Control(Path(self.tmp.name))
  self.assertEqual(reopened.authenticate(token),self.c.authenticate(token))
 def test_revoke_all_waits_for_file_lock(self):
  import fcntl,threading
  entered=threading.Event();done=threading.Event()
  with (self.c.root/'auth.lock').open('a+') as f:
   fcntl.flock(f,fcntl.LOCK_EX)
   def revoke():
    entered.set();self.c.revoke_all();done.set()
   t=threading.Thread(target=revoke);t.start()
   self.assertTrue(entered.wait(1))
   try:self.assertFalse(done.wait(.1))
   finally:fcntl.flock(f,fcntl.LOCK_UN)
   t.join(2);self.assertTrue(done.is_set())
 def test_lookup_lost_action_response_without_reexecution(self):
  op=self.c.action('owner','proxy','restart','request-12345678')
  self.assertEqual(self.c.by_request('owner','request-12345678')['operation']['id'],op['id'])
  self.assertEqual(self.c.by_request('other','request-12345678'),{'found':False})
 def test_pair_consumed_and_revoke(self):
  code=self.c.new_code();token=self.c.pair(code)['token'];owner=self.c.authenticate(token)
  with self.assertRaises(ApiError):self.c.pair(code)
  self.c.revoke(owner)
  with self.assertRaises(ApiError):self.c.authenticate(token)
 def test_secret_not_persisted(self):
  code=self.c.new_code();token=self.c.pair(code)['token']
  self.assertNotIn(token,(self.c.root/'auth.json').read_text())
  self.assertNotIn(code,(self.c.root/'auth.json').read_text())
 def test_whitelist_and_shell_rejected(self):
  for resource,action in [('ssh','stop'),('proxy;id','start'),('proxy','restart;id'),('caddy','stop')]:
   with self.assertRaises(ApiError):command_for(resource,action)
 def test_deduplicate_and_ownership(self):
  first=self.c.action('owner','proxy','restart','request-12345678')
  second=self.c.action('owner','proxy','restart','request-12345678')
  self.assertEqual(first['id'],second['id'])
  for _ in range(100):
   if self.c.operation('owner',first['id'])['state'] not in ('queued','running'):break
   time.sleep(.01)
  self.assertEqual(len(self.calls),1)
  with self.assertRaises(ApiError):self.c.operation('other',first['id'])
 def test_reused_id_cannot_change_action(self):
  self.c.action('owner','proxy','start','request-12345678')
  with self.assertRaises(ApiError):self.c.action('owner','proxy','stop','request-12345678')
if __name__=='__main__':unittest.main()
