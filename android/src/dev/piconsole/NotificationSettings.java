// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;import org.json.*;import java.util.Calendar;
final class NotificationSettings {
 static JSONObject access(Context c,String raw)throws Exception{
  android.content.SharedPreferences p=c.getSharedPreferences("notification_settings",0);
  if(!raw.isEmpty()){JSONObject v=new JSONObject(raw);if(v.getInt("schema")!=1||!(v.get("enabled") instanceof Boolean)||!(v.get("recovery") instanceof Boolean))throw new Exception("通知设置格式无效");NotificationRules.minute(v.getString("quiet_start"));NotificationRules.minute(v.getString("quiet_end"));if(!p.edit().putString("settings",v.toString()).commit())throw new Exception("通知设置保存失败");}
  return new JSONObject(p.getString("settings","{\"schema\":1,\"enabled\":true,\"recovery\":true,\"quiet_start\":\"00:00\",\"quiet_end\":\"00:00\"}"));
 }
 static boolean quiet(JSONObject prefs)throws Exception{Calendar now=Calendar.getInstance();return NotificationRules.quiet(now.get(Calendar.HOUR_OF_DAY)*60+now.get(Calendar.MINUTE),NotificationRules.minute(prefs.getString("quiet_start")),NotificationRules.minute(prefs.getString("quiet_end")));}
 static boolean deliver(Context c,String state,boolean recovered)throws Exception{JSONObject p=access(c,"");return NotificationRules.deliver(p.getBoolean("enabled"),p.getBoolean("recovery"),quiet(p),state,recovered);}
}
