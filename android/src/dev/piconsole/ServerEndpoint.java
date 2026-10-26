// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.net.URI;
import java.util.Locale;
final class ServerEndpoint {
 final String host,canonical,prefix;final int port;
 private ServerEndpoint(String h,int p,String base,String path){host=h;port=p;canonical=base;prefix=path;}
 static ServerEndpoint parse(String raw){
  try{
   if(raw==null||raw.length()>2048||!raw.equals(raw.trim()))throw new Exception();
   URI u=new URI(raw);String host=u.getHost(),path=u.getRawPath();int port=u.getPort();
   if(!"https".equalsIgnoreCase(u.getScheme())||host==null||host.isEmpty()||u.getRawUserInfo()!=null||u.getRawQuery()!=null||u.getRawFragment()!=null||port==0||port>65535||port< -1)throw new Exception();
   if(path==null)path="";if(!path.matches("(?:/[A-Za-z0-9_-]+)*/?"))throw new Exception();
   if(path.endsWith("/"))path=path.substring(0,path.length()-1);
   host=host.toLowerCase(Locale.ROOT);String base="https://"+host+(port==-1||port==443?"":":"+port)+path;
   return new ServerEndpoint(host,port==-1?443:port,base,path);
  }catch(Exception e){throw new IllegalArgumentException("请输入有效的 HTTPS 地址，不含账号、参数、片段或转义路径");}
 }
 String path(String api){
  if(api==null||!api.matches("/api/[a-zA-Z0-9/?=&-]{1,160}")||api.contains("//")||api.contains(".."))throw new IllegalArgumentException("无效 API 路径");
  return prefix+api;
 }
}
