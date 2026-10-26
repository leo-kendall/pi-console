# SPDX-License-Identifier: Apache-2.0
import io,sys,socket,unittest,importlib.util,tempfile,json
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop import Desktop,Session,receive,instruction,certificate_pin
from control import ApiError
class SplitStream(io.BytesIO):
 def read(self,n=-1):return super().read(min(n,1))
class DesktopTests(unittest.TestCase):
 def test_certificate_pin_preserves_colon_separators(self):
  fingerprint='AB:'+':'.join(['CD']*31)
  self.assertEqual(certificate_pin('sha256 Fingerprint='+fingerprint),'sha256:'+fingerprint)
  with self.assertRaises(ApiError):certificate_pin('sha256 Fingerprint=bad')
 def test_fragmented_handshake(self):self.assertEqual(receive(SplitStream(instruction('args','hostname','port'))),['args','hostname','port'])
 def test_bad_frames_refused(self):
  for frame in (b'x.foo;',b'99999999.foo;',b'3.abcX',b'4.abc'):
   with self.assertRaises(ApiError):receive(io.BytesIO(frame))
 def test_session_owner_cannot_be_forged(self):
  m=Desktop();a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close);m.sessions['id']=Session(a,'owner')
  with self.assertRaises(ApiError):m.get('other','id')
  with self.assertRaises(ApiError):m.close('other','id')
  m.close('owner','id');self.assertNotIn('id',m.sessions)
 def test_dimensions_rejected_before_connection(self):
  m=Desktop()
  for w,h in [(True,800),(300,800),(1024,99999),('1024',768)]:
   with self.assertRaises(ApiError):m.open('owner',w,h)
 def test_high_resolution_handshake_is_accepted_and_lossless(self):
  # Only the external socket is replaced. Exercise the real validation and
  # protocol negotiation, never production credentials or a system desktop.
  class BridgeSocket:
   def __init__(self):self.sent=[]
   def sendall(self,data):self.sent.append(data)
   def makefile(self,*args,**kwargs):return io.BytesIO(instruction('args','width','height','force-lossless','cert-fingerprints','timezone')+instruction('ready','test'))
   def settimeout(self,*args):pass
   def shutdown(self,*args):pass
   def close(self):pass
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'remote-desktop').mkdir();config=root/'remote-desktop/connection.json'
   config.write_text(json.dumps({'username':'test','password':'not-a-real-secret','fingerprint':':'.join(['AB']*32)}));config.chmod(0o600)
   with patch('desktop.ROOT',root),patch('desktop.SETTINGS',{'desktop_timezone':'Europe/Berlin'},create=True):
    for width,height in [(1920,1080),(2354,1084),(2560,1440)]:
     bridge=BridgeSocket();m=Desktop()
     with patch('desktop.socket.create_connection',return_value=bridge):
      result=m.open('owner',width,height)
     self.assertEqual((result['width'],result['height']),(width,height))
     frames=[receive(io.BytesIO(frame)) for frame in bridge.sent]
     self.assertIn(['connect',str(width),str(height),'true','sha256:'+':'.join(['AB']*32),'Europe/Berlin'],frames)
     self.assertIn(['timezone','Europe/Berlin'],frames)
     m.close('owner',result['id'])
  for width,height in [(2561,1440),(2560,1441)]:
   with self.assertRaises(ApiError):Desktop().open('owner',width,height)
 def test_system_helper_rejects_core_services(self):
  p=Path(__file__).resolve().parents[1]/'system-control/helper.py';spec=importlib.util.spec_from_file_location('helper',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  for args in [['ssh','stop'],['display','stop','x'],['printer','mask'],['display;id','restart']]:
   with self.assertRaises(ValueError):m.command(args)
  self.assertEqual(m.command(['printer','enable']),['/usr/bin/systemctl','enable','cups-browsed.service'])
  self.assertNotIn('--now',m.command(['printer','disable']))
  self.assertEqual(m.command(['display','stop']),['/usr/bin/systemctl','stop','pi-console-display.service'])
if __name__=='__main__':unittest.main()
