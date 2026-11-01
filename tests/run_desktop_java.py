# SPDX-License-Identifier: Apache-2.0
import os,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
jhome=Path(os.environ.get('JAVA_HOME','/nonexistent'))/'bin'
def tool(name):return str(jhome/name) if (jhome/name).exists() else name
with tempfile.TemporaryDirectory() as tmp:
 subprocess.run([tool('javac'),'--release','8','-d',tmp,str(root/'android/src/dev/piconsole/DesktopKeys.java'),str(root/'android/src/dev/piconsole/DesktopPointer.java'),str(root/'android/src/dev/piconsole/DesktopShortcut.java'),str(root/'tests/native/DesktopKeysTest.java'),str(root/'tests/native/DesktopPointerTest.java'),str(root/'tests/native/DesktopShortcutTest.java')],check=True)
 subprocess.run([tool('java'),'-cp',tmp,'dev.piconsole.DesktopKeysTest'],check=True)
 subprocess.run([tool('java'),'-cp',tmp,'dev.piconsole.DesktopPointerTest'],check=True)
 subprocess.run([tool('java'),'-cp',tmp,'dev.piconsole.DesktopShortcutTest'],check=True)
 android=os.environ.get('PI_ANDROID_JAR')
 if android:
  subprocess.run([tool('javac'),'--release','8','-classpath',android+os.pathsep+tmp,'-d',tmp,str(root/'android/src/dev/piconsole/DesktopInput.java'),str(root/'tests/native/DesktopClipboardTest.java')],check=True)
  subprocess.run([tool('java'),'-cp',tmp+os.pathsep+android,'dev.piconsole.DesktopClipboardTest'],check=True)
