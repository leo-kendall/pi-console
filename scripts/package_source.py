#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export only checked Git source files, with a deterministic SHA-256 manifest."""
import hashlib,zipfile
from pathlib import Path
from check_release import ROOT,tracked_files,scan_files
def main():
 files=tracked_files();errors=scan_files(ROOT,files)
 if not files or errors:raise SystemExit('\n'.join(errors) or 'No source files selected')
 out=ROOT/'build/release';out.mkdir(parents=True,exist_ok=True);target=out/'pi-console-source-0.5.0.zip'
 with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
  manifest=[]
  for name in files:
   data=(ROOT/name).read_bytes();manifest.append(hashlib.sha256(data).hexdigest()+'  '+name)
   entry=zipfile.ZipInfo('pi-console/'+name,(2026,1,1,0,0,0));entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(entry,data)
  entry=zipfile.ZipInfo('pi-console/SOURCE_MANIFEST.sha256',(2026,1,1,0,0,0));entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(entry,'\n'.join(manifest)+'\n')
 digest=hashlib.sha256(target.read_bytes()).hexdigest();target.with_suffix('.zip.sha256').write_text(digest+'  '+target.name+'\n');print(str(target)+'\nSHA256 '+digest)
if __name__=='__main__':main()
