# SPDX-License-Identifier: Apache-2.0
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from control import ApiError
try:
 from live_logs import LiveLogs
except ImportError:
 LiveLogs=None

class Source:
 def __init__(self):self.text='one\ntwo\n';self.calls=0;self.denied=False
 def logs(self,r):
  self.calls+=1
  if self.denied:raise ApiError('denied',403)
  return {'text':self.text,'sampled_at':123}
class LiveLogTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(LiveLogs,'bounded follow API is required')
  self.source=Source();self.logs=LiveLogs(self.source);self.clock=patch('live_logs.time.monotonic',return_value=100);self.now=self.clock.start();self.addCleanup(self.clock.stop)
 def tail(self,owner='a',resource='photos',cursor=None):
  self.now.return_value+=2
  return self.logs.tail(owner,resource,cursor)
 def test_delta_repeat_rotation_and_lost_cursor(self):
  first=self.tail();self.assertTrue(first['reset']);self.assertEqual(first['lines'],['one','two'])
  same=self.tail(cursor=first['cursor']);self.assertEqual(same['lines'],[])
  self.source.text='two\nthree\n';new=self.tail(cursor=same['cursor']);self.assertEqual(new['lines'],['three']);self.assertFalse(new['reset'])
  self.source.text='rotated\n';rotated=self.tail(cursor=new['cursor']);self.assertTrue(rotated['reset']);self.assertEqual(rotated['lines'],['rotated'])
  lost=self.tail(cursor='0'*48);self.assertTrue(lost['reset'])
 def test_cursor_ownership_resource_and_permission(self):
  first=self.tail()
  for owner,resource in [('b','photos'),('a','proxy')]:
   with self.assertRaises(ApiError):self.tail(owner,resource,first['cursor'])
  self.source.denied=True
  with self.assertRaises(ApiError):self.tail(cursor=first['cursor'])
 def test_bounds_and_request_validation(self):
  self.source.text=('x'*10000+'\n')*5000
  r=self.tail();self.assertLessEqual(len(r['lines']),256);self.assertLessEqual(sum(len(s.encode()) for s in r['lines']),65536)
  for resource,cursor in [('../secret',None),('photos',[]),('photos','bad'),('',None)]:
   with self.assertRaises(ApiError):self.tail(resource=resource,cursor=cursor)
 def test_poll_rate_is_not_bypassed_by_fresh_cursor(self):
  self.tail()
  with self.assertRaises(ApiError) as e:self.logs.tail('a','photos')
  self.assertEqual(e.exception.code,429);self.assertEqual(self.source.calls,1)
 def test_state_is_bounded_and_expiry_resets(self):
  first=self.tail()
  for n in range(400):self.tail(owner='owner'+str(n))
  self.assertLessEqual(len(self.logs.sessions),128);self.assertLessEqual(len(self.logs.rates),256)
  self.now.return_value+=601
  self.assertTrue(self.tail(cursor=first['cursor'])['reset'])
