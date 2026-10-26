// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.net.*;
import javax.net.ssl.SSLException;
import java.util.Locale;
import java.util.regex.*;

/** The public handshake deliberately has exactly two fields, not arbitrary JSON. */
final class ProbeRules {
 private static final String W="[ \\t\\r\\n]*";
 private static final String APP="\"app\""+W+":"+W+"\"pi-console\"";
 private static final String PROTOCOL="\"protocol\""+W+":"+W+"(0|[1-9][0-9]{0,8})";
 private static final Pattern HANDSHAKE=Pattern.compile("\\A"+W+"\\{"+W+"(?:"+APP+W+","+W+PROTOCOL+"|"+PROTOCOL+W+","+W+APP+")"+W+"\\}"+W+"\\z");
 static String identity(String mime,String body){
  if(mime==null||!mime.split(";",2)[0].trim().toLowerCase(Locale.ROOT).equals("application/json")||body==null||body.length()>8192)return "response";
  Matcher match=HANDSHAKE.matcher(body);if(!match.matches())return "response";
  return "1".equals(match.group(1)==null?match.group(2):match.group(1))?"ok":"version";
 }
 static String http(int code){
  if(code==200)return "inspect";
  if(code>=300&&code<400)return "redirect";
  if(code==404)return "missing";
  if(code==401||code==403)return "denied";
  if(code==429)return "rate";
  if(code==502||code==503||code==504)return "upstream";
  return "http";
 }
 static String failure(Throwable error){
  for(int n=0;error!=null&&n<8;n++,error=error.getCause()){
   if(error instanceof SSLException)return "tls";
   if(error instanceof UnknownHostException)return "dns";
   if(error instanceof SocketTimeoutException)return "timeout";
   if(error instanceof ConnectException)return "connect";
  }
  return "network";
 }
 static String pairingError(int status){return status==401?"配对码无效或已过期，请在后端项目目录重新生成":status==429?"配对尝试过多，请等待一分钟再试":"配对失败，请检查服务器状态";}
 static final class HttpFailure extends Exception {
  HttpFailure(int status,boolean pairing){super(pairing&&(status==401||status==429)?pairingError(status):
   status==401?"请先配对当前服务器":status==429?"操作过快，请稍后重试":
   status>=300&&status<400?"服务器返回重定向，请填写最终 HTTPS 地址":"请求失败（"+status+"），请检查服务器状态");}
 }
 static String apiError(Exception error){
  if(error instanceof HttpFailure)return error.getMessage();
  String code=failure(error);
  return code.equals("network")?"服务器响应无法读取，请检查完整 API 地址、后端版本和网络":title(code)+"。"+detail(code);
 }
 static String title(String code){
  switch(code){
   case "ok":return "服务器可以连接";
   case "address":return "地址格式需要调整";
   case "dns":return "找不到服务器地址";
   case "connect":return "无法建立连接";
   case "timeout":return "连接超时";
   case "tls":return "HTTPS 证书校验失败";
   case "redirect":return "地址发生了跳转";
   case "missing":return "未找到连接检测接口";
   case "denied":return "访问被服务器拦截";
   case "upstream":return "代理无法连接后端";
   case "response":return "响应不是 Pi Console 检测结果";
   case "version":return "检测接口版本不兼容";
   case "rate":return "请求过于频繁";
   case "http":return "服务器返回异常状态";
   default:return "网络连接未完成";
  }
 }
 static String detail(String code){
  switch(code){
   case "ok":return "HTTPS 校验与后端身份检测通过。此检测不会保存地址或发送配对凭据。";
   case "address":return "填写完整 HTTPS API 地址；不要附带账号、查询参数或页面片段。";
   case "dns":return "检查域名拼写及手机 DNS；使用私网域名时确认已连接对应网络或 VPN。";
   case "connect":return "检查地址和端口，以及服务器、反向代理和防火墙是否允许手机访问。";
   case "timeout":return "检查手机网络、VPN 和服务器响应；网络恢复后可重新检测。";
   case "tls":return "检查手机时间、证书有效期、域名匹配及完整证书链。证书须受手机系统信任。";
   case "redirect":return "填写跳转后的最终 HTTPS API 地址，保留正确的后端路径。";
   case "missing":return "检查 /pi-console 等路径是否正确。旧版后端没有此接口，可升级后端，或继续手动保存和配对。";
   case "denied":return "检查代理登录要求、来源地址限制或防火墙；检测不会携带任何登录凭据。";
   case "upstream":return "在服务器检查后端是否运行，以及反向代理的目标地址和端口。";
   case "response":return "可能填成了网站首页或其他服务地址；请检查完整 API 路径。";
   case "version":return "请核对 App 与后端版本，并按项目发布说明升级。";
   case "rate":return "稍等后重试；同时检查代理的请求频率限制。";
   default:return "检查网络与服务器配置后重试；检测不会改变已有地址或配对。";
  }
 }
}
