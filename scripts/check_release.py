#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the exact Git source set; never echo secret matches."""
import argparse,hashlib,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_DIRS={'state','data','build','dist','tools','previews','__pycache__','.git'}
FORBIDDEN_SUFFIXES={'.apk','.jar','.class','.pyc','.p12','.pfx','.jks','.keystore','.pass','.key','.pem','.zip','.gz','.mp4','.jpg'}
# Only these reviewed source images may bypass the binary-content check.
# Updating it requires a new review and hash; other binary files remain rejected.
BINARY_ASSETS={
 'android/res/drawable-nodpi/pi_console_mark.png':'fa7d5dd3e7f59bcd9811a01786ea0ae748e9eefcf8bbabd7e1441a62fc73b51c',
 'docs/images/overview.png':'f2926b6d141d8b29cb66c5e9bcd0eeea699ab36f083f1ff3b8ea4044dc2d79f3',
 'docs/images/services.png':'e934ed1d6493bc67b45678e8665cc460450815872ecdab85fe7f586fa512d12b',
}
PATTERNS=[re.compile(p) for p in (rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{20,}',rb'github_pat_[A-Za-z0-9_]{20,}',rb'sk-(?:proj-)?[A-Za-z0-9_-]{32,}')]
def tracked_files(root=ROOT):
 result=subprocess.run(['git','ls-files','-z','--cached'],cwd=root,check=True,capture_output=True)
 return sorted(p.decode() for p in result.stdout.split(b'\x00') if p)
def scan_files(root,files):
 root=Path(root).resolve();errors=[]
 for name in files:
  p=root/name;relative=Path(name)
  if set(relative.parts)&FORBIDDEN_DIRS or p.suffix.lower() in FORBIDDEN_SUFFIXES or p.name in ('config.json','connection.json') or p.name.startswith('.env'):
   errors.append(name+': runtime, private configuration or binary must not be published');continue
  if p.is_symlink() or not p.resolve().is_relative_to(root) or not p.is_file():errors.append(name+': unsafe or missing source file');continue
  if p.stat().st_size>4*1024*1024:errors.append(name+': oversized source file');continue
  data=p.read_bytes()
  if name in BINARY_ASSETS:
   if hashlib.sha256(data).hexdigest()!=BINARY_ASSETS[name]:errors.append(name+': reviewed image hash mismatch')
   continue
  if b'\x00' in data or any(pattern.search(data) for pattern in PATTERNS):errors.append(name+': binary or credential-like content detected')
 return errors
def main():
 argparse.ArgumentParser(description=__doc__).parse_args();files=tracked_files()
 if not files:raise SystemExit('No staged/tracked source files; initialize the clean public repository first')
 errors=scan_files(ROOT,files)
 if errors:raise SystemExit('\n'.join(errors))
 print('Release source check passed: '+str(len(files))+' files, no forbidden runtime/binary files or detected secret patterns.')
if __name__=='__main__':main()
