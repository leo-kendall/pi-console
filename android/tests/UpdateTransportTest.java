// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.io.*;import java.net.*;import java.util.*;import javax.net.ssl.*;import java.security.cert.Certificate;
public final class UpdateTransportTest {
 static class Reply extends HttpsURLConnection {
  final int code;final String location;final byte[] data;boolean disconnected;
  Reply(URL u,int c,String l,byte[] d){super(u);code=c;location=l;data=d;}
  public int getResponseCode(){return code;} public String getHeaderField(String n){return "Location".equals(n)?location:null;}public long getContentLengthLong(){return -1;}
  public InputStream getInputStream(){return new ByteArrayInputStream(data);}public void disconnect(){disconnected=true;}public void connect(){}public boolean usingProxy(){return false;}public String getCipherSuite(){return "fake";}public Certificate[] getLocalCertificates(){return null;}public Certificate[] getServerCertificates(){return null;}
 }
 interface Op{void run()throws Exception;}static void deny(Op op)throws Exception{try{op.run();}catch(Exception expected){return;}throw new AssertionError("unsafe transport accepted");}
 public static void main(String[] a)throws Exception{
  List<Reply> replies=new ArrayList<>();UpdateTransport t=new UpdateTransport(u->{Reply r=new Reply(u,replies.isEmpty()?302:200,"https://release-assets.githubusercontent.com/a",new byte[]{97,98,99});replies.add(r);return r;});
  ByteArrayOutputStream out=new ByteArrayOutputStream();String hash=t.copy("https://github.com/a",out,3);
  if(!hash.equals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")||!Arrays.equals(out.toByteArray(),new byte[]{97,98,99})||!replies.get(0).disconnected)throw new AssertionError();
  for(Reply r:replies)if(r.getRequestProperty("Authorization")!=null||r.getInstanceFollowRedirects())throw new AssertionError("credential or automatic redirect");
  deny(()->new UpdateTransport(u->new Reply(u,302,"http://github.com/evil",new byte[0])).copy("https://github.com/a",new ByteArrayOutputStream(),100));
  deny(()->new UpdateTransport(u->new Reply(u,302,"https://attacker.test/a",new byte[0])).copy("https://github.com/a",new ByteArrayOutputStream(),100));
  deny(()->new UpdateTransport(u->new Reply(u,302,"https://github.com/loop",new byte[0])).copy("https://github.com/a",new ByteArrayOutputStream(),100));
  deny(()->new UpdateTransport(u->new Reply(u,200,null,new byte[20])).copy("https://github.com/a",new ByteArrayOutputStream(),10));
  deny(()->new UpdateTransport(u->new Reply(u,404,null,new byte[0])).copy("https://github.com/a",new ByteArrayOutputStream(),10));
  System.out.println("Update transport: digest, bounded stream, HTTPS redirects, loop and token privacy fakes passed");
 }
}
