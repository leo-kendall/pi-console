// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
import android.content.SharedPreferences;
import java.util.*;
/** A credential and endpoint always travel together. No operation retargets a snapshot. */
final class ServerSettings {
 static final class Snapshot {
  final ServerEndpoint endpoint; final String token,generation,profile;
  Snapshot(ServerEndpoint e,String t,String g){this(e,t,g,"");}
  Snapshot(ServerEndpoint e,String t,String g,String p){endpoint=e;token=t;generation=g;profile=p;}
 }
 static final class Profile {
  final String id,name,url;
  Profile(String i,String n,String u){id=i;name=n;url=u;}
 }
 private static SharedPreferences prefs(Context c){return c.getSharedPreferences("server_profiles",0);}
 private static void save(SharedPreferences.Editor e)throws Exception{if(!e.commit())throw new Exception("保存服务器配置失败");}
 private static String next(){return UUID.randomUUID().toString();}
 private static void migrate(Context c)throws Exception {
  SharedPreferences p=prefs(c);if(p.getString("migrated","").equals("1"))return;
  String old=c.getSharedPreferences("server",0).getString("url","");
  SharedPreferences.Editor e=p.edit().putString("migrated","1").putString("generation",next());
  if(!old.isEmpty()){
   String id="legacy";ServerEndpoint endpoint=ServerEndpoint.parse(old);
   // Copy ciphertext under the original Keystore alias, before publishing the profile.
   SecretStore.migrate(c,id);
   String apps=c.getSharedPreferences("app_entries",0).getString("items",null);
   if(apps!=null)save(c.getSharedPreferences("app_entries-"+id,0).edit().putString("items",apps));
   e.putString("ids",id).putString("active",id).putString(id+".name","原服务器").putString(id+".url",endpoint.canonical);
  }
  save(e);
  // Legacy ciphertext is removed only after durable migration. Never delete the key.
  save(c.getSharedPreferences("paired",0).edit().clear());
 }
 static synchronized String activeId(Context c)throws Exception{migrate(c);return prefs(c).getString("active","");}
 static synchronized List<Profile> profiles(Context c)throws Exception{
  migrate(c);List<Profile> out=new ArrayList<>();SharedPreferences p=prefs(c);
  for(String id:p.getString("ids","").split(","))if(!id.isEmpty())out.add(new Profile(id,p.getString(id+".name","服务器"),p.getString(id+".url","")));
  return out;
 }
 private static Profile find(Context c,String id)throws Exception{for(Profile p:profiles(c))if(p.id.equals(id))return p;throw new Exception("服务器配置不存在");}
 static synchronized String url(Context c){try{String id=activeId(c);return id.isEmpty()?"":find(c,id).url;}catch(Exception e){throw new IllegalStateException(e);}}
 static synchronized Snapshot snapshot(Context c)throws Exception{return snapshot(c,activeId(c));}
 static synchronized Snapshot snapshot(Context c,String id)throws Exception{
  Profile p=find(c,id);String token=SecretStore.read(c,id);
  if(!p.url.equals(c.getSharedPreferences("paired-"+id,0).getString("server","")))token="";
  return new Snapshot(ServerEndpoint.parse(p.url),token,prefs(c).getString("generation",""),id);
 }
 static synchronized boolean current(Context c,Snapshot s)throws Exception{return s.profile.equals(activeId(c))&&s.generation.equals(prefs(c).getString("generation",""))&&s.endpoint.canonical.equals(url(c));}
 static synchronized boolean paired(Context c)throws Exception{return !url(c).isEmpty()&&!snapshot(c).token.isEmpty();}
 private static String name(String value)throws Exception{String n=value.trim();if(n.isEmpty()||n.length()>64||n.matches("(?s).*[\\p{Cntrl}].*"))throw new Exception("名称必须为 1–64 个字符");return n;}
 static synchronized String add(Context c,String label,String raw)throws Exception{
  List<Profile> all=profiles(c);String n=name(label),url=ServerEndpoint.parse(raw).canonical;
  if(all.size()>=32)throw new Exception("最多保存 32 台服务器");for(Profile p:all)if(p.url.equals(url))throw new Exception("此服务器地址已保存");
  String id=next(),ids=prefs(c).getString("ids","");SharedPreferences.Editor e=prefs(c).edit().putString("ids",ids.isEmpty()?id:ids+","+id).putString(id+".name",n).putString(id+".url",url);
  if(all.isEmpty())e.putString("active",id).putString("generation",next());save(e);return id;
 }
 static synchronized void rename(Context c,String id,String label)throws Exception{find(c,id);save(prefs(c).edit().putString(id+".name",name(label)));}
 static synchronized void activate(Context c,String id)throws Exception{find(c,id);save(prefs(c).edit().putString("active",id).putString("generation",next()));}
 static synchronized void remove(Context c,String id)throws Exception{
  find(c,id);List<String> ids=new ArrayList<>();for(Profile p:profiles(c))if(!p.id.equals(id))ids.add(p.id);
  SharedPreferences.Editor e=prefs(c).edit().putString("ids",String.join(",",ids)).putString(id+".url","").putString(id+".name","");
  if(activeId(c).equals(id))e.putString("active",ids.isEmpty()?"":ids.get(0)).putString("generation",next());save(e);
  SecretStore.clear(c,id);if(id.equals("legacy")){save(c.getSharedPreferences("server",0).edit().clear());save(c.getSharedPreferences("app_entries",0).edit().clear());}
  save(c.getSharedPreferences("app_entries-"+id,0).edit().clear());save(c.getSharedPreferences("profile_ui-"+id,0).edit().clear());
 }
 static synchronized void set(Context c,String raw)throws Exception{
  ServerEndpoint endpoint=ServerEndpoint.parse(raw);String id=activeId(c);
  if(id.isEmpty()){add(c,"服务器",raw);return;}
  if(!snapshot(c).token.isEmpty())throw new Exception("请添加另一个服务器配置，或先撤销当前配对");
  for(Profile p:profiles(c))if(!p.id.equals(id)&&p.url.equals(endpoint.canonical))throw new Exception("此服务器地址已保存");
  save(prefs(c).edit().putString(id+".url",endpoint.canonical).putString("generation",next()));
 }
 static synchronized void pair(Context c,Snapshot request,String token)throws Exception{
  if(!current(c,request))throw new Exception("服务器已更改，请重新配对");
  if(token==null||token.isEmpty()||token.length()>8192||token.contains("\n")||token.contains("\r"))throw new Exception("无效配对凭证");
  SecretStore.save(c,request.profile,token);
  if(!c.getSharedPreferences("paired-"+request.profile,0).edit().putString("server",request.endpoint.canonical).commit()){SecretStore.clear(c,request.profile);throw new Exception("保存配对绑定失败");}
 }
 static synchronized void forget(Context c,Snapshot request)throws Exception{if(!current(c,request))throw new IllegalStateException("服务器已切换，原配对结果已忽略");forget(c);}
 static synchronized void forget(Context c)throws Exception{String id=activeId(c);save(prefs(c).edit().putString("generation",next()));if(!id.isEmpty())SecretStore.clear(c,id);}
}
