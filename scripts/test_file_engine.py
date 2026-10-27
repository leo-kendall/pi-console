#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compile/run real platform-independent transfer engine; no Android or live host."""
import os,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
java=Path(os.environ.get('JAVA_HOME','/nonexistent'))/'bin'
with tempfile.TemporaryDirectory(prefix='pi-file-tests-') as temp:
 subprocess.run([str(java/'javac') if (java/'javac').exists() else 'javac','--release','8','-d',temp,*map(str,[root/'android/src/dev/piconsole/TransferEngine.java',root/'android/src/dev/piconsole/TransferStore.java']),*map(str,(root/'android/file-tests').rglob('*.java'))],check=True)
 for name in ['TransferEngineTest','TransferStoreTest']:
  subprocess.run([str(java/'java') if (java/'java').exists() else 'java','-cp',temp,'dev.piconsole.'+name],check=True)
