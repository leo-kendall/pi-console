// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.net.URL;
import java.io.*;
import java.nio.charset.*;
import java.util.*;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONObject;

/** A draft-address check; never reads ServerSettings or SecretStore. */
final class ConnectionProbe {
 static JSONObject run(String draft)throws Exception {
  long start=System.nanoTime();String code="address";int status=0;
  ServerEndpoint endpoint;
  try{endpoint=ServerEndpoint.parse(draft);}catch(IllegalArgumentException error){return result(code,status,start);}
  HttpsURLConnection connection=null;Timer deadline=new Timer("pi-console-probe",true);
  try{
   connection=(HttpsURLConnection)new URL(endpoint.canonical+"/api/connection").openConnection();
   final HttpsURLConnection request=connection;
   connection.setInstanceFollowRedirects(false);connection.setRequestMethod("GET");
   connection.setConnectTimeout(8000);connection.setReadTimeout(8000);connection.setUseCaches(false);
   connection.setRequestProperty("Accept","application/json");
   deadline.schedule(new TimerTask(){public void run(){request.disconnect();}},10000);
   status=connection.getResponseCode();code=ProbeRules.http(status);
   if(code.equals("inspect")){
    code="response";
    if(connection.getContentLengthLong()<=8192){
     try(InputStream input=connection.getInputStream();ByteArrayOutputStream output=new ByteArrayOutputStream()){
      byte[] buffer=new byte[1024];int count;
      while((count=input.read(buffer))!=-1){if(output.size()+count>8192)break;output.write(buffer,0,count);}
      if(count==-1){String body=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(output.toByteArray())).toString();code=ProbeRules.identity(connection.getContentType(),body);}
     }
    }
   }
  }catch(CharacterCodingException error){code="response";}
  catch(Exception error){code=ProbeRules.failure(error);if((System.nanoTime()-start)/1000000>=9900&&code.equals("network"))code="timeout";}
  finally{deadline.cancel();if(connection!=null)connection.disconnect();}
  return result(code,status,start);
 }
 private static JSONObject result(String code,int status,long start)throws Exception{
  return new JSONObject().put("ok",code.equals("ok")).put("code",code).put("title",ProbeRules.title(code)).put("detail",ProbeRules.detail(code)).put("http_status",status).put("elapsed_ms",Math.max(0,(System.nanoTime()-start)/1000000));
 }
}
