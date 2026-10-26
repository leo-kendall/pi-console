# SPDX-License-Identifier: Apache-2.0
"""Configuration-independent atomic local state persistence."""
import json,os
def save(path,data):
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 tmp=path.with_suffix('.tmp')
 fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
