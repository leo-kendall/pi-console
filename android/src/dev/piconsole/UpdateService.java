// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.*;import android.content.*;import android.content.pm.ServiceInfo;import android.os.*;import org.json.*;import java.io.*;import java.util.concurrent.atomic.AtomicBoolean;
/** Explicit user-initiated native background download; survives activity navigation. */
public final class UpdateService extends Service {
 static final AtomicBoolean running=new AtomicBoolean(false);private Thread worker;
 private void state(String state,String message){UpdateManager.prefs(this).edit().putString("state",state).putString("message",message).commit();}
 @Override public int onStartCommand(Intent intent,int flags,int startId){
  NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);nm.createNotificationChannel(new NotificationChannel("updates","应用更新下载",NotificationManager.IMPORTANCE_LOW));
  Notification note=new Notification.Builder(this,"updates").setSmallIcon(android.R.drawable.stat_sys_download).setContentTitle("正在下载 Pi Console 更新").setContentText("下载后验证 SHA256、包名与签名；安装需要你确认").setOngoing(true).build();
  if(Build.VERSION.SDK_INT>=29)startForeground(4500,note,ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);else startForeground(4500,note);
  if(!running.compareAndSet(false,true))return START_NOT_STICKY;
  final String raw=intent==null?"":intent.getStringExtra("candidate");state("downloading","正在下载并校验官方更新");
  worker=new Thread(()->{File partial=new File(getFilesDir(),"update.partial.apk");try{
   JSONObject selected=new JSONObject(raw);String sha;try(OutputStream out=new FileOutputStream(partial)){sha=new UpdateTransport().copy(selected.getString("url"),out,Math.min(UpdateRules.MAX_APK,selected.getLong("bytes")));}
   if(!sha.equals(selected.getString("sha256")))throw new IOException("更新 SHA256 校验失败");UpdateManager.validate(this,partial,selected);
   if(!partial.renameTo(UpdateManager.apk(this)))throw new IOException("无法保存已验证的更新");
   if(!UpdateManager.prefs(this).edit().putString("verified",selected.toString()).commit())throw new IOException("无法保存验证信息");state("ready","校验通过，可打开 Android 安装确认界面");
  }catch(Exception e){state("failed",e.getMessage()==null?"更新失败":e.getMessage());}finally{partial.delete();running.set(false);stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();}},"pi-console-update");worker.start();return START_NOT_STICKY;
 }
 @Override public void onTimeout(int startId,int fgsType){if(worker!=null)worker.interrupt();state("interrupted","后台下载已超时，请重试");stopSelf();}
 @Override public void onDestroy(){if(worker!=null)worker.interrupt();super.onDestroy();}
 @Override public IBinder onBind(Intent i){return null;}
}
