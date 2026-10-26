# SPDX-License-Identifier: Apache-2.0
"""Named file roots are provisioned locally; callers only select their IDs."""
import threading,time
from pathlib import Path
from files import Files,MAX_FILE
from control import ApiError

class FileSpaces:
 def __init__(self,base=None,roots=None):
  self.base=Path(base or Path(__file__).resolve().parent/'data');self.spaces={'default':Files(self.base)};self.names={'default':'独立文件区'}
  for key,entry in (roots or {}).items():
   self.spaces[key]=Files(self.base/'spaces'/key,root=entry['path'],writable=entry['writable']);self.names[key]=entry['name']
 def space(self,key='default'):
  if not isinstance(key,str) or key not in self.spaces:raise ApiError('文件目录未获本机配置授权',403)
  return self.spaces[key]
 def roots(self):return {'roots':[{'id':k,'name':self.names[k],'writable':v.writable,'max_file_bytes':MAX_FILE} for k,v in self.spaces.items()]}
 def start_cleanup(self):
  def loop():
   while True:
    for space in self.spaces.values():
     try:
      with space.lock:space.clean_expired()
     except (OSError,ValueError,ApiError):pass
    time.sleep(60)
  threading.Thread(target=loop,name='file-space-cleanup',daemon=True).start()
