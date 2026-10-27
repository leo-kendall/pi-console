// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class TransferEngineTest {
 static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
 static final class Host implements TransferEngine.Host {
  byte[] source;File stage;int saves,published;long pauseAt=Long.MAX_VALUE;boolean changed;TransferStore journal;
  Host(byte[] source)throws Exception{this.source=source;stage=File.createTempFile("transfer-test-",".part");stage.deleteOnExit();}
  public InputStream source(TransferEngine.Job j){return new ByteArrayInputStream(source);}
  public File stage(TransferEngine.Job j){return stage;}
  public void save(TransferEngine.Job j)throws Exception{saves++;if(journal!=null)journal.save(j);}
  public void check(TransferEngine.Job j)throws Exception{if(j.offset>=pauseAt)throw new InterruptedException("paused");}
  public void publish(TransferEngine.Job j,File file)throws Exception{TransferEngineTest.check(Arrays.equals(source,Files.readAllBytes(file.toPath())),"published bytes match");published++;}
 }
 static final class Remote implements TransferEngine.Remote {
  byte[] data;ByteArrayOutputStream upload=new ByteArrayOutputStream();String ticket="ticket-a";int chunks,finishes,starts;boolean loseAck,loseFinish,badOffset,emptyChunk;String lastRequest="";
  Remote(byte[] data){this.data=data;}
  public TransferEngine.Upload start(TransferEngine.Job j){starts++;lastRequest=j.startRequest;return new TransferEngine.Upload("server-id",upload.size(),j.size);}
  public TransferEngine.Upload status(TransferEngine.Job j){return new TransferEngine.Upload("server-id",upload.size(),j.size);}
  public long append(TransferEngine.Job j,long offset,byte[] b,int count)throws Exception{check(offset==upload.size(),"correct remote offset");upload.write(b,0,count);chunks++;if(loseAck){loseAck=false;throw new IOException("ack lost");}return upload.size();}
  public String finish(TransferEngine.Job j)throws Exception{finishes++;check(j.sha256.equals(TransferEngine.digest(upload.toByteArray())),"finish checksum matches remote");if(loseFinish){loseFinish=false;throw new IOException("finish ack lost");}return "operation-id";}
  public TransferEngine.Action action(TransferEngine.Job j){return new TransferEngine.Action("success","");}
  public TransferEngine.Stat stat(TransferEngine.Job j){return new TransferEngine.Stat(data.length,ticket);}
  public TransferEngine.Chunk read(TransferEngine.Job j,long offset){int end=(int)Math.min(data.length,offset+TransferEngine.CHUNK);return new TransferEngine.Chunk(badOffset?offset+1:offset,data.length,emptyChunk?new byte[0]:Arrays.copyOfRange(data,(int)offset,end),end==data.length);}
 }
 static byte[] content(){byte[] b=new byte[TransferEngine.CHUNK*3+19];new Random(42).nextBytes(b);return b;}
 public static void main(String[] args)throws Exception{
  byte[] bytes=content();Host h=new Host(bytes);Remote r=new Remote(bytes);TransferEngine.Job j=new TransferEngine.Job("a","upload",bytes.length);r.loseAck=true;
  try{TransferEngine.run(j,r,h);throw new AssertionError("lost acknowledgement must stop");}catch(IOException expected){}
  check(j.offset==0&&r.upload.size()==TransferEngine.CHUNK,"server may advance before local save");String request=j.startRequest;
  TransferEngine.run(j,r,h);check(Arrays.equals(bytes,r.upload.toByteArray()),"resume avoids duplicated bytes");check(j.status.equals("completed")&&r.starts==1&&request.equals(r.lastRequest),"stable start request");
  h=new Host(bytes);r=new Remote(bytes);j=new TransferEngine.Job("b","upload",bytes.length);h.pauseAt=TransferEngine.CHUNK;
  try{TransferEngine.run(j,r,h);throw new AssertionError("pause stops at chunk boundary");}catch(InterruptedException expected){}
  check(j.offset==TransferEngine.CHUNK,"pause retains progress");h.pauseAt=Long.MAX_VALUE;TransferEngine.run(j,r,h);check(r.chunks==4,"resume uses server offset");
  h=new Host(bytes);r=new Remote(bytes);j=new TransferEngine.Job("c","upload",bytes.length);r.loseFinish=true;
  try{TransferEngine.run(j,r,h);throw new AssertionError("finish response lost");}catch(IOException expected){}
  String finishRequest=j.finishRequest;h.source=new byte[0];TransferEngine.run(j,r,h);check(r.finishes==2&&finishRequest.equals(j.finishRequest),"finish retry stable and does not reread source");
  h=new Host(bytes);r=new Remote(bytes);j=new TransferEngine.Job("d","download",bytes.length);h.pauseAt=TransferEngine.CHUNK;
  try{TransferEngine.run(j,r,h);throw new AssertionError("download paused");}catch(InterruptedException expected){}
  check(h.stage.length()==TransferEngine.CHUNK,"download stage checkpoint");h.pauseAt=Long.MAX_VALUE;TransferEngine.run(j,r,h);check(h.published==1,"publish only after complete");
  h=new Host(bytes);r=new Remote(bytes);j=new TransferEngine.Job("e","download",bytes.length);h.pauseAt=TransferEngine.CHUNK;
  try{TransferEngine.run(j,r,h);}catch(InterruptedException expected){}
  r.ticket="ticket-b";Arrays.fill(bytes,(byte)8);h.pauseAt=Long.MAX_VALUE;TransferEngine.run(j,r,h);check(h.published==1,"changed identity restarts whole stage");
  try{new TransferEngine.Job("bad","upload",TransferEngine.MAX_BYTES+1);throw new AssertionError("size bound");}catch(IllegalArgumentException expected){}
  check(new TransferEngine.Job("large","upload",2L*1024*1024*1024).size>Integer.MAX_VALUE,"large files use long offsets");
  for(boolean empty:new boolean[]{false,true}){h=new Host(bytes);r=new Remote(bytes);r.badOffset=!empty;r.emptyChunk=empty;j=new TransferEngine.Job("invalid","download",bytes.length);try{TransferEngine.run(j,r,h);throw new AssertionError("invalid remote chunk accepted");}catch(IOException expected){}check(h.published==0,"malformed chunks never publish");}
  h=new Host(bytes);h.journal=new TransferStore(Files.createTempDirectory("transfer-crash-").toFile());r=new Remote(bytes);r.loseAck=true;j=new TransferEngine.Job("01234567-1234-1234-1234-123456789abc","upload",bytes.length);try{TransferEngine.run(j,r,h);}catch(IOException expected){}j=h.journal.get(j.id);TransferEngine.run(j,r,h);check(Arrays.equals(bytes,r.upload.toByteArray()),"actual persisted record resumes lost ACK after process replacement");
  System.out.println("Transfer engine: lost ACK, resume, pause, idempotent finish, staged download, changed identity and 8 GiB bounds passed");
 }
}
