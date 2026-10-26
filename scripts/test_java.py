#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run platform-independent Java regressions without an Android emulator."""
import os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];src=ROOT/'android/src/dev/piconsole'
def main():
 java_home=Path(os.environ.get('JAVA_HOME','/nonexistent'))/'bin'
 javac=str(java_home/'javac') if (java_home/'javac').exists() else 'javac';java=str(java_home/'java') if (java_home/'java').exists() else 'java'
 names=['ServerEndpoint','UrlRules','HttpResponseParser','PollGate','BackupRules','AlertDelivery','PendingDocumentRequest']
 with tempfile.TemporaryDirectory(prefix='pi-console-java-') as temp:
  subprocess.run([javac,'--release','8','-d',temp,*map(str,[src/(n+'.java') for n in names]),*map(str,sorted((ROOT/'android/tests').glob('*.java')))],check=True)
  for name in ('PureLogicTest','BackupRulesTest','DeliveryRegressionTest','ServerEndpointTest'):subprocess.run([java,'-cp',temp,'dev.piconsole.'+name],check=True)
 with tempfile.TemporaryDirectory(prefix='pi-console-session-test-') as temp:
  support=sorted((ROOT/'android/test-support').rglob('*.java'))
  subprocess.run([javac,'--release','8','-d',temp,str(src/'ServerEndpoint.java'),str(src/'ServerSettings.java'),*map(str,support)],check=True)
  subprocess.run([java,'-cp',temp,'dev.piconsole.ServerSettingsTest'],check=True)
if __name__=='__main__':main()
