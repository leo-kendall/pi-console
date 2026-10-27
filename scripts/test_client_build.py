#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compile/package the client in a disposable tree with documented integration hooks.
Only creates an ephemeral development signing key, never production material.
"""
import os,shutil,subprocess,tempfile,xml.etree.ElementTree as ET,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 tools=Path(os.environ['PI_TEST_ANDROID_TOOLS']) if os.environ.get('PI_TEST_ANDROID_TOOLS') else None
 with tempfile.TemporaryDirectory(prefix='pi-client-build-') as tmp:
  stage=Path(tmp)/'source';stage.mkdir();(stage/'scripts').mkdir()
  for name in ['android','third_party']:shutil.copytree(ROOT/name,stage/name)
  if os.environ.get('PI_TEST_DESKTOP_SOURCES'):
   for name in ['DesktopInput.java','DesktopKeys.java','DesktopPointer.java']:shutil.copy2(Path(os.environ['PI_TEST_DESKTOP_SOURCES'])/name,stage/'android/src/dev/piconsole'/name)
  for name in ['LICENSE','NOTICE','THIRD_PARTY_NOTICES.md']:shutil.copy2(ROOT/name,stage/name)
  shutil.copy2(ROOT/'scripts/build_android.py',stage/'scripts/build_android.py')
  a='http://schemas.android.com/apk/res/android';ET.register_namespace('android',a);manifest=stage/'android/AndroidManifest.xml';tree=ET.parse(manifest);m=tree.getroot()
  existing={n.get('{'+a+'}name') for n in m.findall('uses-permission')}
  for permission in ['android.permission.REQUEST_INSTALL_PACKAGES','android.permission.FOREGROUND_SERVICE_DATA_SYNC']:
   if permission not in existing:ET.SubElement(m,'uses-permission',{'{'+a+'}name':permission})
  app=m.find('application')
  if not any(n.get('{'+a+'}name')=='.UpdateService' for n in app.findall('service')):ET.SubElement(app,'service',{'{'+a+'}name':'.UpdateService','{'+a+'}exported':'false','{'+a+'}foregroundServiceType':'dataSync'})
  if not any(n.get('{'+a+'}name')=='.UpdateProvider' for n in app.findall('provider')):ET.SubElement(app,'provider',{'{'+a+'}name':'.UpdateProvider','{'+a+'}authorities':'dev.piconsole.updates','{'+a+'}exported':'false','{'+a+'}grantUriPermissions':'true'})
  tree.write(manifest,encoding='utf-8',xml_declaration=True)
  html=stage/'android/assets/index.html';s=html.read_text()
  for script in ['profiles-ui.js','updates-ui.js']:
   if 'src="'+script+'"' not in s:s=s.replace('</body>','<script src="'+script+'"></script></body>')
  html.write_text(s)
  env=dict(os.environ)
  if tools is not None:
   sdk=Path(tmp)/'sdk';(sdk/'platforms/android-35').mkdir(parents=True);(sdk/'platforms/android-35/android.jar').symlink_to(tools/'android-35/android.jar')
   env=dict(os.environ,ANDROID_HOME=str(sdk),JAVA_HOME=str(tools/'root/usr/lib/jvm/java-21-openjdk-arm64'),PI_ANDROID_AAPT2=str(tools/'root/usr/lib/android-sdk/build-tools/debian/aapt2'),PI_ANDROID_ZIPALIGN=str(tools/'root/usr/lib/android-sdk/build-tools/debian/zipalign'),PI_ANDROID_D8_JAR=str(tools/'r8.jar'),PI_ANDROID_APKSIGNER_JAR=str(tools/'root/usr/share/java/apksigner-35.0.2.jar'),PI_ANDROID_RESOURCE_JAR=str(tools/'android-29/android.jar'))
   env['LD_LIBRARY_PATH']=str(tools/'root/usr/lib/aarch64-linux-gnu')+':'+str(tools/'root/usr/lib/aarch64-linux-gnu/android')+':'+str(tools/'root/usr/lib/7zip')+':'+str(tools/'root/usr/lib')
  subprocess.run(['python3','-B','scripts/build_android.py'],cwd=stage,env=env,check=True)
  apk=stage/'build/pi-console-debug.apk';print('Disposable client full build: bytes='+str(apk.stat().st_size)+' sha256='+hashlib.sha256(apk.read_bytes()).hexdigest())
if __name__=='__main__':main()
