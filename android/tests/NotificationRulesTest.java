// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
public final class NotificationRulesTest {
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] a){
  check(NotificationRules.quiet(23*60,22*60,7*60));check(NotificationRules.quiet(6*60,22*60,7*60));check(!NotificationRules.quiet(12*60,22*60,7*60));check(!NotificationRules.quiet(0,0,0));check(!NotificationRules.quiet(7*60,22*60,7*60));
  check(NotificationRules.deliver(true,true,false,"active",false));check(!NotificationRules.deliver(true,true,true,"active",false));check(!NotificationRules.deliver(true,false,false,"resolved",true));check(!NotificationRules.deliver(true,true,false,"resolved",false));check(NotificationRules.deliver(true,true,false,"resolved",true));check(!NotificationRules.deliver(false,true,false,"active",false));
  System.out.println("Notification quiet hours, recovery opt-out and config-removal suppression passed");
 }
}
