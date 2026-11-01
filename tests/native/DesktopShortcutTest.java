// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
public final class DesktopShortcutTest {
 public static void main(String[] args){
  DesktopShortcut s=new DesktopShortcut();
  check(s.key(62,true,false,false,0)==0,"ordinary Space stays local/remote input");
  check(s.key(62,true,true,false,0)==0,"Ctrl+Space is not the toggle");
  check(s.key(29,true,true,true,0)==0,"Ctrl+Alt+letter is not the toggle");
  check(s.key(62,true,true,true,0)==2,"first chord toggles");
  check(s.key(62,true,true,true,1)==1,"repeat is consumed without toggling");
  check(s.key(62,true,true,true,0)==1,"duplicate down cannot toggle twice");
  check(s.key(62,false,false,false,0)==1,"Space release consumed even if modifiers released first");
  check(s.key(62,true,true,true,0)==2,"next distinct press toggles back");
  s.reset();
  check(s.key(62,true,true,true,3)==1,"focus regain during held chord must not toggle");
  check(s.key(62,false,true,true,0)==1,"repeat-only chord still consumes release");
  check(s.key(62,true,true,true,0)==2,"fresh press after reset works");
  System.out.println("Desktop shortcut one toggle per press / modifier order / focus reset passed");
 }
 static void check(boolean condition,String reason){if(!condition)throw new AssertionError(reason);}
}
