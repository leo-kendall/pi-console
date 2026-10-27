// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
public final class DesktopClipboardTest {
 public static void main(String[] args){
  check(DesktopInput.checkedClipboard("explicit 📋").equals("explicit 📋"),"plain unicode clipboard");
  StringBuilder limit=new StringBuilder();for(int i=0;i<4096;i++)limit.append("🚀");
  check(DesktopInput.checkedClipboard(limit.toString()).length()==8192,"exact UTF-8 limit");
  boolean rejected=false;try{DesktopInput.checkedClipboard(limit.append("x").toString());}catch(IllegalArgumentException e){rejected=true;}check(rejected,"UTF-8 bytes bounded, not UTF-16 chars");
  rejected=false;try{DesktopInput.checkedClipboard(null);}catch(IllegalArgumentException e){rejected=true;}check(rejected,"null refused");
  System.out.println("Desktop native clipboard UTF-8 boundary tests passed");
 }
 static void check(boolean value,String reason){if(!value)throw new AssertionError(reason);}
}
