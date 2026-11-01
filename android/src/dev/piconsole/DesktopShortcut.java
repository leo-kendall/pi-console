// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
/** Session-scoped Ctrl+Alt+Space latch. 0: pass, 1: consume, 2: toggle. */
final class DesktopShortcut {
 private boolean spaceHeld;
 int key(int code,boolean down,boolean ctrl,boolean alt,int repeat){
  if(code!=62)return 0;
  if(!down){if(!spaceHeld)return 0;spaceHeld=false;return 1;}
  if(spaceHeld)return 1;
  if(!ctrl||!alt)return 0;
  spaceHeld=true;return repeat==0?2:1;
 }
 void reset(){spaceHeld=false;}
}
