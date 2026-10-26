#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build with a standard Android SDK and JDK; never downloads tools or keys."""
import argparse,json,os,shutil,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(args):subprocess.run(list(map(str,args)),check=True,stdin=subprocess.DEVNULL)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--release',action='store_true');args=parser.parse_args()
 sdk=Path(os.environ.get('ANDROID_HOME',os.environ.get('ANDROID_SDK_ROOT','/nonexistent-android-sdk')))
 tools=sdk/'build-tools'/os.environ.get('PI_ANDROID_BUILD_TOOLS','35.0.0')
 platform=sdk/'platforms/android-35/android.jar';resource=Path(os.environ.get('PI_ANDROID_RESOURCE_JAR',str(platform)))
 jhome=Path(os.environ.get('JAVA_HOME','/nonexistent-java'))/'bin'
 java=str(jhome/'java') if (jhome/'java').exists() else 'java';javac=str(jhome/'javac') if (jhome/'javac').exists() else 'javac';keytool=str(jhome/'keytool') if (jhome/'keytool').exists() else 'keytool'
 aapt=Path(os.environ.get('PI_ANDROID_AAPT2',str(tools/'aapt2')));align=Path(os.environ.get('PI_ANDROID_ZIPALIGN',str(tools/'zipalign')))
 d8=[java,'-cp',os.environ['PI_ANDROID_D8_JAR'],'com.android.tools.r8.D8'] if 'PI_ANDROID_D8_JAR' in os.environ else [str(tools/'d8')]
 signer=[java,'-jar',os.environ['PI_ANDROID_APKSIGNER_JAR']] if 'PI_ANDROID_APKSIGNER_JAR' in os.environ else [str(tools/'apksigner')]
 for p in (platform,resource,aapt,align):
  if not p.is_file():raise SystemExit('Missing build input: '+str(p)+'; see docs/build.md')
 build=ROOT/'build';build.mkdir(exist_ok=True)
 work=build/'android'
 if work.is_symlink():raise SystemExit('Build directory must not be a symlink')
 if work.exists():shutil.rmtree(work)
 work.mkdir();classes=work/'classes';classes.mkdir();dex=work/'dex';dex.mkdir()
 run([javac,'--release','8','-classpath',platform,'-d',classes,*sorted((ROOT/'android/src').rglob('*.java'))])
 jar=work/'classes.jar'
 with zipfile.ZipFile(jar,'w') as out:
  for p in sorted(classes.rglob('*.class')):out.write(p,p.relative_to(classes))
 run([*d8,'--release','--min-api','26','--lib',platform,'--output',dex,jar])
 run([aapt,'compile','--dir',ROOT/'android/res','-o',work/'compiled.zip'])
 run([aapt,'link','--manifest',ROOT/'android/AndroidManifest.xml','-I',resource,'-o',work/'resources.ap_',work/'compiled.zip'])
 unsigned=work/'unsigned.apk'
 with zipfile.ZipFile(work/'resources.ap_') as res,zipfile.ZipFile(unsigned,'w',compression=zipfile.ZIP_DEFLATED) as out:
  for item in res.infolist():out.writestr(item,res.read(item.filename))
  for p in sorted((ROOT/'android/assets').rglob('*')):
   if p.is_file():out.write(p,'assets/'+str(p.relative_to(ROOT/'android/assets')))
  out.writestr('assets/LICENSE.txt',(ROOT/'LICENSE').read_bytes())
  out.writestr('assets/NOTICE.txt',(ROOT/'NOTICE').read_bytes()+b'\n'+(ROOT/'third_party/guacamole-NOTICE.txt').read_bytes()+b'\n'+(ROOT/'THIRD_PARTY_NOTICES.md').read_bytes())
  out.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_STORED)
 run([align,'-f','-p','4',unsigned,work/'aligned.apk'])
 if args.release:
  required=('PI_CONSOLE_KEYSTORE','PI_CONSOLE_KEY_ALIAS','PI_CONSOLE_KEYSTORE_PASSWORD')
  if any(not os.environ.get(k) for k in required):raise SystemExit('Release signing requires '+', '.join(required))
  keystore=Path(os.environ['PI_CONSOLE_KEYSTORE']);alias=os.environ['PI_CONSOLE_KEY_ALIAS'];password='env:PI_CONSOLE_KEYSTORE_PASSWORD'
  output=build/'pi-console-release.apk'
 else:
  keystore=build/'debug-signing.p12';alias='pi-console-debug';password='pass:android';output=build/'pi-console-debug.apk'
  if not keystore.exists():run([keytool,'-genkeypair','-keystore',keystore,'-storetype','PKCS12','-alias',alias,'-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=Pi Console development','-storepass','android','-keypass','android'])
 if keystore.is_symlink() or not keystore.is_file():raise SystemExit('Invalid keystore path')
 run([*signer,'sign','--ks',keystore,'--ks-key-alias',alias,'--ks-pass',password,'--out',output,work/'aligned.apk'])
 run([*signer,'verify','--verbose',output]);run([align,'-c','-p','4',output])
 print(json.dumps({'apk':str(output),'release_signing':args.release,'bytes':output.stat().st_size}))
if __name__=='__main__':main()
