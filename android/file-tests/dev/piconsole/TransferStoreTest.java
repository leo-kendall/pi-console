// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.io.*;
import java.nio.file.*;
public final class TransferStoreTest {
 public static void main(String[] args)throws Exception{
  File dir=Files.createTempDirectory("transfer-store-").toFile();TransferStore store=new TransferStore(dir);
  TransferEngine.Job j=new TransferEngine.Job("a1234567-1234-1234-1234-123456789abc","upload",2L*1024*1024*1024);j.profile="profile-a";j.server="https://fixture.example.test";j.uri="content://fixture/private";j.offset=123;j.uploadId="remote";j.status="running";store.save(j);
  TransferEngine.Job restored=new TransferStore(dir).get(j.id);TransferEngineTest.check(restored.offset==123&&restored.startRequest.equals(j.startRequest)&&restored.finishRequest.equals(j.finishRequest),"durable offsets and request IDs");
  store.recover();TransferEngineTest.check(store.get(j.id).status.equals("paused"),"process death requires explicit resume");
  TransferEngineTest.check(store.list("other","https://fixture.example.test").isEmpty(),"jobs isolated by profile");
  TransferEngineTest.check(store.list("profile-a","https://different.example.test").isEmpty(),"jobs bound to endpoint");
  try{store.get("../../outside");throw new AssertionError("path traversal");}catch(IllegalArgumentException expected){}
  File part=store.stage(j);Files.write(part.toPath(),new byte[]{1,2});store.remove(j);TransferEngineTest.check(!part.exists()&&store.list().isEmpty(),"cancellation cleanup removes app-private stage");
  for(int n=0;n<32;n++){TransferEngine.Job queued=new TransferEngine.Job(String.format("%08x-1234-1234-1234-123456789abc",n),"upload",0);store.save(queued);}
  try{store.save(new TransferEngine.Job("ffffffff-1234-1234-1234-123456789abc","upload",0));throw new AssertionError("queue bound");}catch(IOException expected){}
  System.out.println("Transfer store: durable IDs, restart pause, profile/endpoint isolation, traversal, stage cleanup and queue bounds passed");
 }
}
