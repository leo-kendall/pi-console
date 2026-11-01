// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.*;
import android.view.View;
import android.content.Intent;
import android.net.Uri;
import android.content.res.Configuration;
import org.json.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
 private WebView web;
 private FileTransfer files;
 private BackupTransfer backup;
 private TextExport textExport;
 private DesktopInput desktopInput;
 private boolean desktopFullscreen=false;
 private final ExecutorService pool=Executors.newFixedThreadPool(4);
 private final java.util.concurrent.atomic.AtomicInteger pending=new java.util.concurrent.atomic.AtomicInteger();
 private final String origin="https://pi-console.local/";
 @Override public void onCreate(Bundle state){
  super.onCreate(state);
  boolean dark=(getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
  int bg=android.graphics.Color.parseColor(dark?"#101114":"#F3F4F7");
  getWindow().setStatusBarColor(bg);getWindow().setNavigationBarColor(bg);
  getWindow().getDecorView().setSystemUiVisibility(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
  web=new WebView(this);web.setBackgroundColor(bg);
  getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
  web.setOnApplyWindowInsetsListener((v,insets)->{
   int left=0,right=0,top=desktopFullscreen?0:insets.getSystemWindowInsetTop(),bottom=desktopFullscreen?0:insets.getSystemWindowInsetBottom();
   if(Build.VERSION.SDK_INT>=28 && insets.getDisplayCutout()!=null){android.view.DisplayCutout cutout=insets.getDisplayCutout();left=cutout.getSafeInsetLeft();right=cutout.getSafeInsetRight();if(desktopFullscreen){top=cutout.getSafeInsetTop();bottom=cutout.getSafeInsetBottom();}}
   v.setPadding(left,top,right,bottom);return insets;
  });
  setContentView(web);files=new FileTransfer(this);backup=new BackupTransfer(this);textExport=new TextExport(this);desktopInput=new DesktopInput(this,web);
  WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setAllowFileAccess(false);s.setAllowContentAccess(false);
  s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);s.setTextZoom(Math.round(100*getResources().getConfiguration().fontScale));
  web.addJavascriptInterface(new Bridge(),"Pi");
  web.setWebViewClient(new WebViewClient(){
   @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return true;}
   @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){
    String url=r.getUrl().toString();
    if(!url.startsWith(origin))return blocked();
    String name=url.substring(origin.length());
    if(!Arrays.asList("index.html","style.css","app.js","app-state.js","setup-ui.js","resources-ui.js","process-ui.js","tools-ui.js","files-ui.js","guacamole.js","desktop-layout.js","desktop-diagnostics.js","desktop-ui.js","profiles-ui.js","updates-ui.js","admin-ui.js","observability-ui.js","observability.css","files-ui.css").contains(name))return blocked();
    try {
     String mime=name.endsWith(".html")?"text/html":name.endsWith(".css")?"text/css":"application/javascript";
     Map<String,String> headers=new HashMap<>();headers.put("Content-Security-Policy","default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src data: blob:; media-src data: blob:; connect-src 'none'; base-uri 'none'; frame-src 'none'; form-action 'none'");
     return new WebResourceResponse(mime,"UTF-8",200,"OK",headers,getAssets().open(name));
    }catch(Exception e){return blocked();}
   }
   @Override public void onPageFinished(WebView v,String url){if(getResources().getConfiguration().fontScale>1.3f)v.evaluateJavascript("document.body.classList.add('large-text')",null);notifyOrientation();v.evaluateJavascript("window.resumeApp&&resumeApp()",null);}
  });
  web.loadUrl(origin+"index.html");
 }
 private void notifyOrientation(){if(web!=null)web.evaluateJavascript("window.setDeviceLandscape&&setDeviceLandscape("+(getResources().getConfiguration().orientation==Configuration.ORIENTATION_LANDSCAPE)+")",null);}
 private void setDesktopFullscreen(boolean enabled){
  desktopFullscreen=enabled;
  View decor=getWindow().getDecorView();
  if(Build.VERSION.SDK_INT>=30){
   WindowInsetsController controller=getWindow().getInsetsController();
   if(controller!=null){if(enabled){controller.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);controller.hide(WindowInsets.Type.systemBars());}else controller.show(WindowInsets.Type.systemBars());}
  }else{
   boolean dark=(getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
   decor.setSystemUiVisibility(enabled?View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|View.SYSTEM_UI_FLAG_LAYOUT_STABLE:(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR));
  }
  if(enabled)getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
  if(web!=null)web.requestApplyInsets();
 }
 @Override public void onConfigurationChanged(Configuration configuration){super.onConfigurationChanged(configuration);notifyOrientation();if(web!=null)web.getSettings().setTextZoom(Math.round(100*configuration.fontScale));setDesktopFullscreen(desktopFullscreen);}
 @Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(desktopInput!=null)desktopInput.focusChanged(focused);if(focused&&desktopFullscreen)setDesktopFullscreen(true);}
 @Override public boolean dispatchKeyEvent(android.view.KeyEvent event){return desktopInput!=null&&desktopInput.key(event)||super.dispatchKeyEvent(event);}
 private WebResourceResponse blocked(){return new WebResourceResponse("text/plain","UTF-8",403,"Forbidden",Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));}
 private void result(String id,JSONObject value,String error){runOnUiThread(()->{if(!isDestroyed())web.evaluateJavascript("window.nativeResult("+JSONObject.quote(id)+","+(value==null?"null":value.toString())+","+(error==null?"null":JSONObject.quote(error))+")",null);});}
 final class Bridge {
  @JavascriptInterface public void request(String id,String method,String path,String body){
   if(!id.matches("[0-9]{1,12}")||!(method.equals("GET")||method.equals("POST"))||!path.matches("/api/[a-zA-Z0-9/?=&-]{1,160}")||body.length()>262144){result(id,null,"无效请求");return;}
   if(path.equals("/api/unpair")&&(files.busy()||backup.busy())){result(id,null,"请先暂停文件传输并完成文件选择或备份，再撤销配对");return;}
   if(pending.incrementAndGet()>12){pending.decrementAndGet();result(id,null,"请求过多，请稍候");return;}
   final ServerSettings.Snapshot session;
   try{session=ServerSettings.snapshot(MainActivity.this);}catch(Exception e){pending.decrementAndGet();result(id,null,e.getMessage());return;}
   pool.execute(()->{try{
    JSONObject response=new JSONObject(StatusClient.request(session,method,path,body));
    if(!ServerSettings.current(MainActivity.this,session))throw new Exception("服务器已切换，请重新操作");
    if(path.equals("/api/pair")){ServerSettings.pair(MainActivity.this,session,response.getString("token"));response=new JSONObject().put("paired",true);}
    if(path.equals("/api/unpair")){AlertMonitorService.stop(MainActivity.this);ServerSettings.forget(MainActivity.this,session);}
    result(id,response,null);
   }catch(Exception e){result(id,null,Arrays.asList("/api/status","/api/setup","/api/pair").contains(path)?ProbeRules.apiError(e):e.getMessage()==null?"连接失败，请检查网络和服务器地址":e.getMessage());}finally{pending.decrementAndGet();}});
  }
  @JavascriptInterface public void local(String id,String action,String value){
   if(!id.matches("[0-9]{1,12}")||action.length()>64||value.length()>524288){result(id,null,"无效本机请求");return;}
   if(action.equals("installUpdate")){pool.execute(()->{try{UpdateManager.install(MainActivity.this);result(id,new JSONObject().put("installer",true),null);}catch(Exception e){result(id,null,e.getMessage());}});return;}
   if(action.equals("checkUpdate")||action.equals("profileStatus")){
    pool.execute(()->{try{result(id,action.equals("checkUpdate")?UpdateManager.check(MainActivity.this,value.equals("prerelease")):ProfileBridge.status(MainActivity.this,value),null);}catch(Exception e){result(id,null,e.getMessage());}});return;
   }
   if(action.equals("probeServer")){
    if(!id.matches("[0-9]{1,12}")||value.length()>2048){result(id,null,"无效检测请求");return;}
    if(pending.incrementAndGet()>12){pending.decrementAndGet();result(id,null,"请求过多，请稍候");return;}
    pool.execute(()->{try{result(id,ConnectionProbe.run(value),null);}catch(Exception e){result(id,null,"检测未完成，请稍后重试");}finally{pending.decrementAndGet();}});return;
   }
   runOnUiThread(()->{try{
    JSONObject out=new JSONObject();AppStore store=new AppStore(MainActivity.this);
    if(action.equals("licenses")){
     StringBuilder text=new StringBuilder();
     for(String file:new String[]{"NOTICE.txt","LICENSE.txt"})try(InputStream input=getAssets().open(file);ByteArrayOutputStream bytes=new ByteArrayOutputStream()){
      byte[] buffer=new byte[4096];int count;while((count=input.read(buffer))!=-1){if(bytes.size()+count>65536)throw new Exception("许可文件过大");bytes.write(buffer,0,count);}text.append(bytes.toString("UTF-8")).append("\n\n");
     }
     out.put("text",text.toString());result(id,out,null);return;
    }
    if(action.equals("profiles"))out=ProfileBridge.list(MainActivity.this);
    else if(action.equals("addProfile")){JSONObject p=new JSONObject(value);out.put("id",ServerSettings.add(MainActivity.this,p.getString("name"),p.getString("url")));}
    else if(action.equals("renameProfile")){JSONObject p=new JSONObject(value);ServerSettings.rename(MainActivity.this,p.getString("id"),p.getString("name"));out.put("ok",true);}
    else if(action.equals("switchProfile")||action.equals("removeProfile")){
     if(files.busy()||backup.busy())throw new Exception("请等待文件选择、传输或备份任务结束");
     if(action.equals("removeProfile"))TransferService.discardProfile(MainActivity.this,value);
     AlertMonitorService.stop(MainActivity.this);desktopInput.setShortcutSession("");desktopInput.setSession("");
     if(action.equals("switchProfile"))ServerSettings.activate(MainActivity.this,value);else ServerSettings.remove(MainActivity.this,value);
     out=ProfileBridge.list(MainActivity.this);
    }
    else if(action.equals("profileSettings"))out=ProfileBridge.settings(MainActivity.this,null);
    else if(action.equals("saveProfileSettings"))out=ProfileBridge.settings(MainActivity.this,new JSONObject(value));
    else if(action.equals("updateState"))out=UpdateManager.state(MainActivity.this);
    else if(action.equals("downloadUpdate")){UpdateManager.download(MainActivity.this,value);out.put("started",true);}
    else if(action.equals("logsExport")){JSONObject p=new JSONObject(value);textExport.start(p.getString("name"),p.getString("text"));out.put("started",true);}
    else if(action.equals("logsCopy")){String text=new JSONObject(value).getString("text");TextExport.validate("logs.txt",text);android.content.ClipboardManager cm=(android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE);cm.setPrimaryClip(android.content.ClipData.newPlainText("服务器日志",text));out.put("ok",true);}
    else if(action.equals("notificationSettings"))out=NotificationSettings.access(MainActivity.this,value);
    else if(action.equals("serverSettings")){out.put("url",ServerSettings.url(MainActivity.this));out.put("paired",ServerSettings.paired(MainActivity.this));out.put("profile",ServerSettings.activeId(MainActivity.this));}
    else if(action.equals("saveServer")){if(pending.get()>0||files.busy()||backup.busy())throw new Exception("请等待当前请求或文件操作结束");if(!ServerSettings.activeId(MainActivity.this).isEmpty()&&!ServerEndpoint.parse(value).canonical.equals(ServerSettings.url(MainActivity.this)))TransferService.store(MainActivity.this).requireProfileEmpty(ServerSettings.activeId(MainActivity.this));ServerSettings.set(MainActivity.this,value);out.put("url",ServerSettings.url(MainActivity.this));}
    else if(action.equals("paired"))out.put("paired",ServerSettings.paired(MainActivity.this));
    else if(action.equals("desktopProbe")){DesktopProbe.capture(MainActivity.this,web,new JSONObject(value),data->result(id,data,null));return;}
    else if(action.equals("desktopRepaint")){web.requestLayout();web.postInvalidateOnAnimation();out.put("ok",true);}
    else if(action.equals("copyDesktopReport")){
     if(value.length()>32768)throw new Exception("诊断记录过大");
     android.content.ClipboardManager clipboard=(android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE);
     clipboard.setPrimaryClip(android.content.ClipData.newPlainText("桌面显示诊断",value));out.put("ok",true);
    }
    else if(action.equals("desktopRendering")){
     if(!value.equals("software")&&!value.equals("default"))throw new Exception("无效显示模式");
     // Some Android GPUs clip large scaled canvas layers after rotation.
     // Restrict software rendering to the active desktop; restore normal
     // compositing as soon as that session is closed.
     web.setLayerType(value.equals("software")?View.LAYER_TYPE_SOFTWARE:View.LAYER_TYPE_NONE,null);
     web.invalidate();out.put("ok",true);
    }
    else if(action.equals("desktopInput")){if(value.length()>128)throw new Exception("桌面会话无效");desktopInput.setSession(value);out.put("ok",true);}
    else if(action.equals("desktopInputShortcut")){desktopInput.setShortcutSession(value);out.put("ok",true);}
    else if(action.equals("desktopInputRegion")){desktopInput.setRegion(new JSONObject(value));out.put("ok",true);}
    else if(action.equals("desktopClipboardRead"))out=desktopInput.readClipboard();
    else if(action.equals("desktopClipboardWrite"))out=desktopInput.writeClipboard(value);
    else if(action.equals("desktopFullscreen")){if(!value.equals("true")&&!value.equals("false"))throw new Exception("无效全屏参数");setDesktopFullscreen(value.equals("true"));out.put("ok",true);}
    else if(action.equals("fileUpload")){if(backup.busy())throw new Exception("已有备份任务进行中");files.upload(new JSONObject(value));out.put("started",true);}
    else if(action.equals("fileDownload")){if(backup.busy())throw new Exception("已有备份任务进行中");files.download(new JSONObject(value));out.put("started",true);}
    else if(action.equals("backupExport")){if(files.state().getBoolean("busy"))throw new Exception("已有文件任务进行中");backup.exportSettings(new JSONObject(value));out.put("started",true);}
    else if(action.equals("backupImport")){if(files.state().getBoolean("busy"))throw new Exception("已有文件任务进行中");backup.importSettings();out.put("started",true);}
    else if(action.equals("backupApply")){backup.apply();out.put("started",true);}
    else if(action.equals("transferState"))out=files.state();
    else if(action.equals("transferPause")||action.equals("transferResume")||action.equals("transferCancel")||action.equals("transferDiscard")){JSONObject command=new JSONObject(value);if(command.length()!=1||!command.has("id"))throw new Exception("无效传输操作");files.command(command.getString("id"),action.substring(8).toLowerCase(java.util.Locale.ROOT));out.put("ok",true);}
    else if(action.equals("monitorState"))out=AlertMonitorService.state(MainActivity.this);
    else if(action.equals("monitorStop")){AlertMonitorService.stop(MainActivity.this);out=AlertMonitorService.state(MainActivity.this);}
    else if(action.equals("monitorStart")){
     if(!ServerSettings.paired(MainActivity.this))throw new Exception("请先配对设备");
     if(Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},30);throw new Exception("请允许通知后，再点击开启监控");}
     if(!AlertMonitorService.state(MainActivity.this).getBoolean("notifications"))throw new Exception("请先在系统设置中允许本 App 的通知");
     getSharedPreferences("monitor",0).edit().putBoolean("enabled",true).putLong("started",System.currentTimeMillis()).apply();startForegroundService(new Intent(MainActivity.this,AlertMonitorService.class));out.put("starting",true);
    }
    else if(action.equals("exit")){finish();out.put("ok",true);}
    else if(action.equals("forget")){if(files.busy()||backup.busy())throw new Exception("请先暂停文件传输并完成文件选择或备份，再移除配对");AlertMonitorService.stop(MainActivity.this);ServerSettings.forget(MainActivity.this);out.put("ok",true);}
    else if(action.equals("apps")){
     JSONArray a=new JSONArray();for(AppStore.Entry e:store.load())a.put(new JSONObject().put("name",e.name).put("url",e.url).put("inline",e.inline));out.put("apps",a);
    }else if(action.equals("saveApps")){
     JSONArray a=new JSONArray(value);if(a.length()>40)throw new Exception("最多40个入口");List<AppStore.Entry> list=new ArrayList<>();
     for(int i=0;i<a.length();i++){JSONObject e=a.getJSONObject(i);String name=e.getString("name");if(name.isEmpty()||name.length()>64)throw new Exception("名称长度无效");list.add(new AppStore.Entry(name,UrlRules.validate(e.getString("url")),e.optBoolean("inline")));}store.save(list);out.put("ok",true);
    }else if(action.equals("openApp")){
     JSONObject e=new JSONObject(value);String url=UrlRules.validate(e.getString("url"));Intent intent=e.optBoolean("inline")?new Intent(MainActivity.this,WebActivity.class).putExtra("url",url):new Intent(Intent.ACTION_VIEW,Uri.parse(url));startActivity(intent);out.put("ok",true);
    }else throw new Exception("未知操作");result(id,out,null);
   }catch(Exception e){result(id,null,e.getMessage());}});
  }
 }
 @Override protected void onPause(){if(desktopInput!=null){desktopInput.setShortcutSession("");desktopInput.setSession("");}setDesktopFullscreen(false);if(web!=null)web.evaluateJavascript("window.pauseApp&&pauseApp()",null);super.onPause();}
 @Override protected void onResume(){super.onResume();if(web!=null)web.evaluateJavascript("window.resumeApp&&resumeApp()",null);}
 void backupEvent(String type,JSONObject event){runOnUiThread(()->{if(!isDestroyed())web.evaluateJavascript("window.backupEvent&&backupEvent("+JSONObject.quote(type)+","+event.toString()+")",null);});}
 void fileProgress(JSONObject progress){runOnUiThread(()->{if(!isDestroyed())web.evaluateJavascript("window.fileTransferProgress&&fileTransferProgress("+progress.toString()+")",null);});}
 @Override protected void onActivityResult(int request,int code,Intent data){super.onActivityResult(request,code,data);if(files!=null)files.result(request,code,data);if(backup!=null)backup.result(request,code,data);if(textExport!=null)textExport.result(request,code,data);}
 @Override public void onBackPressed(){web.evaluateJavascript("window.appBack&&appBack()",null);}
 @Override protected void onDestroy(){if(files!=null)files.close();if(backup!=null)backup.close();if(textExport!=null)textExport.close();pool.shutdown();if(web!=null){web.removeJavascriptInterface("Pi");web.destroy();}super.onDestroy();}
}
