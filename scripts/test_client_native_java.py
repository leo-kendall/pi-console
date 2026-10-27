#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Use the Android API jar only for linkage; no stub Android methods are invoked."""
import os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 tools=Path(os.environ.get('PI_TEST_ANDROID_TOOLS','/home/ikun/pi-lab/console/tools'))
 j=Path(os.environ.get('JAVA_HOME',str(tools/'root/usr/lib/jvm/java-21-openjdk-arm64')))/'bin'
 jar=tools/'android-35/android.jar'
 with tempfile.TemporaryDirectory(prefix='pi-text-export-') as temp:
  subprocess.run([str(j/'javac'),'--release','8','-cp',str(jar),'-d',temp,str(ROOT/'android/src/dev/piconsole/TextExport.java'),str(ROOT/'android/client-tests/TextExportTest.java')],check=True)
  subprocess.run([str(j/'java'),'-cp',temp+os.pathsep+str(jar),'dev.piconsole.TextExportTest'],check=True)
if __name__=='__main__':main()
