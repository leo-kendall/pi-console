// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;

/** User-started monitoring of the network-connected Raspberry Pi. */
public final class AlertMonitorService extends Service {
 static volatile boolean running;
 private ScheduledExecutorService executor;
 private NotificationManager manager;
 private int failures=0;
 private boolean offline=false;
 private volatile boolean stopped=false;
 private static final int STATUS=4100;
 static JSONObject state(Context c)throws Exception {
  NotificationManager nm=(NotificationManager)c.getSystemService(NOTIFICATION_SERVICE);NotificationChannel alerts=nm.getNotificationChannel("pi-alerts");
  return new JSONObject().put("available",true).put("running",running).put("requested",c.getSharedPreferences("monitor",0).getBoolean("enabled",false)).put("notifications",nm.areNotificationsEnabled()&&(alerts==null||alerts.getImportance()!=NotificationManager.IMPORTANCE_NONE));
 }
 static void stop(Context c){c.getSharedPreferences("monitor",0).edit().putBoolean("enabled",false).apply();c.stopService(new Intent(c,AlertMonitorService.class));}
 @Override public void onCreate(){super.onCreate();manager=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
  manager.createNotificationChannel(new NotificationChannel("monitor-status","服务器持续监控",NotificationManager.IMPORTANCE_LOW));
  manager.createNotificationChannel(new NotificationChannel("pi-alerts","服务器异常提醒",NotificationManager.IMPORTANCE_DEFAULT));
 }
 private PendingIntent open(){return PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
 private Notification status(String text){
  PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,AlertMonitorService.class).setAction("stop"),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
  return new Notification.Builder(this,"monitor-status").setSmallIcon(android.R.drawable.ic_menu_info_details).setContentTitle("正在监控服务器").setContentText(text).setContentIntent(open()).setOngoing(true).setOnlyAlertOnce(true).addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause,"停止监控",stop).build()).build();
 }
 @Override public int onStartCommand(Intent intent,int flags,int startId){
  if(intent!=null&&"stop".equals(intent.getAction())){getSharedPreferences("monitor",0).edit().putBoolean("enabled",false).apply();stopSelf();return START_NOT_STICKY;}
  if(!getSharedPreferences("monitor",0).getBoolean("enabled",false)){stopSelf();return START_NOT_STICKY;}
  if(Build.VERSION.SDK_INT>=29)startForeground(STATUS,status("每分钟检查 · 使用已配置的服务器地址"),ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);else startForeground(STATUS,status("每分钟检查 · 使用已配置的服务器地址"));
  running=true;
  if(executor==null){executor=Executors.newSingleThreadScheduledExecutor();executor.scheduleWithFixedDelay(this::poll,0,60,TimeUnit.SECONDS);}
  return START_NOT_STICKY;
 }
 private void notifyAlert(int id,String title,String message){if(stopped)return;manager.notify(id,new Notification.Builder(this,"pi-alerts").setSmallIcon(android.R.drawable.ic_dialog_alert).setContentTitle(title).setContentText(message).setStyle(new Notification.BigTextStyle().bigText(message)).setContentIntent(open()).setAutoCancel(true).build());}
 private void poll(){
  try{
   String token=SecretStore.read(this);if(token.isEmpty()){new Handler(getMainLooper()).post(()->AlertMonitorService.stop(this));return;}
   JSONObject data=new JSONObject(StatusClient.request(this,"GET","/api/alerts",""));if(stopped)return;
   if(AlertDelivery.stale(data.optDouble("sampled_at",Double.NaN),System.currentTimeMillis()/1000.0))throw new java.io.IOException("监控采样已过期");
   if(offline)notifyAlert(4200,"服务器监控已恢复","已重新连接，异常监控继续运行");offline=false;failures=0;
   android.content.SharedPreferences prefs=getSharedPreferences("monitor",0);
   Set<String> seen=new HashSet<>(prefs.getStringSet("seen",Collections.emptySet()));
   JSONArray events=data.getJSONArray("events"),active=data.getJSONArray("active");List<String> historyIds=new ArrayList<>(),activeIds=new ArrayList<>();Map<String,JSONObject> byId=new LinkedHashMap<>();
   for(int i=0;i<events.length();i++){JSONObject e=events.getJSONObject(i);String id=e.getString("id");historyIds.add(id);byId.put(id,e);}
   for(int i=0;i<active.length();i++){JSONObject e=active.getJSONObject(i);String id=e.getString("id");activeIds.add(id);byId.put(id,e);}
   Set<String> retained=AlertDelivery.candidates(historyIds,activeIds);long since=prefs.getLong("started",System.currentTimeMillis())/1000-120;
   for(String id:AlertDelivery.unseen(retained,seen)){
    JSONObject e=byId.get(id);
    if(e.getLong("time")>=since||activeIds.contains(id))notifyAlert(4300+Math.floorMod(e.getString("key").hashCode(),100000),e.getString("title"),e.getString("message"));
   }
   prefs.edit().putStringSet("seen",new HashSet<>(retained)).apply();
   if(!stopped)manager.notify(STATUS,status("连接正常 · "+active.length()+" 项当前异常 · 每分钟检查"));
  }catch(Exception e){if(stopped)return;
   failures++;
   if(e.getMessage()!=null&&e.getMessage().contains("配对")){notifyAlert(4201,"配对已失效","请打开控制台重新配对，再开启监控");new Handler(getMainLooper()).post(()->AlertMonitorService.stop(this));return;}
   if(failures>=3&&!offline){offline=true;boolean stale=e.getMessage()!=null&&e.getMessage().contains("采样");notifyAlert(4200,stale?"服务器监控数据已过期":"服务器暂时无法连接",stale?"服务器可连接，但监控采样未更新。请检查控制台服务。":"连续三次连接失败；请检查手机网络、服务器地址和后端运行状态。");}
   if(!stopped)manager.notify(STATUS,status("暂时无法连接 · 已连续失败 "+failures+" 次"));
  }
 }
 @Override public void onDestroy(){stopped=true;running=false;if(executor!=null)executor.shutdownNow();stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();}
 @Override public android.os.IBinder onBind(Intent intent){return null;}
}
