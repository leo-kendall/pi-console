// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;import java.io.*;import java.net.*;import java.security.cert.Certificate;import javax.net.ssl.*;
/** Real production HTTP writer, with only the socket/TLS boundary replaced. */
public final class ProfileTransportTest {
 static Fake next;static URL captured;static int opens;
 static final class Fake extends HttpsURLConnection {
  int code=200;byte[] data="{}".getBytes(java.nio.charset.StandardCharsets.UTF_8);boolean closed;
  Fake()throws Exception{super(new URL("https://fixture.test"));}
  public int getResponseCode(){return code;}public InputStream getInputStream(){return new ByteArrayInputStream(data);}
  public void disconnect(){closed=true;}public void connect(){}public boolean usingProxy(){return false;}
  public String getCipherSuite(){return "fixture";}public Certificate[] getLocalCertificates(){return null;}public Certificate[] getServerCertificates(){return null;}
 }
 static void check(boolean value){if(!value)throw new AssertionError("profile transport boundary");}
 public static void main(String[] args)throws Exception{
  URL.setURLStreamHandlerFactory(protocol->protocol.equals("https")?new URLStreamHandler(){protected URLConnection openConnection(URL url){captured=url;opens++;return next;}}:null);
  Context c=new Context();String a=ServerSettings.add(c,"A","https://a.test/prefix"),b=ServerSettings.add(c,"B","https://b.test");ServerSettings.pair(c,ServerSettings.snapshot(c),"A-token");
  ServerSettings.Snapshot old=ServerSettings.snapshot(c);ServerSettings.activate(c,b);ServerSettings.pair(c,ServerSettings.snapshot(c),"B-token");
  next=new Fake();check(StatusClient.request(old,"GET","/api/status","").equals("{}"));
  check(captured.toString().equals("https://a.test/prefix/api/status"));check(next.getRequestProperty("Authorization").equals("Bearer A-token"));check(next.closed&&!next.getInstanceFollowRedirects());
  next=new Fake();StatusClient.request(ServerSettings.snapshot(c),"GET","/api/status","");
  check(captured.toString().equals("https://b.test/api/status"));check(next.getRequestProperty("Authorization").equals("Bearer B-token"));
  next=new Fake();next.code=302;int before=opens;try{StatusClient.request(old,"GET","/api/status","");throw new AssertionError("redirect accepted");}catch(ProbeRules.HttpFailure expected){}check(opens==before+1&&next.closed);
  next=new Fake();next.data=new byte[1048577];try{StatusClient.request(old,"GET","/api/status","");throw new AssertionError("oversize accepted");}catch(Exception expected){}check(next.closed);
  System.out.println("Profiles real HTTP boundary: captured endpoint/token, post-switch routing, redirects and bounded cleanup passed");
 }
}
