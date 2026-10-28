// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** App-private, token-free journal. A crash can lose an ACK, never the stable request ID. */
final class TransferStore {
 private static final Object LOCK=new Object();private final File directory;
 TransferStore(File directory)throws IOException{this.directory=directory;if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("无法创建本机传输队列");}
 private File file(String id,String suffix){if(id==null||!id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))throw new IllegalArgumentException("无效传输任务");return new File(directory,id+suffix);}
 File stage(TransferEngine.Job j){return file(j.id,".part");}
 TransferEngine.Job get(String id)throws Exception{synchronized(LOCK){Properties p=new Properties();try(InputStream in=new FileInputStream(file(id,".properties"))){p.load(in);}TransferEngine.Job j=new TransferEngine.Job(id,p.getProperty("kind"),Long.parseLong(p.getProperty("size")));j.profile=p.getProperty("profile","");j.server=p.getProperty("server","");j.root=p.getProperty("root","default");j.uri=p.getProperty("uri","");j.grantUri=p.getProperty("grantUri",j.uri);j.name=p.getProperty("name","");j.directory=p.getProperty("directory","");j.path=p.getProperty("path","");j.ticket=p.getProperty("ticket","");j.uploadId=p.getProperty("uploadId","");j.sha256=p.getProperty("sha256","");j.actionId=p.getProperty("actionId","");j.startRequest=p.getProperty("startRequest",j.startRequest);j.finishRequest=p.getProperty("finishRequest",j.finishRequest);j.status=p.getProperty("status","paused");j.message=p.getProperty("message","");j.offset=Long.parseLong(p.getProperty("offset","0"));if(j.offset<0||j.offset>j.size)throw new IOException("传输记录位置无效");return j;}}
 void save(TransferEngine.Job j)throws Exception{synchronized(LOCK){
  File target=file(j.id,".properties");if(!target.exists()&&list().size()>=32)throw new IOException("本机最多保留 32 个传输任务，请先清理已结束的任务");
  Properties p=new Properties();String[][] fields={{"kind",j.kind},{"size",Long.toString(j.size)},{"profile",j.profile},{"server",j.server},{"root",j.root},{"uri",j.uri},{"grantUri",j.grantUri},{"name",j.name},{"directory",j.directory},{"path",j.path},{"ticket",j.ticket},{"uploadId",j.uploadId},{"sha256",j.sha256},{"actionId",j.actionId},{"startRequest",j.startRequest},{"finishRequest",j.finishRequest},{"status",j.status},{"message",j.message},{"offset",Long.toString(j.offset)}};for(String[] field:fields)p.setProperty(field[0],field[1]);
  File temp=file(j.id,".new");try(FileOutputStream out=new FileOutputStream(temp)){p.store(out,"Pi Console transfer schema 1; no credentials");out.getFD().sync();}Files.move(temp.toPath(),target.toPath(),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
 }}
 List<TransferEngine.Job> list()throws Exception{synchronized(LOCK){List<TransferEngine.Job> jobs=new ArrayList<>();File[] files=directory.listFiles((dir,name)->name.matches("[0-9a-f-]{36}\\.properties"));if(files!=null){Arrays.sort(files,Comparator.comparingLong(File::lastModified));for(File f:files)try{jobs.add(get(f.getName().substring(0,36)));}catch(Exception ignored){/* Corrupt task is never executed. */}}return jobs;}}
 List<TransferEngine.Job> list(String profile,String server)throws Exception{List<TransferEngine.Job> out=new ArrayList<>();for(TransferEngine.Job j:list())if(j.profile.equals(profile)&&j.server.equals(server))out.add(j);return out;}
 void requireProfileEmpty(String profile)throws Exception{synchronized(LOCK){for(TransferEngine.Job j:list())if(j.profile.equals(profile))throw new IOException("请先切换到此服务器，在文件管理中取消未完成任务并移除传输记录，再删除服务器配置");}}
 void recover()throws Exception{for(TransferEngine.Job j:list())if(!Arrays.asList("completed","cancelled","paused","failed").contains(j.status)){j.status="paused";j.message="应用已重新启动，请确认后继续";save(j);}}
 void remove(TransferEngine.Job j)throws IOException{synchronized(LOCK){Files.deleteIfExists(file(j.id,".part").toPath());Files.deleteIfExists(file(j.id,".properties").toPath());Files.deleteIfExists(file(j.id,".new").toPath());}}
}
