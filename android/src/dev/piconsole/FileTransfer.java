// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.Activity;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.provider.DocumentsContract;
import android.util.Base64;
import org.json.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.concurrent.*;

/** SAF-only phone file access. Server transfers are bounded, chunked and authenticated. */
final class FileTransfer {
 private final MainActivity activity;
 private final ExecutorService executor=Executors.newSingleThreadExecutor();
 private boolean selecting=false;
 private volatile boolean busy=false;
 private String directory="";
 private JSONObject download;
 private volatile String last="尚无传输任务";
 boolean busy(){return busy||selecting;}
 FileTransfer(MainActivity activity){this.activity=activity;}
 JSONObject state()throws Exception{return new JSONObject().put("busy",busy||selecting).put("message",last);}
 void upload(String directory)throws Exception{check();this.directory=directory;selecting=true;Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);try{activity.startActivityForResult(i,41);}catch(Exception e){selecting=false;throw e;}}
 void download(JSONObject file)throws Exception{check();if(file.getLong("bytes")>100L*1024*1024)throw new Exception("一次最多下载 100 MiB");download=file;selecting=true;Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,file.getString("name"));try{activity.startActivityForResult(i,42);}catch(Exception e){selecting=false;throw e;}}
 private void check()throws Exception{if(busy||selecting)throw new Exception("已有文件任务进行中");if(SecretStore.read(activity).isEmpty())throw new Exception("请先配对手机");}
 private JSONObject api(String path,JSONObject body)throws Exception{String token=SecretStore.read(activity);if(token.isEmpty())throw new Exception("配对已移除，传输已停止");return new JSONObject(StatusClient.request(activity,"POST",path,body.toString()));}
 private void progress(String text,int percent){last=text;try{activity.fileProgress(new JSONObject().put("message",text).put("percent",percent));}catch(Exception ignored){}}
 boolean result(int request,int result,Intent intent){if(request!=41&&request!=42)return false;if(!PendingDocumentRequest.accepts(request,selecting,download!=null)){
  if(request==42&&result==Activity.RESULT_OK&&intent!=null&&intent.getData()!=null)try{DocumentsContract.deleteDocument(activity.getContentResolver(),intent.getData());}catch(Exception ignored){}
  progress("文件选择上下文已失效，请重新选择文件",0);android.widget.Toast.makeText(activity,"文件选择已失效，请重新选择文件",android.widget.Toast.LENGTH_LONG).show();selecting=false;return true;
 }selecting=false;if(result!=Activity.RESULT_OK||intent==null||intent.getData()==null){progress("已取消文件选择",0);return true;}final Uri uri=intent.getData();final JSONObject info=download;final String targetDir=directory;busy=true;executor.execute(()->{try{if(request==41)send(uri,targetDir);else receive(uri,info);}catch(Exception e){progress("传输失败："+(e.getMessage()==null?"请检查连接":e.getMessage()),0);}finally{busy=false;}});return true;}
 private void send(Uri uri,String dir)throws Exception{
  String name=null;long size=-1;
  try(Cursor c=activity.getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE},null,null,null)){if(c!=null&&c.moveToFirst()){name=c.getString(0);if(!c.isNull(1))size=c.getLong(1);}}
  if(name==null||size<0||size>100L*1024*1024)throw new Exception("请选择大小明确且不超过 100 MiB 的本地文件");
  String id=null;boolean submitted=false;
  try{
   JSONObject start=api("/api/files/upload/start",new JSONObject().put("directory",dir).put("name",name).put("size",size));id=start.getString("id");long offset=0;MessageDigest hash=MessageDigest.getInstance("SHA-256");byte[] buffer=new byte[128*1024];
   try(InputStream in=activity.getContentResolver().openInputStream(uri)){if(in==null)throw new IOException("无法读取所选文件");int count;while((count=in.read(buffer))!=-1){if(count==0)continue;if(offset+count>size)throw new IOException("文件大小已变化");hash.update(buffer,0,count);JSONObject d=api("/api/files/upload/chunk",new JSONObject().put("id",id).put("offset",offset).put("data",Base64.encodeToString(buffer,0,count,Base64.NO_WRAP)));offset=d.getLong("offset");progress("正在上传 "+name,size==0?100:(int)(offset*100/size));}}
   if(offset!=size)throw new IOException("文件大小已变化，未发布");StringBuilder hex=new StringBuilder();for(byte b:hash.digest())hex.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
   submitted=true;JSONObject op=api("/api/files/upload/finish",new JSONObject().put("id",id).put("sha256",hex.toString()).put("request",UUID.randomUUID().toString()));await(op);progress("上传完成："+name,100);
  }finally{if(id!=null&&!submitted)try{api("/api/files/upload/abort",new JSONObject().put("id",id));}catch(Exception ignored){progress("上传未完成；服务器暂存内容将在到期后清理",0);}}
 }
 private void await(JSONObject op)throws Exception{String id=op.getString("id");for(int i=0;i<50;i++){String state=op.getString("state");if("success".equals(state))return;if(!"queued".equals(state)&&!"running".equals(state))throw new IOException(op.getString("message"));Thread.sleep(300);op=new JSONObject(StatusClient.request(activity,"GET","/api/actions/"+id,""));}throw new IOException("结果尚未确认，请到操作记录核实原任务");}
 private void receive(Uri uri,JSONObject info)throws Exception{
  boolean complete=false;
  try(OutputStream out=activity.getContentResolver().openOutputStream(uri,"wt")){
   if(out==null)throw new IOException("无法写入手机文件");long offset=0,size=info.getLong("bytes");
   while(true){JSONObject d=api("/api/files/read",new JSONObject().put("path",info.getString("path")).put("ticket",info.getString("ticket")).put("offset",offset));byte[] bytes=Base64.decode(d.getString("data"),Base64.DEFAULT);if(bytes.length>128*1024||offset+bytes.length>size)throw new IOException("下载数据不匹配");out.write(bytes);offset+=bytes.length;progress("正在下载 "+info.getString("name"),size==0?100:(int)(offset*100/size));if(d.getBoolean("eof")){if(offset!=size)throw new IOException("文件下载不完整");break;}if(bytes.length==0)throw new IOException("下载没有进展");}
   out.flush();complete=true;progress("下载完成："+info.getString("name"),100);
  }finally{if(!complete)try{DocumentsContract.deleteDocument(activity.getContentResolver(),uri);}catch(Exception ignored){progress("下载未完成，手机可能保留部分文件，请手动删除",0);}}
 }
 void close(){executor.shutdown();}
}
