// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
import org.json.*;
final class ProfileBridge {
 static JSONObject list(Context c)throws Exception{
  JSONArray a=new JSONArray();String active=ServerSettings.activeId(c);
  for(ServerSettings.Profile p:ServerSettings.profiles(c)){boolean paired=false,damaged=false;try{paired=!ServerSettings.snapshot(c,p.id).token.isEmpty();}catch(Exception invalid){damaged=true;}a.put(new JSONObject().put("id",p.id).put("name",p.name).put("url",p.url).put("paired",paired).put("credential_error",damaged).put("active",active.equals(p.id)));}
  return new JSONObject().put("profiles",a).put("active",active);
 }
 static JSONObject settings(Context c,JSONObject value)throws Exception{
  String id=ServerSettings.activeId(c);android.content.SharedPreferences p=c.getSharedPreferences("profile_ui-"+id,0);
  if(value!=null){if(!id.equals(value.getString("profile")))throw new Exception("服务器已切换，设置未保存");BackupRules.ui(value.getString("theme"),value.getInt("frequency"));if(!p.edit().putString("settings",value.toString()).commit())throw new Exception("设置保存失败");}
  return new JSONObject(p.getString("settings","{}")).put("profile",id);
 }
 static JSONObject status(Context c,String id)throws Exception{
  // Explicit per-profile button only. Never enumerate saved endpoints in the background.
  ServerSettings.Snapshot s=ServerSettings.snapshot(c,id);JSONObject out=new JSONObject().put("id",id);
  try{new JSONObject(StatusClient.request(s,"GET","/api/status",""));out.put("online",true);}catch(Exception unavailable){out.put("online",false);}
  return out;
 }
}
