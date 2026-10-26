// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.util.Timer;
import java.util.TimerTask;
import javax.net.ssl.HttpsURLConnection;
final class StatusClient {
 static String request(Context context,String method,String path,String body)throws Exception {
  return request(ServerSettings.snapshot(context),method,path,body);
 }
 static String request(ServerSettings.Snapshot session,String method,String path,String body)throws Exception {
  if(!method.equals("GET")&&!method.equals("POST"))throw new IllegalArgumentException("无效方法");
  session.endpoint.path(path);
  HttpsURLConnection c=(HttpsURLConnection)new URL(session.endpoint.canonical+path).openConnection();
  c.setInstanceFollowRedirects(false);c.setConnectTimeout(35000);c.setReadTimeout(35000);
  c.setRequestMethod(method);c.setRequestProperty("Accept","application/json");c.setRequestProperty("Content-Type","application/json");
  if(!session.token.isEmpty())c.setRequestProperty("Authorization","Bearer "+session.token);
  Timer deadline=new Timer("pi-console-request-deadline",true);deadline.schedule(new TimerTask(){public void run(){c.disconnect();}},35000);
  try {
   if(method.equals("POST")){byte[] bytes=body.getBytes(StandardCharsets.UTF_8);if(bytes.length>262144)throw new Exception("请求过大");c.setDoOutput(true);c.setFixedLengthStreamingMode(bytes.length);try(java.io.OutputStream out=c.getOutputStream()){out.write(bytes);}}
   int code=c.getResponseCode();
   if(code!=200){
    if(code==401)throw new Exception("请先配对当前服务器");
    if(code==429)throw new Exception("操作过快，请稍后重试");
    if(code>=300&&code<400)throw new Exception("服务器返回重定向，请填写最终 HTTPS 地址");
    throw new Exception("请求失败（"+code+"），请检查服务器状态");
   }
   try(InputStream input=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
    byte[] buf=new byte[8192];int n;while((n=input.read(buf))!=-1){if(out.size()+n>1048576)throw new Exception("响应过大");out.write(buf,0,n);}
    return StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(out.toByteArray())).toString();
   }
  }finally{deadline.cancel();c.disconnect();}
 }
}
