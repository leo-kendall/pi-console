// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.net.*;
import java.util.*;
/** Pure policy shared by the downloader and Android installer boundary. */
final class UpdateRules {
 static final long MAX_APK=134217728;
 static boolean apkName(String name){return name!=null&&name.matches("pi-console(?:-release|-[0-9]+\\.[0-9]+\\.[0-9]+(?:-[0-9A-Za-z.-]+)?)?\\.apk");}
 static URL url(String raw)throws Exception {
  URI u=new URI(raw);String h=u.getHost();
  if(raw.length()>4096||!"https".equals(u.getScheme())||u.getRawUserInfo()!=null||u.getFragment()!=null||(u.getPort()!=-1&&u.getPort()!=443)||h==null||!Arrays.asList("api.github.com","github.com","release-assets.githubusercontent.com","objects.githubusercontent.com").contains(h.toLowerCase(Locale.ROOT)))throw new IllegalArgumentException("更新地址必须为官方 GitHub HTTPS 资源");
  return u.toURL();
 }
 static String digest(String digest){if(digest==null||!digest.matches("sha256:[a-fA-F0-9]{64}"))throw new IllegalArgumentException("发布资源缺少 SHA256，暂不能安全下载");return digest.substring(7).toLowerCase(Locale.ROOT);}
 static boolean newer(String next,String current){try{return compare(next,current)>0;}catch(Exception invalid){return false;}}
 private static String[] version(String value){if(value==null||value.length()>100||!value.matches("v?[0-9]+\\.[0-9]+\\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\\+[0-9A-Za-z.-]+)?"))throw new IllegalArgumentException();return value.replaceFirst("^v","").split("\\+",2)[0].split("-",2);}
 private static int compare(String a,String b){String[] x=version(a),y=version(b);String[] xa=x[0].split("\\."),ya=y[0].split("\\.");for(int i=0;i<3;i++){int c=new java.math.BigInteger(xa[i]).compareTo(new java.math.BigInteger(ya[i]));if(c!=0)return c;}if(x.length==1||y.length==1)return Integer.compare(y.length,x.length);xa=x[1].split("\\.");ya=y[1].split("\\.");for(int i=0;i<Math.min(xa.length,ya.length);i++){boolean xn=xa[i].matches("[0-9]+"),yn=ya[i].matches("[0-9]+");int c=xn&&yn?new java.math.BigInteger(xa[i]).compareTo(new java.math.BigInteger(ya[i])):xn!=yn?(xn?-1:1):xa[i].compareTo(ya[i]);if(c!=0)return c;}return Integer.compare(xa.length,ya.length);}
 static boolean signers(String[] installed,String[] candidate,String[] history){
  if(installed.length==0||candidate.length==0)return false;
  if(installed.length>1||candidate.length>1)return new HashSet<>(Arrays.asList(installed)).equals(new HashSet<>(Arrays.asList(candidate)));
  return installed[0].equals(candidate[0])||Arrays.asList(history).contains(installed[0]);
 }
}
