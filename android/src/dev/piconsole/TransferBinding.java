// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
import java.lang.reflect.*;

/** Persist only identity, then decrypt a fresh credential from that saved profile. */
final class TransferBinding {
 final ServerSettings.Snapshot snapshot;final String profile,server;
 private TransferBinding(ServerSettings.Snapshot snapshot,String profile)throws Exception{if(snapshot.token.isEmpty())throw new Exception("请先配对这台服务器");this.snapshot=snapshot;this.profile=profile;server=snapshot.endpoint.canonical;}
 static TransferBinding capture(Context c)throws Exception{ServerSettings.Snapshot s=ServerSettings.snapshot(c);String profile=s.endpoint.canonical;try{profile=(String)ServerSettings.class.getDeclaredMethod("activeId",Context.class).invoke(null,c);}catch(NoSuchMethodException ignored){}return new TransferBinding(s,profile);}
 static TransferBinding resolve(Context c,TransferEngine.Job job)throws Exception{
  ServerSettings.Snapshot s;
  try{s=(ServerSettings.Snapshot)ServerSettings.class.getDeclaredMethod("snapshot",Context.class,String.class).invoke(null,c,job.profile);}
  catch(NoSuchMethodException ignored){TransferBinding current=capture(c);if(!current.profile.equals(job.profile))throw new Exception("请切换回任务所属服务器后继续");s=current.snapshot;}
  catch(InvocationTargetException e){throw new Exception("任务所属服务器已删除或配对已移除");}
  TransferBinding binding=new TransferBinding(s,job.profile);if(!binding.server.equals(job.server))throw new Exception("服务器地址已变化，请重新选择文件");return binding;
 }
 void check(Context c,TransferEngine.Job job)throws Exception{TransferBinding fresh=resolve(c,job);if(!fresh.server.equals(server)||!fresh.snapshot.token.equals(snapshot.token))throw new Exception("任务配对已变化，传输已暂停");}
 boolean owns(TransferEngine.Job job){return profile.equals(job.profile)&&server.equals(job.server);}
}
