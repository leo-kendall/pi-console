// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.Activity;
import android.content.*;
import android.net.Uri;
import org.json.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

/** Versioned settings only; pairing credentials and desktop secrets never exported. */
final class BackupTransfer {
 private final MainActivity activity;
 private final ExecutorService executor=Executors.newSingleThreadExecutor();
 private volatile boolean busy=false;
 private boolean selecting=false;
 private JSONObject ui,pending;
 BackupTransfer(MainActivity a){activity=a;}
 boolean busy(){return busy||selecting;}
 private void check()throws Exception{if(busy())throw new Exception("已有备份任务进行中");if(SecretStore.read(activity).isEmpty())throw new Exception("请先配对手机");}
 void exportSettings(JSONObject ui)throws Exception{check();BackupRules.ui(ui.getString("theme"),ui.getInt("frequency"));this.ui=ui;selecting=true;try{activity.startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json").putExtra(Intent.EXTRA_TITLE,"pi-console-settings.json"),51);}catch(Exception e){selecting=false;throw e;}}
 void importSettings()throws Exception{check();pending=null;selecting=true;try{activity.startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),52);}catch(Exception e){selecting=false;throw e;}}
 private JSONObject server(String method,String body)throws Exception{String token=SecretStore.read(activity);if(token.isEmpty())throw new IOException("配对已移除");return new JSONObject(StatusClient.request(activity,method,"/api/backup",body));}
 private static void exact(JSONObject object,String...fields)throws Exception{if(object.length()!=fields.length)throw new IOException("备份包含不支持的字段");for(String f:fields)if(!object.has(f))throw new IOException("备份缺少字段："+f);}
 private static List<AppStore.Entry> apps(JSONArray array)throws Exception{if(array.length()>40)throw new IOException("最多恢复 40 个应用入口");List<AppStore.Entry> list=new ArrayList<>();for(int i=0;i<array.length();i++){JSONObject e=array.getJSONObject(i);exact(e,"name","url","inline");String name=e.getString("name");if(name.isEmpty()||name.length()>64||!(e.get("inline") instanceof Boolean))throw new IOException("应用入口格式无效");list.add(new AppStore.Entry(name,UrlRules.validate(e.getString("url")),e.getBoolean("inline")));}return list;}
 private static void validate(JSONObject b)throws Exception{
  exact(b,"schema","kind","app","server");if(b.getInt("schema")!=1||!"pi-console-settings".equals(b.getString("kind")))throw new IOException("不支持的备份格式");JSONObject app=b.getJSONObject("app");exact(app,"apps","theme","frequency");BackupRules.ui(app.getString("theme"),app.getInt("frequency"));apps(app.getJSONArray("apps"));JSONObject server=b.getJSONObject("server");exact(server,"schema","alert_rules");if(server.getInt("schema")!=1)throw new IOException("服务器备份版本不支持");JSONObject rules=server.getJSONObject("alert_rules");exact(rules,"temperature","memory","disk","watch");for(String key:new String[]{"temperature","memory","disk"})if(!(rules.get(key) instanceof Number))throw new IOException("阈值类型无效");BackupRules.thresholds(rules.getDouble("temperature"),rules.getDouble("memory"),rules.getDouble("disk"));JSONArray watch=rules.getJSONArray("watch");Set<String> seen=new HashSet<>();for(int i=0;i<watch.length();i++){String key=watch.getString(i);if(!key.matches("[a-z][a-z0-9-]{0,31}")||!seen.add(key))throw new IOException("监控对象无效");}
 }
 boolean result(int request,int result,Intent data){if(request!=51&&request!=52)return false;if(!PendingDocumentRequest.accepts(request,selecting,ui!=null)){
  if(request==51&&result==Activity.RESULT_OK&&data!=null&&data.getData()!=null)try{android.provider.DocumentsContract.deleteDocument(activity.getContentResolver(),data.getData());}catch(Exception ignored){}
  android.widget.Toast.makeText(activity,"备份文件选择已失效，请重新选择",android.widget.Toast.LENGTH_LONG).show();activity.backupEvent("result",message(false,"备份文件选择已失效，请重新选择"));selecting=false;return true;
 }selecting=false;if(result!=Activity.RESULT_OK||data==null||data.getData()==null){activity.backupEvent("result",message(false,"已取消备份文件选择"));return true;}Uri uri=data.getData();busy=true;executor.execute(()->{try{
  if(request==51){JSONArray entries=new JSONArray();for(AppStore.Entry e:new AppStore(activity).load())entries.put(new JSONObject().put("name",e.name).put("url",e.url).put("inline",e.inline));JSONObject bundle=new JSONObject().put("schema",1).put("kind","pi-console-settings").put("app",new JSONObject().put("apps",entries).put("theme",ui.getString("theme")).put("frequency",ui.getInt("frequency"))).put("server",server("GET",""));validate(bundle);byte[] encoded=bundle.toString(2).getBytes("UTF-8");BackupRules.encodedSize(encoded.length);try(OutputStream out=activity.getContentResolver().openOutputStream(uri,"wt")){if(out==null)throw new IOException("无法写入备份文件");out.write(encoded);}activity.backupEvent("result",message(true,"配置备份已保存"));}
  else {ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream in=activity.getContentResolver().openInputStream(uri)){if(in==null)throw new IOException("无法读取备份");byte[] chunk=new byte[4096];int n;while((n=in.read(chunk))!=-1){if(bytes.size()+n>65536)throw new IOException("备份文件不能超过 64 KiB");bytes.write(chunk,0,n);}}JSONObject bundle=new JSONObject(new String(bytes.toByteArray(),"UTF-8"));validate(bundle);pending=bundle;JSONObject app=bundle.getJSONObject("app");activity.backupEvent("preview",new JSONObject().put("apps",app.getJSONArray("apps").length()).put("theme",app.getString("theme")).put("frequency",app.getInt("frequency")).put("rules",bundle.getJSONObject("server").getJSONObject("alert_rules")));}
 }catch(Exception e){if(request==51)try{android.provider.DocumentsContract.deleteDocument(activity.getContentResolver(),uri);}catch(Exception ignored){}activity.backupEvent("result",message(false,"备份操作失败："+e.getMessage()));}finally{busy=false;}});return true;}
 void apply()throws Exception{check();if(pending==null)throw new IOException("请先选择并预览备份文件");final JSONObject bundle=pending;validate(bundle);busy=true;executor.execute(()->{boolean serverChanged=false;try{server("POST",bundle.getJSONObject("server").toString());serverChanged=true;JSONObject app=bundle.getJSONObject("app");new AppStore(activity).save(apps(app.getJSONArray("apps")));pending=null;activity.backupEvent("result",new JSONObject().put("ok",true).put("message","配置已恢复").put("settings",new JSONObject().put("theme",app.getString("theme")).put("frequency",app.getInt("frequency"))));}catch(Exception e){activity.backupEvent("result",message(false,(serverChanged?"服务器告警规则已更新，手机配置保存未确认：":"恢复失败：")+e.getMessage()));}finally{busy=false;}});}
 private JSONObject message(boolean ok,String message){try{return new JSONObject().put("ok",ok).put("message",message);}catch(Exception e){return new JSONObject();}}
 void close(){executor.shutdown();}
}
