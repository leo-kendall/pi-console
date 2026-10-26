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
  setContentView(web);files=new FileTransfer(this);backup=new BackupTransfer(this);
  WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setAllowFileAccess(false);s.setAllowContentAccess(false);
  s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);s.setTextZoom(Math.round(100*getResources().getConfiguration().fontScale));
  web.addJavascriptInterface(new Bridge(),"Pi");
  web.setWebViewClient(new WebViewClient(){
   @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return true;}
   @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){
    String url=r.getUrl().toString();
    if(!url.startsWith(origin))return blocked();
    String name=url.substring(origin.length());
    if(!Arrays.asList("index.html","style.css","app.js","app-state.js","resources-ui.js","process-ui.js","tools-ui.js","files-ui.js","guacamole.js","desktop-layout.js","desktop-diagnostics.js","desktop-ui.js").contains(name))return blocked();
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
 @Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(focused&&desktopFullscreen)setDesktopFullscreen(true);}
 private WebResourceResponse blocked(){return new WebResourceResponse("text/plain","UTF-8",403,"Forbidden",Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));}
 private void result(String id,JSONObject value,String error){runOnUiThread(()->{if(!isDestroyed())web.evaluateJavascript("window.nativeResult("+JSONObject.quote(id)+","+(value==null?"null":value.toString())+","+(error==null?"null":JSONObject.quote(error))+")",null);});}
 final class Bridge {
  @JavascriptInterface public void request(String id,String method,String path,String body){
   if(!id.matches("[0-9]{1,12}")||!(method.equals("GET")||method.equals("POST"))||!path.matches("/api/[a-zA-Z0-9/?=&-]{1,160}")||body.length()>262144){result(id,null,"无效请求");return;}
   if(pending.incrementAndGet()>12){pending.decrementAndGet();result(id,null,"请求过多，请稍候");return;}
   pool.execute(()->{try{
    ServerSettings.Snapshot session=ServerSettings.snapshot(MainActivity.this);
    JSONObject response=new JSONObject(StatusClient.request(session,method,path,body));
    if(path.equals("/api/pair")){ServerSettings.pair(MainActivity.this,session,response.getString("token"));response=new JSONObject().put("paired",true);}
    if(path.equals("/api/unpair")){AlertMonitorService.stop(MainActivity.this);ServerSettings.forget(MainActivity.this);}
    result(id,response,null);
   }catch(Exception e){result(id,null,e.getMessage()==null?"连接失败，请检查网络和服务器地址":e.getMessage());}finally{pending.decrementAndGet();}});
  }
  @JavascriptInterface public void local(String id,String action,String value){
   runOnUiThread(()->{try{
    JSONObject out=new JSONObject();AppStore store=new AppStore(MainActivity.this);
    if(action.equals("licenses")){
     StringBuilder text=new StringBuilder();
     for(String file:new String[]{"NOTICE.txt","LICENSE.txt"})try(InputStream input=getAssets().open(file);ByteArrayOutputStream bytes=new ByteArrayOutputStream()){
      byte[] buffer=new byte[4096];int count;while((count=input.read(buffer))!=-1){if(bytes.size()+count>65536)throw new Exception("许可文件过大");bytes.write(buffer,0,count);}text.append(bytes.toString("UTF-8")).append("\n\n");
     }
     out.put("text",text.toString());result(id,out,null);return;
    }
    if(action.equals("serverSettings")){out.put("url",ServerSettings.url(MainActivity.this));out.put("paired",ServerSettings.paired(MainActivity.this));}
    else if(action.equals("saveServer")){if(pending.get()>0||files.busy()||backup.busy())throw new Exception("请等待当前请求或文件操作结束");ServerSettings.set(MainActivity.this,value);out.put("url",ServerSettings.url(MainActivity.this));}
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
    else if(action.equals("desktopFullscreen")){if(!value.equals("true")&&!value.equals("false"))throw new Exception("无效全屏参数");setDesktopFullscreen(value.equals("true"));out.put("ok",true);}
    else if(action.equals("fileUpload")){if(backup.busy())throw new Exception("已有备份任务进行中");files.upload(new JSONObject(value).getString("directory"));out.put("started",true);}
    else if(action.equals("fileDownload")){if(backup.busy())throw new Exception("已有备份任务进行中");files.download(new JSONObject(value));out.put("started",true);}
    else if(action.equals("backupExport")){if(files.state().getBoolean("busy"))throw new Exception("已有文件任务进行中");backup.exportSettings(new JSONObject(value));out.put("started",true);}
    else if(action.equals("backupImport")){if(files.state().getBoolean("busy"))throw new Exception("已有文件任务进行中");backup.importSettings();out.put("started",true);}
    else if(action.equals("backupApply")){backup.apply();out.put("started",true);}
    else if(action.equals("transferState"))out=files.state();
    else if(action.equals("monitorState"))out=AlertMonitorService.state(MainActivity.this);
    else if(action.equals("monitorStop")){AlertMonitorService.stop(MainActivity.this);out=AlertMonitorService.state(MainActivity.this);}
    else if(action.equals("monitorStart")){
     if(!ServerSettings.paired(MainActivity.this))throw new Exception("请先配对设备");
     if(Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},30);throw new Exception("请允许通知后，再点击开启监控");}
     if(!AlertMonitorService.state(MainActivity.this).getBoolean("notifications"))throw new Exception("请先在系统设置中允许本 App 的通知");
     getSharedPreferences("monitor",0).edit().putBoolean("enabled",true).putLong("started",System.currentTimeMillis()).apply();startForegroundService(new Intent(MainActivity.this,AlertMonitorService.class));out.put("starting",true);
    }
    else if(action.equals("exit")){finish();out.put("ok",true);}
    else if(action.equals("forget")){AlertMonitorService.stop(MainActivity.this);ServerSettings.forget(MainActivity.this);out.put("ok",true);}
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
 @Override protected void onPause(){setDesktopFullscreen(false);if(web!=null)web.evaluateJavascript("window.pauseApp&&pauseApp()",null);super.onPause();}
 @Override protected void onResume(){super.onResume();if(web!=null)web.evaluateJavascript("window.resumeApp&&resumeApp()",null);}
 void backupEvent(String type,JSONObject event){runOnUiThread(()->{if(!isDestroyed())web.evaluateJavascript("window.backupEvent&&backupEvent("+JSONObject.quote(type)+","+event.toString()+")",null);});}
 void fileProgress(JSONObject progress){runOnUiThread(()->{if(!isDestroyed())web.evaluateJavascript("window.fileTransferProgress&&fileTransferProgress("+progress.toString()+")",null);});}
 @Override protected void onActivityResult(int request,int code,Intent data){super.onActivityResult(request,code,data);if(files!=null)files.result(request,code,data);if(backup!=null)backup.result(request,code,data);}
 @Override public void onBackPressed(){web.evaluateJavascript("window.appBack&&appBack()",null);}
 @Override protected void onDestroy(){if(files!=null)files.close();if(backup!=null)backup.close();pool.shutdown();if(web!=null){web.removeJavascriptInterface("Pi");web.destroy();}super.onDestroy();}
}
