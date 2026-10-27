// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.Activity;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.provider.DocumentsContract;
import org.json.*;
import java.util.*;

/** Foreground SAF selection only. TransferService owns network and durable work. */
final class FileTransfer implements TransferService.Listener {
 private final MainActivity activity;private boolean selecting;private int request;private JSONObject selection;private TransferBinding binding;
 FileTransfer(MainActivity activity){this.activity=activity;TransferService.listen(this);}
 boolean busy(){return selecting||TransferService.busy();}
 JSONObject state()throws Exception{return TransferService.state(activity).put("busy",busy());}
 void command(String id,String action)throws Exception{TransferService.command(activity,id,action);}
 void upload(String directory)throws Exception{upload(new JSONObject().put("directory",directory));}
 void upload(JSONObject destination)throws Exception{
  check();selection=new JSONObject(destination.toString());request=41;selecting=true;
  Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
  try{activity.startActivityForResult(intent,request);}catch(Exception e){selecting=false;throw e;}
 }
 void download(JSONObject file)throws Exception{
  check();selection=new JSONObject(file.toString());JSONArray items=file.optJSONArray("items");if(items!=null&&(items.length()<1||items.length()>32))throw new Exception("批量下载最多 32 项");
  if(items==null)size(file.getLong("bytes"));else for(int n=0;n<items.length();n++)size(items.getJSONObject(n).getLong("bytes"));
  request=items==null?42:43;selecting=true;Intent intent=items==null?new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,file.getString("name")):new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
  intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
  try{activity.startActivityForResult(intent,request);}catch(Exception e){selecting=false;throw e;}
 }
 private void check()throws Exception{if(selecting)throw new Exception("请先完成当前文件选择");binding=TransferBinding.capture(activity);}
 private static void size(long size)throws Exception{if(size<0||size>TransferEngine.MAX_BYTES)throw new Exception("请选择大小明确且不超过 8 GiB 的普通文件");}
 private TransferEngine.Job job(String kind,Uri uri,Uri grant,String name,long size,String root)throws Exception{size(size);TransferEngine.Job j=new TransferEngine.Job(UUID.randomUUID().toString(),kind,size);j.profile=binding.profile;j.server=binding.server;j.root=root;j.uri=uri.toString();j.grantUri=grant.toString();j.name=name;return j;}
 private void retain(Uri uri,int flags,int needed)throws Exception{if((flags&needed)!=needed)throw new Exception("文件提供方没有授予所需权限，请选择其他位置");try{activity.getContentResolver().takePersistableUriPermission(uri,flags&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION));}catch(Exception e){throw new Exception("这个文件提供方不支持保留访问权限，请选择手机文档中的其他位置");}}
 boolean result(int req,int result,Intent intent){
  if(req!=41&&req!=42&&req!=43)return false;
  if(!selecting||req!=request||selection==null||binding==null){if(req==42&&result==Activity.RESULT_OK&&intent!=null&&intent.getData()!=null)try{DocumentsContract.deleteDocument(activity.getContentResolver(),intent.getData());}catch(Exception ignored){}selecting=false;notice("文件选择已失效，请重新选择");return true;}
  selecting=false;if(result!=Activity.RESULT_OK||intent==null){notice("已取消文件选择");return true;}
  List<TransferEngine.Job> jobs=new ArrayList<>();List<Uri> created=new ArrayList<>(),retained=new ArrayList<>();
  try{
   TransferBinding current=TransferBinding.capture(activity);if(!current.profile.equals(binding.profile)||!current.server.equals(binding.server)||!current.snapshot.token.equals(binding.snapshot.token))throw new Exception("服务器配对已变化，请重新选择文件");
   String root=selection.optString("root","default");
   if(req==41){
    List<Uri> uris=new ArrayList<>();ClipData clips=intent.getClipData();if(clips!=null){if(clips.getItemCount()>32)throw new Exception("一次最多选择 32 个文件");for(int n=0;n<clips.getItemCount();n++)uris.add(clips.getItemAt(n).getUri());}else if(intent.getData()!=null)uris.add(intent.getData());
    if(uris.isEmpty())throw new Exception("没有选择文件");Set<String> names=new HashSet<>();
    for(Uri uri:uris){String name=null;long bytes=-1;try(Cursor c=activity.getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE},null,null,null)){if(c!=null&&c.moveToFirst()){name=c.getString(0);if(!c.isNull(1))bytes=c.getLong(1);}}
     if(name==null||name.isEmpty()||name.contains("/")||name.contains("\\")||name.startsWith(".")||!names.add(name))throw new Exception("文件名称无效或重复，请分开选择");size(bytes);retain(uri,intent.getFlags(),Intent.FLAG_GRANT_READ_URI_PERMISSION);retained.add(uri);TransferEngine.Job j=job("upload",uri,uri,name,bytes,root);j.directory=selection.optString("directory","");jobs.add(j);}
   }else{
    Uri target=intent.getData();if(target==null)throw new Exception("没有选择保存位置");retain(target,intent.getFlags(),Intent.FLAG_GRANT_WRITE_URI_PERMISSION);retained.add(target);
    JSONArray items=selection.optJSONArray("items");if(items==null){TransferEngine.Job j=job("download",target,target,selection.getString("name"),selection.getLong("bytes"),root);j.path=selection.getString("path");j.ticket=selection.getString("ticket");jobs.add(j);created.add(target);}
    else{Uri parent=DocumentsContract.buildDocumentUriUsingTree(target,DocumentsContract.getTreeDocumentId(target));for(int n=0;n<items.length();n++){JSONObject item=items.getJSONObject(n);Uri child=DocumentsContract.createDocument(activity.getContentResolver(),parent,"application/octet-stream",item.getString("name"));if(child==null)throw new Exception("无法在所选文件夹创建文件");created.add(child);TransferEngine.Job j=job("download",child,target,item.getString("name"),item.getLong("bytes"),root);j.path=item.getString("path");j.ticket=item.getString("ticket");jobs.add(j);}}
   }
   TransferService.enqueue(activity,jobs);notice("已加入后台传输队列；可以离开页面，仍可暂停和继续");
  }catch(Exception e){for(Uri uri:created)try{DocumentsContract.deleteDocument(activity.getContentResolver(),uri);}catch(Exception ignored){}for(Uri uri:retained)TransferService.releaseUnused(activity,uri.toString());notice(e.getMessage()==null?"文件任务未启动":e.getMessage());}
  finally{selection=null;binding=null;}
  return true;
 }
 private void notice(String message){try{activity.fileProgress(new JSONObject().put("message",message).put("percent",0));}catch(Exception ignored){}android.widget.Toast.makeText(activity,message,android.widget.Toast.LENGTH_LONG).show();}
 public void progress(JSONObject event){activity.fileProgress(event);}
 void close(){TransferService.unlisten(this);}
}
