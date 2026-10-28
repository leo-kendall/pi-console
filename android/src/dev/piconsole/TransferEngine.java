// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** Bounded streaming protocol. Host owns persistence/SAF, Remote owns captured transport. */
final class TransferEngine {
 static final int CHUNK=128*1024;static final long MAX_BYTES=8L*1024*1024*1024;
 static final class RateLimited extends IOException {RateLimited(){super("服务器操作限流，请稍后继续核实原任务");}}
 static final class Job {
  final String id,kind;final long size;
  String profile="",server="",root="default",uri="",grantUri="",name="",directory="",path="",ticket="",uploadId="",sha256="",actionId="";
  String startRequest=UUID.randomUUID().toString(),finishRequest=UUID.randomUUID().toString();
  volatile String status="queued",message="等待传输";volatile long offset=0;
  Job(String id,String kind,long size){if(size<0||size>MAX_BYTES||!Arrays.asList("upload","download").contains(kind))throw new IllegalArgumentException("单文件最多 8 GiB，大小必须明确");this.id=id;this.kind=kind;this.size=size;}
 }
 static final class Upload {final String id;final long offset,size;Upload(String id,long offset,long size){this.id=id;this.offset=offset;this.size=size;}}
 static final class Stat {final long size;final String ticket;Stat(long size,String ticket){this.size=size;this.ticket=ticket;}}
 static final class Chunk {final long offset,size;final byte[] data;final boolean eof;Chunk(long offset,long size,byte[] data,boolean eof){this.offset=offset;this.size=size;this.data=data;this.eof=eof;}}
 static final class Action {final String state,message;Action(String state,String message){this.state=state;this.message=message;}}
 interface Remote {
  Upload start(Job j)throws Exception;Upload status(Job j)throws Exception;long append(Job j,long offset,byte[] data,int count)throws Exception;
  String finish(Job j)throws Exception;Action action(Job j)throws Exception;Stat stat(Job j)throws Exception;Chunk read(Job j,long offset)throws Exception;
 }
 interface Host {
  InputStream source(Job j)throws Exception;File stage(Job j)throws Exception;void save(Job j)throws Exception;void check(Job j)throws Exception;void publish(Job j,File stage)throws Exception;
 }
 static String digest(byte[] bytes)throws Exception{return hex(MessageDigest.getInstance("SHA-256").digest(bytes));}
 private static String hex(byte[] bytes){StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
 static void run(Job j,Remote remote,Host host)throws Exception {
  host.check(j);j.status="running";host.save(j);
  if("upload".equals(j.kind))upload(j,remote,host);else download(j,remote,host);
  host.check(j);j.status="completed";j.message="传输完成";host.save(j);
 }
 private static void upload(Job j,Remote remote,Host host)throws Exception {
  if(j.sha256.isEmpty()){
   host.check(j);Upload u=j.uploadId.isEmpty()?remote.start(j):remote.status(j);
   if(u.id==null||u.id.isEmpty()||u.size!=j.size||u.offset<0||u.offset>j.size)throw new IOException("服务器上传位置不匹配");
   j.uploadId=u.id;j.offset=u.offset;host.save(j);MessageDigest hash=MessageDigest.getInstance("SHA-256");byte[] buffer=new byte[CHUNK];long consumed=0;
   try(InputStream in=host.source(j)){
    if(in==null)throw new IOException("无法读取所选文件，请重新授权");
    while(consumed<j.size){
     host.check(j);long boundary=consumed<j.offset?j.offset:j.size;int wanted=(int)Math.min(CHUNK,boundary-consumed),count=read(in,buffer,wanted);
     if(count==0)throw new IOException("手机文件大小已变化，未发布");hash.update(buffer,0,count);
     if(consumed>=j.offset){long next=remote.append(j,j.offset,buffer,count);if(next!=j.offset+count)throw new IOException("服务器上传没有按预期推进");j.offset=next;host.save(j);}
     consumed+=count;
    }
    if(in.read()!=-1)throw new IOException("手机文件大小已变化，未发布");
   }
   j.sha256=hex(hash.digest());host.save(j);
  }
  host.check(j);j.status="verifying";j.message="正在核实服务器发布结果";host.save(j);
  if(j.actionId.isEmpty()){
   for(int attempt=0;attempt<4;attempt++){
    host.check(j);
    try{j.actionId=remote.finish(j);host.save(j);break;}
    catch(RateLimited limited){if(attempt==3)throw limited;j.message="服务器忙，稍后核实同一上传请求";host.save(j);for(int tick=0;tick<21;tick++){host.check(j);Thread.sleep(100);}}
   }
  }
  for(int n=0;n<60;n++){
   host.check(j);Action action=remote.action(j);
   if("success".equals(action.state))return;
   if(!"queued".equals(action.state)&&!"running".equals(action.state))throw new IOException(action.message.isEmpty()?"上传发布未成功，请核实原任务":action.message);
   Thread.sleep(500);
  }
  throw new IOException("发布结果尚未确认，继续任务会核实原操作");
 }
 private static int read(InputStream in,byte[] bytes,int count)throws IOException{int offset=0;while(offset<count){int n=in.read(bytes,offset,count-offset);if(n<0)break;if(n==0)throw new IOException("读取文件没有进展");offset+=n;}return offset;}
 private static void download(Job j,Remote remote,Host host)throws Exception {
  host.check(j);Stat stat=remote.stat(j);if(stat.size!=j.size||stat.ticket==null||stat.ticket.isEmpty())throw new IOException("服务器文件大小已变化，请重新打开详情");File file=host.stage(j);
  try(RandomAccessFile out=new RandomAccessFile(file,"rw")){
   // Ticket includes source identity. A backend restart/source change must never mix prefixes.
   if(!j.ticket.equals(stat.ticket)||j.offset<0||j.offset>j.size||out.length()<j.offset){j.offset=0;out.setLength(0);}
   j.ticket=stat.ticket;out.setLength(j.offset);host.save(j);
   while(j.offset<j.size){
    host.check(j);Chunk chunk=remote.read(j,j.offset);
    if(chunk.data==null||chunk.data.length==0||chunk.data.length>CHUNK||chunk.offset!=j.offset||chunk.size!=j.size||j.offset+chunk.data.length>j.size||chunk.eof!=(j.offset+chunk.data.length==j.size))throw new IOException("下载数据位置或大小不匹配");
    out.seek(j.offset);out.write(chunk.data);out.getFD().sync();j.offset+=chunk.data.length;host.save(j);
   }
   out.getFD().sync();
  }
  host.check(j);j.status="saving";j.message="正在保存到手机所选位置";host.save(j);host.publish(j,file);
 }
}
