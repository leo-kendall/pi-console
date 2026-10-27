#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Profile JVM boundary tests; never reads phone preferences or credentials."""
import os, subprocess, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 j=Path(os.environ['JAVA_HOME'])/'bin' if os.environ.get('JAVA_HOME') else Path(shutil.which('javac') or 'javac').parent
 with tempfile.TemporaryDirectory(prefix='console-client-tests-') as d:
  sources=[ROOT/'android/src/dev/piconsole'/n for n in ('ServerSettings.java','ServerEndpoint.java','StatusClient.java','ProbeRules.java')]
  sources+=list((ROOT/'android/test-support').rglob('*.java'))
  subprocess.run([str(j/'javac'),'--release','8','-Xlint:-options','-d',d,*map(str,sources)],check=True)
  for test in ['ServerSettingsTest','ProfileSettingsTest','ProfileRaceTest','ProfileTransportTest']:
   subprocess.run([str(j/'java'),'-cp',d,'dev.piconsole.'+test],check=True)
if __name__=='__main__':main()
