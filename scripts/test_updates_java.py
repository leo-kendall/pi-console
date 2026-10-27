#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 j=Path(os.environ.get('JAVA_HOME','/home/ikun/pi-lab/console/tools/root/usr/lib/jvm/java-21-openjdk-arm64'))/'bin'
 with tempfile.TemporaryDirectory(prefix='console-updates-') as d:
  sources=list((ROOT/'android/src/dev/piconsole').glob('UpdateRules.java'))+list((ROOT/'android/src/dev/piconsole').glob('UpdateTransport.java'))+list((ROOT/'android/tests').glob('Update*Test.java'))
  subprocess.run([str(j/'javac'),'--release','8','-Xlint:-options','-d',d,*map(str,sources)],check=True)
  for p in (ROOT/'android/tests').glob('Update*Test.java'):subprocess.run([str(j/'java'),'-cp',d,'dev.piconsole.'+p.stem],check=True)
if __name__=='__main__':main()
