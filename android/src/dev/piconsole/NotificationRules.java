// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
final class NotificationRules {
 static int minute(String s){if(!s.matches("(?:[01][0-9]|2[0-3]):[0-5][0-9]"))throw new IllegalArgumentException("时间必须为 HH:MM");return Integer.parseInt(s.substring(0,2))*60+Integer.parseInt(s.substring(3));}
 static boolean quiet(int now,int start,int end){return start!=end&&(start<end?now>=start&&now<end:now>=start||now<end);}
 static boolean deliver(boolean enabled,boolean recovery,boolean quiet,String state,boolean recovered){return enabled&&!quiet&&("active".equals(state)||"resolved".equals(state)&&recovered&&recovery);}
}
