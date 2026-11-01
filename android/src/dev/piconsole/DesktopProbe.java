// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import android.app.Activity;
import android.content.pm.PackageInfo;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Point;
import android.graphics.Rect;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.view.PixelCopy;
import android.webkit.WebView;
import org.json.JSONArray;
import org.json.JSONObject;

/** Window sampling returns aggregate ratios and fixed failure codes, never images. */
final class DesktopProbe {
 interface Done { void complete(JSONObject value); }
 private static void failed(JSONObject out,String reason,Done done)throws Exception {
  out.put("available",false);out.put("reason",reason);done.complete(out);
 }
 // Numeric geometry is sufficient to distinguish app letterboxing from CSS placement.
 // Bound every platform value and expose no screenshot, page text or input data.
 private static JSONArray geometryValues(int... values){
  JSONArray out=new JSONArray();for(int value:values)out.put(Math.max(-131072,Math.min(131072,value)));return out;
 }
 private static JSONObject geometry(Activity activity,WebView web)throws Exception {
  int[] inWindow=new int[2],onScreen=new int[2];web.getLocationInWindow(inWindow);web.getLocationOnScreen(onScreen);
  JSONObject out=new JSONObject().put("view",geometryValues(web.getWidth(),web.getHeight()))
   .put("content",geometryValues(Math.max(0,web.getWidth()-web.getPaddingLeft()-web.getPaddingRight()),Math.max(0,web.getHeight()-web.getPaddingTop()-web.getPaddingBottom())))
   .put("padding",geometryValues(web.getPaddingLeft(),web.getPaddingTop(),web.getPaddingRight(),web.getPaddingBottom()))
   .put("window",geometryValues(activity.getWindow().getDecorView().getWidth(),activity.getWindow().getDecorView().getHeight()))
   .put("inWindow",geometryValues(inWindow[0],inWindow[1])).put("onScreen",geometryValues(onScreen[0],onScreen[1]));
  android.view.Display display=web.getDisplay();
  if(display!=null){Point size=new Point();display.getRealSize(size);out.put("display",geometryValues(size.x,size.y));}
  return out;
 }
 private static JSONArray rectangle(Rect r){return new JSONArray().put(r.left).put(r.top).put(r.right).put(r.bottom);}
 static void capture(Activity activity,WebView web,JSONObject request,Done done)throws Exception {
  final JSONObject out=new JSONObject().put("available",false);
  out.put("sdk",Build.VERSION.SDK_INT);out.put("layer",web.getLayerType());out.put("hardwareWindow",web.isHardwareAccelerated());
  try{PackageInfo pkg=WebView.getCurrentWebViewPackage();if(pkg!=null)out.put("webview",pkg.packageName+" "+pkg.versionName);}catch(Exception ignored){}
  try{out.put("geometry",geometry(activity,web));}catch(Exception ignored){}
  final double cssWidth,cssHeight,x,y,width,height;
  try{
   cssWidth=request.getDouble("cssWidth");cssHeight=request.getDouble("cssHeight");
   x=request.getDouble("x");y=request.getDouble("y");width=request.getDouble("width");height=request.getDouble("height");
  }catch(Exception e){failed(out,"invalid-geometry",done);return;}
  for(double n:new double[]{cssWidth,cssHeight,x,y,width,height})if(Double.isNaN(n)||Double.isInfinite(n)){failed(out,"invalid-geometry",done);return;}
  if(cssWidth<=0||cssHeight<=0||width<=0||height<=0||x< -1||y< -1||x+width>cssWidth+1||y+height>cssHeight+1){failed(out,"invalid-geometry",done);return;}
  int[] location=new int[2];web.getLocationInWindow(location);
  double sx=(web.getWidth()-web.getPaddingLeft()-web.getPaddingRight())/cssWidth;
  double sy=(web.getHeight()-web.getPaddingTop()-web.getPaddingBottom())/cssHeight;
  Rect source=new Rect((int)Math.round(location[0]+web.getPaddingLeft()+x*sx),(int)Math.round(location[1]+web.getPaddingTop()+y*sy),
    (int)Math.round(location[0]+web.getPaddingLeft()+(x+width)*sx),(int)Math.round(location[1]+web.getPaddingTop()+(y+height)*sy));
  out.put("requestedPixels",rectangle(source));
  Rect visible=new Rect(Math.max(0,location[0]+web.getPaddingLeft()),Math.max(0,location[1]+web.getPaddingTop()),
    Math.min(activity.getWindow().getDecorView().getWidth(),location[0]+web.getWidth()-web.getPaddingRight()),
    Math.min(activity.getWindow().getDecorView().getHeight(),location[1]+web.getHeight()-web.getPaddingBottom()));
  // Fractional CSS centering and integer clientHeight can differ by < 1 CSS px.
  // Keep the visible part instead of refusing the entire screen sample.
  if(source.width()<=0||source.height()<=0||!source.intersect(visible)){failed(out,"outside-window",done);return;}
  out.put("sampledPixels",rectangle(source));
  final Bitmap bitmap;
  try{bitmap=Bitmap.createBitmap(160,100,Bitmap.Config.ARGB_8888);}catch(Exception e){failed(out,"bitmap-allocation",done);return;}
  try {
   PixelCopy.request(activity.getWindow(),source,bitmap,status->{
    try {
     out.put("pixelCopy",status);
     if(status==PixelCopy.SUCCESS){
      JSONArray columns=new JSONArray();
      for(int col:new int[]{5,50,70,90,99}){
       int black=0,transparent=0;
       for(int row:new int[]{10,20,40,60,80,90}){
        int p=bitmap.getPixel(Math.min(159,160*col/100),row);
        if(Color.alpha(p)==0)transparent++;
        if(Color.alpha(p)>0&&Color.red(p)<=16&&Color.green(p)<=16&&Color.blue(p)<=16)black++;
       }
       columns.put(new JSONObject().put("x",col).put("black",Math.round(black*100f/6)).put("transparent",Math.round(transparent*100f/6)));
      }
      out.put("columns",columns);out.put("available",true);
     }else out.put("reason","pixel-copy-failed");
    }catch(Exception ignored){try{out.put("available",false);out.put("reason","pixel-sampling");}catch(Exception ignoredAgain){}}
    finally{bitmap.recycle();done.complete(out);}
   },new Handler(Looper.getMainLooper()));
  }catch(Exception e){bitmap.recycle();failed(out,"pixel-copy-request",done);}
 }
}
