#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deterministically repack a compiled unsigned APK and sign using a private fixed key.
Does not generate keys, download tools, publish artifacts or read server configuration.
"""
import argparse,datetime,hashlib,json,os,re,stat,struct,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def fingerprint(value):
 value=value.replace(':','').lower()
 if not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('Expected certificate SHA256 must contain 64 hex digits')
 return value
def private_key(path,repo=ROOT):
 path=Path(path)
 if path.is_symlink() or not path.is_file() or path.resolve().is_relative_to(repo.resolve()):raise ValueError('Signing keystore must be a regular private file outside the repository')
 if stat.S_IMODE(path.stat().st_mode)&0o077:raise ValueError('Signing keystore must have mode 0600 or stricter')
 return path
def repack(source,target,epoch):
 timestamp=datetime.datetime.fromtimestamp(max(315532800,int(epoch)),datetime.timezone.utc)
 fixed=(timestamp.year,timestamp.month,timestamp.day,timestamp.hour,timestamp.minute,timestamp.second//2*2)
 with zipfile.ZipFile(source) as old:
  names=old.namelist()
  if len(set(names))!=len(names) or not {'AndroidManifest.xml','classes.dex'}<=set(names):raise ValueError('Invalid unsigned APK input')
  if any(n.startswith('/') or '..' in Path(n).parts or re.match(r'META-INF/.*\.(?:RSA|DSA|EC|SF)$',n,re.I) for n in names):raise ValueError('Input must be unsigned and contain safe paths')
  with zipfile.ZipFile(target,'w') as out:
   for name in sorted(names):
    # Android 11+ rejects compressed resources.arsc for target SDK 30+.
    item=zipfile.ZipInfo(name,fixed);item.create_system=3;item.external_attr=0o100644<<16;item.compress_type=zipfile.ZIP_STORED if name in {'classes.dex','resources.arsc'} else zipfile.ZIP_DEFLATED
    out.writestr(item,old.read(name),compresslevel=9)
def verify_resource_table(apk):
 with zipfile.ZipFile(apk) as archive:
  try:item=archive.getinfo('resources.arsc')
  except KeyError:raise ValueError('APK is missing resources.arsc') from None
  if item.compress_type!=zipfile.ZIP_STORED:raise ValueError('resources.arsc must be uncompressed for Android 11+')
  with Path(apk).open('rb') as stream:
   stream.seek(item.header_offset);header=stream.read(30)
  if len(header)!=30 or header[:4]!=b'PK\x03\x04':raise ValueError('Invalid resources.arsc local ZIP header')
  name_length,extra_length=struct.unpack_from('<HH',header,26)
  if (item.header_offset+30+name_length+extra_length)%4:raise ValueError('resources.arsc must be aligned to 4 bytes for Android 11+')
def verify_certificate(output,expected):
 found=re.findall(r'Signer #\d+ certificate SHA-256 digest:\s*([a-fA-F0-9]{64})',output)
 if found!=[fingerprint(expected)]:raise ValueError('Signed APK certificate does not match the approved fixed production signer')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--unsigned',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'build/pi-console-release.apk');p.add_argument('--expected-cert-sha256',required=True);p.add_argument('--source-date-epoch',type=int,default=os.environ.get('SOURCE_DATE_EPOCH'));a=p.parse_args()
 expected=fingerprint(a.expected_cert_sha256);key=private_key(Path(os.environ.get('PI_CONSOLE_KEYSTORE','')))
 alias=os.environ.get('PI_CONSOLE_KEY_ALIAS','')
 if not alias or not os.environ.get('PI_CONSOLE_KEYSTORE_PASSWORD'):raise ValueError('Private signing alias and password environment are required')
 if a.unsigned.is_symlink() or not a.unsigned.is_file() or a.output.is_symlink():raise ValueError('Invalid input/output file')
 epoch=a.source_date_epoch
 if epoch is None:epoch=int(subprocess.check_output(['git','show','-s','--format=%ct','HEAD'],cwd=ROOT,text=True).strip())
 java=Path(os.environ.get('JAVA_HOME','/nonexistent'))/'bin/java';java=str(java) if java.is_file() else 'java'
 sdk=Path(os.environ.get('ANDROID_HOME','/nonexistent'))/'build-tools'/os.environ.get('PI_ANDROID_BUILD_TOOLS','35.0.0')
 signer=[java,'-jar',os.environ['PI_ANDROID_APKSIGNER_JAR']] if os.environ.get('PI_ANDROID_APKSIGNER_JAR') else [str(sdk/'apksigner')]
 align=os.environ.get('PI_ANDROID_ZIPALIGN',str(sdk/'zipalign'))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='private-release-',dir=a.output.parent) as temporary:
  d=Path(temporary);repack(a.unsigned,d/'normalized.apk',epoch)
  subprocess.run([align,'-f','-p','4',str(d/'normalized.apk'),str(d/'aligned.apk')],check=True,stdin=subprocess.DEVNULL)
  subprocess.run([*signer,'sign','--ks',str(key),'--ks-key-alias',alias,'--ks-pass','env:PI_CONSOLE_KEYSTORE_PASSWORD','--v1-signing-enabled','true','--v2-signing-enabled','true','--v3-signing-enabled','true','--out',str(d/'signed.apk'),str(d/'aligned.apk')],check=True,stdin=subprocess.DEVNULL)
  verified=subprocess.check_output([*signer,'verify','--verbose','--print-certs',str(d/'signed.apk')],text=True,stdin=subprocess.DEVNULL);verify_certificate(verified,expected)
  subprocess.run([align,'-c','-p','4',str(d/'signed.apk')],check=True,stdin=subprocess.DEVNULL)
  verify_resource_table(d/'signed.apk')
  (d/'signed.apk').replace(a.output)
 digest=hashlib.sha256(a.output.read_bytes()).hexdigest();a.output.with_suffix('.apk.sha256').write_text(digest+'  '+a.output.name+'\n')
 print(json.dumps({'apk':str(a.output),'sha256':digest,'certificate_sha256':expected,'source_date_epoch':epoch}))
if __name__=='__main__':main()
