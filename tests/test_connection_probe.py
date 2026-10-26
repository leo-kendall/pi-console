# SPDX-License-Identifier: Apache-2.0
"""Exercise native HTTP behavior without an Android device or external network."""
import os,shutil,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JSON_STUB='''package org.json; public final class JSONObject {
 private final java.util.Map<String,Object> values=new java.util.HashMap<>();
 public JSONObject put(String key,Object value){values.put(key,value);return this;}
 public Object get(String key){return values.get(key);}
}'''
TRANSPORT_TEST=r'''
package dev.piconsole;
import java.net.*;import java.io.*;import java.security.Principal;import java.security.cert.Certificate;
import javax.net.ssl.*;import org.json.JSONObject;
public class ProbeTransportTest {
 static Fake next;static int opens;static URL captured;
 static final class Fake extends HttpsURLConnection {
  int status=200;String mime="application/json";byte[] bytes="{\"app\":\"pi-console\",\"protocol\":1}".getBytes(java.nio.charset.StandardCharsets.UTF_8);
  int length=-1,reads;boolean closed;IOException failure;
  Fake()throws Exception{super(new URL("https://fixture.example.test"));}
  public int getResponseCode()throws IOException{if(failure!=null)throw failure;return status;}
  public InputStream getInputStream(){reads++;return new ByteArrayInputStream(bytes);}
  public long getContentLengthLong(){return length;}
  public String getContentType(){return mime;}
  public void disconnect(){closed=true;}
  public void connect(){}public boolean usingProxy(){return false;}
  public String getCipherSuite(){return "fixture";}public Certificate[] getLocalCertificates(){return null;}public Certificate[] getServerCertificates(){return null;}
  public Principal getPeerPrincipal(){return null;}public Principal getLocalPrincipal(){return null;}
 }
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 static JSONObject run()throws Exception{return ConnectionProbe.run("https://draft.example.test:8443/pi-console/");}
 public static void main(String[] args)throws Exception{
  URL.setURLStreamHandlerFactory(protocol->protocol.equals("https")?new URLStreamHandler(){protected URLConnection openConnection(URL url){opens++;captured=url;return next;}}:null);
  next=new Fake();JSONObject data=run();
  check(Boolean.TRUE.equals(data.get("ok")),"compatible identity succeeds");
  check(captured.toString().equals("https://draft.example.test:8443/pi-console/api/connection"),"request uses draft and correct prefix");
  check(next.getRequestProperty("Authorization")==null,"probe must never carry a saved token");
  check(!next.getInstanceFollowRedirects(),"redirects disabled");check(next.closed,"connection cleaned up");
  next=new Fake();next.status=302;data=run();check(data.get("code").equals("redirect")&&next.reads==0,"redirect does not fetch response or another URL");
  next=new Fake();next.status=401;data=run();check(data.get("code").equals("denied")&&next.reads==0,"proxy login is not reported as pairing success");
  next=new Fake();next.bytes=new byte[8193];data=run();check(data.get("code").equals("response"),"streaming response bounded");
  next=new Fake();next.length=8193;data=run();check(data.get("code").equals("response")&&next.reads==0,"large content length rejected before read");
  next=new Fake();next.failure=new SSLHandshakeException("secret-subject");data=run();
  check(data.get("code").equals("tls"),"TLS error actionable");check(!data.get("detail").toString().contains("secret-subject"),"provider secrets not echoed");
  next=new Fake();next.bytes=new byte[]{(byte)0xff};data=run();check(data.get("code").equals("response"),"malformed UTF8 not accepted");
  int previous=opens;data=ConnectionProbe.run("http://bad.example.test");check(data.get("code").equals("address")&&opens==previous,"invalid draft does not connect");
  System.out.println("Native HTTPS probe: draft routing, credential absence, redirects, bounds, TLS, UTF8 and cleanup passed");
 }
}
'''


class ConnectionProbeTests(unittest.TestCase):
 def test_native_probe_transport(self):
  java_home=Path(os.environ.get('JAVA_HOME','/nonexistent'))/'bin'
  javac=str(java_home/'javac') if (java_home/'javac').exists() else shutil.which('javac')
  java=str(java_home/'java') if (java_home/'java').exists() else shutil.which('java')
  if not javac or not java:self.skipTest('JDK required for native transport regression')
  with tempfile.TemporaryDirectory(prefix='pi-console-probe-test-') as temp:
   root=Path(temp);stub=root/'org/json/JSONObject.java';stub.parent.mkdir(parents=True);stub.write_text(JSON_STUB)
   test=root/'ProbeTransportTest.java';test.write_text(TRANSPORT_TEST)
   source=ROOT/'android/src/dev/piconsole'
   subprocess.run([javac,'--release','8','-d',temp,str(stub),str(test),*[str(source/(n+'.java')) for n in ('ServerEndpoint','ProbeRules','ConnectionProbe')]],check=True,capture_output=True)
   result=subprocess.run([java,'-cp',temp,'dev.piconsole.ProbeTransportTest'],check=True,capture_output=True,text=True,timeout=20)
   self.assertIn('credential absence',result.stdout)
