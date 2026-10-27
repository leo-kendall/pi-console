// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.io.*;import java.net.*;import java.security.*;import javax.net.ssl.HttpsURLConnection;
/** No cookies, server tokens or automatic redirects. All hops pass the same policy. */
final class UpdateTransport {
 interface Opener {HttpsURLConnection open(URL u)throws Exception;}
 private final Opener opener;
 UpdateTransport(){this(u->(HttpsURLConnection)u.openConnection());}
 UpdateTransport(Opener o){opener=o;}
 String copy(String raw,OutputStream out,long limit)throws Exception {
  URL url=UpdateRules.url(raw);long deadline=System.nanoTime()+120000000000L;
  for(int hop=0;hop<6;hop++){
   final HttpsURLConnection c=opener.open(url);c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(15000);c.setUseCaches(false);c.setRequestProperty("Accept",url.getHost().equals("api.github.com")?"application/vnd.github+json":"application/octet-stream");c.setRequestProperty("Accept-Encoding","identity");
   try{
    int code=c.getResponseCode();
    if(code==301||code==302||code==303||code==307||code==308){String target=c.getHeaderField("Location");if(target==null)throw new IOException("更新重定向缺少目标");url=UpdateRules.url(new URL(url,target).toString());continue;}
    if(code!=200)throw new IOException("更新服务器 HTTP "+code);
    if(c.getContentLengthLong()>limit)throw new IOException("更新文件过大");
    MessageDigest digest=MessageDigest.getInstance("SHA-256");long total=0;
    try(InputStream in=c.getInputStream()){byte[] b=new byte[32768];int n;while((n=in.read(b))!=-1){total+=n;if(total>limit||System.nanoTime()>deadline||Thread.currentThread().isInterrupted())throw new IOException("更新下载超过大小或时间限制");out.write(b,0,n);digest.update(b,0,n);}}
    StringBuilder hex=new StringBuilder();for(byte b:digest.digest())hex.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return hex.toString();
   }finally{c.disconnect();}
  }
  throw new IOException("更新重定向次数过多");
 }
}
