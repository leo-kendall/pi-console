// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
public final class DesktopKeysTest {
 public static void main(String[] args){
  check(DesktopKeys.keysym(113,0)==65507,"left control");check(DesktopKeys.keysym(114,0)==65508,"right control");
  check(DesktopKeys.keysym(57,0)==65513,"alt");check(DesktopKeys.keysym(117,0)==65515,"super");check(DesktopKeys.keysym(60,0)==65506,"right shift");
  check(DesktopKeys.keysym(19,0)==65362,"up");check(DesktopKeys.keysym(112,0)==65535,"delete");check(DesktopKeys.keysym(67,8)==65288,"backspace");
  check(DesktopKeys.keysym(131,0)==65470,"F1");check(DesktopKeys.keysym(142,0)==65481,"F12");
  check(DesktopKeys.keysym(29,'a')==97,"unmodified letter");check(DesktopKeys.keysym(29,'A')==65,"shifted letter");
  check(DesktopKeys.keysym(0,0x4e2d)==0x1004e2d,"unicode");check(DesktopKeys.keysym(0,0x1f680)==0x101f680,"supplementary unicode");
  check(DesktopKeys.keysym(4,0)==0,"Android back remains local");check(DesktopKeys.keysym(0,-1)==0,"dead/invalid unicode");check(DesktopKeys.keysym(0,0x110000)==0,"out of range");
  DesktopKeys.Pressed pressed=new DesktopKeys.Pressed();check(pressed.down(29,97)==97,"press records");check(pressed.up(29,65)==97,"release stable when shift changes");check(pressed.size()==0,"released");
  pressed.down(113,65507);pressed.down(29,97);check(pressed.release().length==2,"focus loss releases all");check(pressed.release().length==0,"focus loss idempotent");
  System.out.println("Desktop key mapping / stable releases / focus loss tests passed");
 }
 static void check(boolean condition,String reason){if(!condition)throw new AssertionError(reason);}
}
