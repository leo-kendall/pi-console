#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Use the Android API jar only for linkage; no stub Android methods are invoked."""
import os,subprocess,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 j=Path(os.environ['JAVA_HOME'])/'bin' if os.environ.get('JAVA_HOME') else Path(shutil.which('javac') or 'javac').parent
 jar=Path(os.environ.get('PI_ANDROID_TEST_JAR',str(Path(os.environ.get('ANDROID_HOME','/nonexistent-sdk'))/'platforms/android-35/android.jar')))
 if not jar.is_file():raise SystemExit('Set ANDROID_HOME or PI_ANDROID_TEST_JAR to Android Platform 35 for native linkage checks.')
 with tempfile.TemporaryDirectory(prefix='pi-text-export-') as temp:
  subprocess.run([str(j/'javac'),'--release','8','-cp',str(jar),'-d',temp,str(ROOT/'android/src/dev/piconsole/TextExport.java'),str(ROOT/'android/client-tests/TextExportTest.java')],check=True)
  subprocess.run([str(j/'java'),'-cp',temp+os.pathsep+str(jar),'dev.piconsole.TextExportTest'],check=True)
if __name__=='__main__':main()
