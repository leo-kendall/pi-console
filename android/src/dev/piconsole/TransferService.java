// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.net.Uri;
import android.os.*;
import android.util.Base64;
import org.json.*;
import java.io.*;
import java.lang.ref.WeakReference;
import java.util.*;
import java.util.concurrent.*;

/** User-started durable dataSync queue. Process death pauses rather than silently retargeting. */
public final class TransferService extends Service {
 interface Listener{void progress(JSONObject event);}
 private static volatile WeakReference<Listener> listener=new WeakReference<>(null);
 private static final ConcurrentMap<String,String> signals=new ConcurrentHashMap<>();
 private static final Set<String> requested=ConcurrentHashMap.newKeySet();
 private static final java.util.concurrent.locks.ReentrantLock WORK_LOCK=new java.util.concurrent.locks.ReentrantLock();
 private static final Object QUEUE_LOCK=new Object();private static volatile TransferEngine.Job activeJob;
 static volatile boolean running;private volatile boolean destroyed;private ExecutorService executor;private NotificationManager manager;private final java.util.concurrent.atomic.AtomicInteger pending=new java.util.concurrent.atomic.AtomicInteger();private final Set<String> scheduled=ConcurrentHashMap.newKeySet();private volatile int latestStart;
 private static final int NOTIFICATION=5100;private static final long RESERVE=128L*1024*1024;
 static TransferStore store(Context c)throws Exception{return new TransferStore(new File(c.getFilesDir(),"file-transfers-v1"));}
 static void listen(Listener l){listener=new WeakReference<>(l);}
 static void unlisten(Listener l){if(listener.get()==l)listener.clear();}
 static boolean busy(){return running||activeJob!=null||!requested.isEmpty();}
 static JSONObject state(Context c)throws Exception{
  TransferBinding binding=TransferBinding.capture(c);JSONArray jobs=new JSONArray();String message="尚无传输任务";
  for(TransferEngine.Job j:store(c).list(binding.profile,binding.server)){jobs.put(json(j));message=j.message;}
  return new JSONObject().put("schema",1).put("available",true).put("background",true).put("resumable",true).put("busy",busy()).put("jobs",jobs).put("message",message).put("max_file_bytes",TransferEngine.MAX_BYTES);
 }
 static void enqueue(Context c,List<TransferEngine.Job> jobs)throws Exception{
  synchronized(QUEUE_LOCK){TransferStore s=store(c);if(s.list().size()+jobs.size()>32)throw new Exception("本机最多保留 32 个任务，请先清理已结束任务");List<TransferEngine.Job> saved=new ArrayList<>();try{for(TransferEngine.Job j:jobs){j.status="paused";j.message="等待后台传输";s.save(j);saved.add(j);}}catch(Exception error){for(TransferEngine.Job j:saved)try{remove(c,j);}catch(Exception ignored){}throw error;}}
  for(TransferEngine.Job j:jobs)try{command(c,j.id,"resume");}catch(Exception e){j.status="paused";j.message=e.getMessage();store(c).save(j);emit(c,j);}
 }
 static void command(Context c,String id,String action)throws Exception{
  TransferEngine.Job j=store(c).get(id);if(!TransferBinding.capture(c).owns(j))throw new Exception("这个任务不属于当前服务器");
  if(!Arrays.asList("pause","resume","cancel").contains(action))throw new Exception("无效传输操作");
  if("cancel".equals(action)&&"completed".equals(j.status)){remove(c,j);signals.remove(id);j.status="cancelled";j.message="已移除完成记录";emit(c,j);return;}
  if("cancel".equals(action)&&"upload".equals(j.kind)&&!j.sha256.isEmpty()&&!"completed".equals(j.status))throw new Exception("上传发布可能已经提交，请继续原任务核实结果，不能取消发布");
  if("resume".equals(action)){if("completed".equals(j.status))throw new Exception("任务已完成");TransferBinding.resolve(c,j);signals.remove(id);if(activeJob==null||!activeJob.id.equals(id)){j.status="queued";j.message="等待后台传输";store(c).save(j);}requested.add(id);Intent intent=new Intent(c,TransferService.class).setAction("resume").putExtra("job",id);try{c.startForegroundService(intent);}catch(Exception e){requested.remove(id);j.status="paused";j.message="无法启动后台传输，请保持 App 在前台并重试";store(c).save(j);throw new Exception(j.message);}return;}
  signals.put(id,"cancel".equals(action)?"cancelled":"paused");
  if(activeJob==null||!activeJob.id.equals(id)){if("cancel".equals(action)){remove(c,j);if(!requested.contains(id))signals.remove(id);j.status="cancelled";j.message="本机任务已移除；未完成的服务器暂存会到期清理";}else{j.status="paused";j.message="已暂停，可稍后继续";store(c).save(j);}}
  emit(c,j);
 }
 private static JSONObject json(TransferEngine.Job j)throws Exception{return new JSONObject().put("id",j.id).put("name",j.name).put("root",j.root).put("kind",j.kind).put("bytes",j.size).put("offset",j.offset).put("state",j.status).put("message",j.message).put("percent",j.size==0?("completed".equals(j.status)?100:0):(int)Math.min(100,j.offset*100/j.size));}
 private static void emit(Context c,TransferEngine.Job j){try{TransferBinding current=TransferBinding.capture(c);if(!current.owns(j))return;Listener l=listener.get();if(l!=null)l.progress(json(j).put("profile",j.profile).put("server",j.server));}catch(Exception ignored){}}
 private static void release(Context c,TransferEngine.Job j){if(j.grantUri.isEmpty())return;try{for(TransferEngine.Job other:store(c).list())if(!other.id.equals(j.id)&&other.grantUri.equals(j.grantUri)&&!"completed".equals(other.status))return;for(UriPermission permission:c.getContentResolver().getPersistedUriPermissions())if(permission.getUri().toString().equals(j.grantUri)){int flags=(permission.isReadPermission()?Intent.FLAG_GRANT_READ_URI_PERMISSION:0)|(permission.isWritePermission()?Intent.FLAG_GRANT_WRITE_URI_PERMISSION:0);c.getContentResolver().releasePersistableUriPermission(permission.getUri(),flags);}}catch(Exception ignored){}}
 static void releaseUnused(Context c,String uri){try{for(TransferEngine.Job job:store(c).list())if(job.grantUri.equals(uri)&&!"completed".equals(job.status))return;TransferEngine.Job unused=new TransferEngine.Job(UUID.randomUUID().toString(),"upload",0);unused.grantUri=uri;release(c,unused);}catch(Exception ignored){}}
 private static void remove(Context c,TransferEngine.Job j)throws Exception{store(c).remove(j);release(c,j);}
 @Override public void onCreate(){super.onCreate();manager=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);manager.createNotificationChannel(new NotificationChannel("file-transfers","文件传输",NotificationManager.IMPORTANCE_LOW));executor=Executors.newSingleThreadExecutor();try{store(this).recover();}catch(Exception ignored){}}
 private Notification notification(String message){
  PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
  PendingIntent pause=PendingIntent.getService(this,2,new Intent(this,TransferService.class).setAction("pause-all"),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
  return new Notification.Builder(this,"file-transfers").setSmallIcon(android.R.drawable.stat_sys_upload).setContentTitle("文件传输").setContentText(message).setContentIntent(open).setOnlyAlertOnce(true).setOngoing(true).addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause,"暂停全部",pause).build()).build();
 }
 @Override public int onStartCommand(Intent intent,int flags,int startId){
  latestStart=startId;
  if(Build.VERSION.SDK_INT>=29)startForeground(NOTIFICATION,notification("正在处理传输队列"),ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);else startForeground(NOTIFICATION,notification("正在处理传输队列"));running=true;
  if(intent==null){stopSelf();return START_NOT_STICKY;}
  if("pause-all".equals(intent.getAction())){try{for(TransferEngine.Job j:store(this).list()){if(!Arrays.asList("queued","running","verifying","saving").contains(j.status))continue;signals.put(j.id,"paused");if(activeJob==null||!activeJob.id.equals(j.id)){if("queued".equals(j.status)){j.status="paused";j.message="已暂停";store(this).save(j);}}}}catch(Exception ignored){}if(activeJob==null)stopSelf();return START_NOT_STICKY;}
  final String id=intent.getStringExtra("job");
  if(id==null){stopSelf();return START_NOT_STICKY;}if(!scheduled.add(id))return START_NOT_STICKY;
  pending.incrementAndGet();executor.execute(()->{boolean locked=false;try{
   WORK_LOCK.lockInterruptibly();locked=true;TransferEngine.Job j=store(this).get(id);if(destroyed||signals.containsKey(id))return;run(j);
  }catch(Exception e){try{TransferEngine.Job j=store(this).get(id);j.status="failed";j.message="已暂停："+(e.getMessage()==null?"请检查连接":e.getMessage());store(this).save(j);emit(this,j);}catch(Exception ignored){}}finally{if(locked)WORK_LOCK.unlock();signals.remove(id);requested.remove(id);scheduled.remove(id);if(pending.decrementAndGet()==0)new Handler(getMainLooper()).post(()->{if(pending.get()==0)stopSelfResult(latestStart);});}});
  return START_NOT_STICKY;
 }
 private void run(TransferEngine.Job j)throws Exception{
  final TransferStore journal=store(this);final TransferBinding binding=TransferBinding.resolve(this,j);final Remote remote=new Remote(binding);activeJob=j;
  try{TransferEngine.run(j,remote,new TransferEngine.Host(){
   public InputStream source(TransferEngine.Job job)throws Exception{return getContentResolver().openInputStream(Uri.parse(job.uri));}
   public File stage(TransferEngine.Job job)throws Exception{File stage=journal.stage(job);if(stage.getParentFile().getUsableSpace()<Math.max(0,job.size-stage.length())+RESERVE)throw new IOException("手机空间不足，传输已暂停并保留进度");return stage;}
   public void save(TransferEngine.Job job)throws Exception{journal.save(job);emit(TransferService.this,job);int percent=job.size==0?0:(int)(job.offset*100/job.size);manager.notify(NOTIFICATION,notification(("upload".equals(job.kind)?"上传":"下载")+" · "+percent+"% · "+job.name));}
   public void check(TransferEngine.Job job)throws Exception{if(destroyed||Thread.currentThread().isInterrupted()||signals.containsKey(job.id))throw new InterruptedException("已暂停");binding.check(TransferService.this,job);}
   public void publish(TransferEngine.Job job,File file)throws Exception{
    try(InputStream in=new FileInputStream(file);OutputStream out=getContentResolver().openOutputStream(Uri.parse(job.uri),"wt")){if(out==null)throw new IOException("无法写入所选手机位置，请重新授权");byte[] buffer=new byte[TransferEngine.CHUNK];int count;while((count=in.read(buffer))!=-1){check(job);out.write(buffer,0,count);}out.flush();}
   }
  });if("completed".equals(j.status)){if("download".equals(j.kind))java.nio.file.Files.deleteIfExists(journal.stage(j).toPath());release(this,j);}}
  catch(Exception e){String signal=signals.get(j.id);if("cancelled".equals(signal)){if(!j.uploadId.isEmpty()&&j.sha256.isEmpty())try{remote.abort(j);}catch(Exception ignored){}remove(this,j);j.status="cancelled";j.message="已取消；未完成的手机目标文件可能需要手动清理";}else{j.status=e instanceof InterruptedException?"paused":"failed";j.message=e instanceof InterruptedException?"已暂停，可继续原任务":"已暂停："+(e.getMessage()==null?"连接失败，请稍后继续":e.getMessage());journal.save(j);}emit(this,j);}
  finally{signals.remove(j.id);activeJob=null;}
 }
 private final class Remote implements TransferEngine.Remote {
  final TransferBinding binding;Remote(TransferBinding binding){this.binding=binding;}
  JSONObject api(TransferEngine.Job j,String path,JSONObject body)throws Exception{binding.check(TransferService.this,j);if(signals.containsKey(j.id)||destroyed)throw new InterruptedException("已暂停");if(!"default".equals(j.root))body.put("root",j.root);return new JSONObject(StatusClient.request(binding.snapshot,"POST",path,body.toString()));}
  public TransferEngine.Upload start(TransferEngine.Job j)throws Exception{JSONObject r=api(j,"/api/files/upload/start",new JSONObject().put("directory",j.directory).put("name",j.name).put("size",j.size).put("request",j.startRequest));return new TransferEngine.Upload(r.getString("id"),r.getLong("offset"),j.size);}
  public TransferEngine.Upload status(TransferEngine.Job j)throws Exception{JSONObject r=api(j,"/api/files/upload/status",new JSONObject().put("id",j.uploadId));return new TransferEngine.Upload(r.getString("id"),r.getLong("offset"),r.getLong("size"));}
  public long append(TransferEngine.Job j,long offset,byte[] data,int count)throws Exception{return api(j,"/api/files/upload/chunk",new JSONObject().put("id",j.uploadId).put("offset",offset).put("data",Base64.encodeToString(data,0,count,Base64.NO_WRAP))).getLong("offset");}
  public String finish(TransferEngine.Job j)throws Exception{return api(j,"/api/files/upload/finish",new JSONObject().put("id",j.uploadId).put("sha256",j.sha256).put("request",j.finishRequest)).getString("id");}
  public TransferEngine.Action action(TransferEngine.Job j)throws Exception{binding.check(TransferService.this,j);JSONObject r=new JSONObject(StatusClient.request(binding.snapshot,"GET","/api/actions/"+j.actionId,""));return new TransferEngine.Action(r.getString("state"),r.optString("message",""));}
  public TransferEngine.Stat stat(TransferEngine.Job j)throws Exception{JSONObject r=api(j,"/api/files/stat",new JSONObject().put("path",j.path));if(!"file".equals(r.getString("kind")))throw new IOException("只支持下载普通文件");return new TransferEngine.Stat(r.getLong("bytes"),r.getString("ticket"));}
  public TransferEngine.Chunk read(TransferEngine.Job j,long offset)throws Exception{JSONObject r=api(j,"/api/files/read",new JSONObject().put("path",j.path).put("ticket",j.ticket).put("offset",offset));String data=r.getString("data");if(data.length()>TransferEngine.CHUNK*4/3+8)throw new IOException("下载数据块过大");return new TransferEngine.Chunk(r.getLong("offset"),r.getLong("size"),Base64.decode(data,Base64.DEFAULT),r.getBoolean("eof"));}
  void abort(TransferEngine.Job j)throws Exception{binding.check(TransferService.this,j);StatusClient.request(binding.snapshot,"POST","/api/files/upload/abort",new JSONObject().put("root",j.root).put("id",j.uploadId).toString());}
 }
 @Override public void onTimeout(int startId,int fgsType){destroyed=true;TransferEngine.Job j=activeJob;if(j!=null){signals.put(j.id,"paused");try{j.status="paused";j.message="系统后台传输时限已到，请打开 App 后继续";store(this).save(j);}catch(Exception ignored){}}stopSelf();}
 @Override public void onDestroy(){destroyed=true;running=false;if(activeJob!=null)signals.put(activeJob.id,"paused");if(executor!=null)executor.shutdownNow();for(String id:scheduled){requested.remove(id);if(activeJob!=null&&activeJob.id.equals(id))continue;try{TransferEngine.Job j=store(this).get(id);j.status="paused";j.message="后台传输已停止，请打开 App 后继续";store(this).save(j);emit(this,j);}catch(Exception ignored){}signals.remove(id);}stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();}
 @Override public IBinder onBind(Intent intent){return null;}
}
