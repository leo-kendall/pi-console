// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.*;import android.content.*;import android.content.pm.*;import android.net.Uri;import android.os.Build;import org.json.*;import java.io.*;import java.security.MessageDigest;import java.util.*;
/** Official release metadata only. The bridge never supplies a download URL or hash. */
final class UpdateManager {
 static final String FEED="https://api.github.com/repos/leo-kendall/pi-console/releases?per_page=20";
 static android.content.SharedPreferences prefs(Context c){return c.getSharedPreferences("updates",0);}
 static String current(Context c)throws Exception{return c.getPackageManager().getPackageInfo(c.getPackageName(),0).versionName;}
 static JSONObject check(Context c,boolean prerelease)throws Exception{
  ByteArrayOutputStream bytes=new ByteArrayOutputStream();new UpdateTransport().copy(FEED,bytes,1048576);
  JSONArray releases=new JSONArray(new String(bytes.toByteArray(),"UTF-8"));JSONObject best=null;String current=current(c);
  for(int i=0;i<releases.length();i++){JSONObject r=releases.getJSONObject(i);if(r.optBoolean("draft")||r.optBoolean("prerelease")&&!prerelease)continue;String version=r.optString("tag_name");if(!UpdateRules.newer(version,current))continue;if(best==null||UpdateRules.newer(version,best.optString("tag_name")))best=r;}
  JSONObject out=new JSONObject().put("current",current).put("available",best!=null).put("channel",prerelease?"prerelease":"stable").put("source",FEED);
  if(best!=null){String tag=best.getString("tag_name");out.put("version",tag).put("notes",best.optString("body","")).put("downloadable",false);
   JSONArray assets=best.getJSONArray("assets");for(int i=0;i<assets.length();i++){JSONObject a=assets.getJSONObject(i);String name=a.optString("name");if(!UpdateRules.apkName(name))continue;
    try{String url=a.getString("browser_download_url");UpdateRules.url(url);if(!url.startsWith("https://github.com/leo-kendall/pi-console/releases/download/"))throw new IOException("资源不属于官方发布");String digest=UpdateRules.digest(a.optString("digest",null));long size=a.getLong("size");if(size<=0||size>UpdateRules.MAX_APK)throw new IOException("APK 大小无效");out.put("url",url).put("sha256",digest).put("bytes",size).put("downloadable",true);}catch(Exception invalid){out.put("blocked",invalid.getMessage());}break;
   }
   if(!out.getBoolean("downloadable")&&!out.has("blocked"))out.put("blocked","此发布尚未提供可验证的 Android APK");
  }
  if(!prefs(c).edit().putString("candidate",out.toString()).putLong("checked_at",System.currentTimeMillis()).commit())throw new IOException("保存更新信息失败");
  // Public metadata only; no profile, token or pairing preferences are read or modified.
  return out;
 }
 static JSONObject state(Context c)throws Exception{
  JSONObject out=new JSONObject().put("current",current(c)).put("state",prefs(c).getString("state","idle")).put("message",prefs(c).getString("message",""));
  if(out.getString("state").equals("downloading")&&!UpdateService.running.get())out.put("state","interrupted").put("message","上次下载已中断，请重新下载");return out;
 }
 static void download(Context c,String tag)throws Exception{
  JSONObject selected=new JSONObject(prefs(c).getString("candidate","{}"));
  if(!selected.optBoolean("downloadable")||!tag.equals(selected.optString("version"))||System.currentTimeMillis()-prefs(c).getLong("checked_at",0)>86400000)throw new IOException("请先重新检查官方更新");
  if(UpdateService.running.get())throw new IOException("已有更新下载进行中");
  c.startForegroundService(new Intent(c,UpdateService.class).putExtra("candidate",selected.toString()));
 }
 static File apk(Context c){return new File(c.getFilesDir(),"verified-update.apk");}
 static String[] certs(Signature[] signatures)throws Exception{if(signatures==null)return new String[0];List<String> out=new ArrayList<>();for(Signature s:signatures){byte[] hash=MessageDigest.getInstance("SHA-256").digest(s.toByteArray());StringBuilder b=new StringBuilder();for(byte v:hash)b.append(String.format(Locale.ROOT,"%02x",v&255));out.add(b.toString());}return out.toArray(new String[0]);}
 static void validate(Context c,File file,JSONObject expected)throws Exception{
  if(file.length()!=expected.getLong("bytes"))throw new IOException("更新文件大小不符");MessageDigest md=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] b=new byte[32768];int n;while((n=in.read(b))!=-1)md.update(b,0,n);}StringBuilder hash=new StringBuilder();for(byte b:md.digest())hash.append(String.format(Locale.ROOT,"%02x",b&255));if(!hash.toString().equals(expected.getString("sha256")))throw new IOException("更新 SHA256 校验失败");
  PackageManager pm=c.getPackageManager();int flags=Build.VERSION.SDK_INT>=28?PackageManager.GET_SIGNING_CERTIFICATES:PackageManager.GET_SIGNATURES;
  PackageInfo candidate=pm.getPackageArchiveInfo(file.getAbsolutePath(),flags),installed=pm.getPackageInfo(c.getPackageName(),flags);
  if(candidate==null||!c.getPackageName().equals(candidate.packageName))throw new IOException("更新 APK 包名不匹配");
  long candidateCode=Build.VERSION.SDK_INT>=28?candidate.getLongVersionCode():candidate.versionCode,installedCode=Build.VERSION.SDK_INT>=28?installed.getLongVersionCode():installed.versionCode;
  if(candidateCode<=installedCode)throw new IOException("更新版本号必须高于当前版本");
  if(candidate.applicationInfo==null||candidate.applicationInfo.minSdkVersion>Build.VERSION.SDK_INT)throw new IOException("更新不支持此 Android 版本");
  boolean trusted;
  if(Build.VERSION.SDK_INT>=28){if(candidate.signingInfo==null||installed.signingInfo==null)throw new IOException("更新签名缺失");trusted=UpdateRules.signers(certs(installed.signingInfo.getApkContentsSigners()),certs(candidate.signingInfo.getApkContentsSigners()),certs(candidate.signingInfo.hasMultipleSigners()?null:candidate.signingInfo.getSigningCertificateHistory()));}
  else trusted=UpdateRules.signers(certs(installed.signatures),certs(candidate.signatures),new String[0]);
  if(!trusted)throw new IOException("更新签名与当前安装不兼容；请保留原签名或有效签名轮换证明");
 }
 static void install(Activity c)throws Exception{
  if(!prefs(c).getString("state","").equals("ready")||UpdateService.running.get())throw new IOException("请先完成更新下载与校验");
  JSONObject selected=new JSONObject(prefs(c).getString("verified","{}"));validate(c,apk(c),selected);
  if(Build.VERSION.SDK_INT>=26&&!c.getPackageManager().canRequestPackageInstalls()){c.startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+c.getPackageName())));throw new IOException("请允许此 App 安装更新，然后再次点击安装");}
  Uri uri=Uri.parse("content://"+c.getPackageName()+".updates/apk");Intent intent=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);c.startActivity(intent);
 }
}
