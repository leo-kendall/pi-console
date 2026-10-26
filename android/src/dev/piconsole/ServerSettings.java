// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
import java.util.UUID;
/** Request URL and credential are captured together; pairing is endpoint-bound. */
final class ServerSettings {
 static final class Snapshot {
  final ServerEndpoint endpoint;final String token,generation;
  Snapshot(ServerEndpoint e,String t,String g){endpoint=e;token=t;generation=g;}
 }
 static synchronized String url(Context c){return c.getSharedPreferences("server",0).getString("url","");}
 static synchronized Snapshot snapshot(Context c)throws Exception {
  android.content.SharedPreferences prefs=c.getSharedPreferences("server",0);
  ServerEndpoint endpoint=ServerEndpoint.parse(prefs.getString("url",""));String token=SecretStore.read(c);
  if(!endpoint.canonical.equals(c.getSharedPreferences("paired",0).getString("server","")))token="";
  return new Snapshot(endpoint,token,prefs.getString("generation",""));
 }
 static synchronized boolean paired(Context c)throws Exception {return !url(c).isEmpty()&&!snapshot(c).token.isEmpty();}
 static synchronized void set(Context c,String raw)throws Exception {
  ServerEndpoint endpoint=ServerEndpoint.parse(raw);
  if(!SecretStore.read(c).isEmpty())throw new Exception("请先撤销当前配对，再修改服务器地址");
  if(!c.getSharedPreferences("server",0).edit().putString("url",endpoint.canonical).putString("generation",UUID.randomUUID().toString()).commit())throw new Exception("保存服务器地址失败");
 }
 static synchronized void pair(Context c,Snapshot request,String token)throws Exception {
  android.content.SharedPreferences prefs=c.getSharedPreferences("server",0);
  if(!request.endpoint.canonical.equals(url(c))||!request.generation.equals(prefs.getString("generation","")))throw new Exception("服务器已更改，请重新配对");
  SecretStore.save(c,token);
  if(!c.getSharedPreferences("paired",0).edit().putString("server",request.endpoint.canonical).commit()){SecretStore.clear(c);throw new Exception("保存配对绑定失败");}
 }
 static synchronized void forget(Context c)throws Exception {
  if(!c.getSharedPreferences("server",0).edit().putString("generation",UUID.randomUUID().toString()).commit())throw new Exception("无法取消正在进行的配对，请重试");
  SecretStore.clear(c);
 }
}
