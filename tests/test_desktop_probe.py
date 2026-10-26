# SPDX-License-Identifier: Apache-2.0
"""Exercise real probe geometry and completion against small Android API fakes.

The boundary is the rectangle submitted to PixelCopy, not actual phone drawing.
The fakes keep Android-only calls runnable on a JVM and retain no screenshots.
"""
import shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SDK={
 'android/app/Activity.java':'''package android.app; public class Activity { public android.view.Window getWindow(){return new android.view.Window();} }''',
 'android/view/Window.java':'''package android.view; public class Window {public View getDecorView(){return new View();}}''',
 'android/view/View.java':'''package android.view; public class View {public int getWidth(){return 2250;} public int getHeight(){return 1078;} }''',
 'android/content/pm/PackageInfo.java':'''package android.content.pm; public class PackageInfo {public String packageName="test.webview",versionName="test-version";}''',
 'android/graphics/Rect.java':'''package android.graphics; public class Rect {public int left,top,right,bottom; public Rect(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;} public int width(){return right-left;} public int height(){return bottom-top;} public boolean contains(Rect r){return left<=r.left&&top<=r.top&&right>=r.right&&bottom>=r.bottom;} public boolean intersect(Rect r){int l=Math.max(left,r.left),t=Math.max(top,r.top),rr=Math.min(right,r.right),b=Math.min(bottom,r.bottom);if(l>=rr||t>=b)return false;left=l;top=t;right=rr;bottom=b;return true;} }''',
 'android/graphics/Bitmap.java':'''package android.graphics; public class Bitmap {public enum Config {ARGB_8888} public static int live,color=0xff222222;public Bitmap(){live++;} public static Bitmap createBitmap(int w,int h,Config c){return new Bitmap();} public int getPixel(int x,int y){return color;} public void recycle(){live--;} }''',
 'android/graphics/Color.java':'''package android.graphics; public class Color {public static int alpha(int p){return p>>>24;}public static int red(int p){return p>>16&255;}public static int green(int p){return p>>8&255;}public static int blue(int p){return p&255;} }''',
 'android/os/Build.java':'''package android.os; public class Build {public static class VERSION {public static int SDK_INT=35;}}''',
 'android/os/Handler.java':'''package android.os; public class Handler {public Handler(Looper l){} }''',
 'android/os/Looper.java':'''package android.os; public class Looper {public static Looper getMainLooper(){return new Looper();}}''',
 'android/webkit/WebView.java':'''package android.webkit; public class WebView extends android.view.View {public static android.content.pm.PackageInfo getCurrentWebViewPackage(){return new android.content.pm.PackageInfo();}public int getLayerType(){return 1;}public boolean isHardwareAccelerated(){return true;}public int getPaddingLeft(){return 0;}public int getPaddingRight(){return 0;}public int getPaddingTop(){return 0;}public int getPaddingBottom(){return 0;}public void getLocationInWindow(int[] a){a[0]=0;a[1]=0;} }''',
 'android/view/PixelCopy.java':'''package android.view; public class PixelCopy {public static final int SUCCESS=0;public static int status=0,calls;public static boolean fail;public static android.graphics.Rect last;public interface OnPixelCopyFinishedListener {void onPixelCopyFinished(int status);}public static void request(Window w,android.graphics.Rect r,android.graphics.Bitmap b,OnPixelCopyFinishedListener done,android.os.Handler h){calls++;last=r;if(fail)throw new IllegalArgumentException("private-password-in-provider-error");done.onPixelCopyFinished(status);} }''',
 'org/json/JSONObject.java':'''package org.json; public class JSONObject {private java.util.Map<String,Object> data=new java.util.LinkedHashMap<>();public JSONObject put(String k,Object v){data.put(k,v);return this;}public double getDouble(String k){return ((Number)data.get(k)).doubleValue();}public Object get(String k){return data.get(k);}public String toString(){return data.toString();} }''',
 'org/json/JSONArray.java':'''package org.json; public class JSONArray {private java.util.List<Object> data=new java.util.ArrayList<>();public JSONArray put(Object v){data.add(v);return this;}public Object get(int i){return data.get(i);} }''',
 'dev/piconsole/DesktopProbeTest.java':'''package dev.piconsole;
import org.json.JSONObject;import android.view.PixelCopy;import android.graphics.Rect;import android.graphics.Bitmap;
public class DesktopProbeTest {
 static void require(boolean b,String message){if(!b)throw new AssertionError(message);}
 static JSONObject run(double x,double y,double width,double height)throws Exception{
  JSONObject req=new JSONObject().put("cssWidth",818).put("cssHeight",392).put("x",x).put("y",y).put("width",width).put("height",height);
  JSONObject[] result={null};PixelCopy.calls=0;
  DesktopProbe.capture(new android.app.Activity(),new android.webkit.WebView(),req,r->result[0]=r);
  require(result[0]!=null,"Probe must complete once without hiding errors");require(Bitmap.live==0,"Probe bitmap leaked");return result[0];
 }
 public static void main(String[] args)throws Exception{
  JSONObject report;
  try{report=run(59.75568389892578,-0.13636364042758942,698.664794921875,393);}
  catch(Exception e){throw new AssertionError("Reported fractional landscape frame must still be sampled; clip subpixel overflow to the actual window",e);}
  require(PixelCopy.calls==1,"Valid edge frame never reached PixelCopy");
  Rect r=PixelCopy.last;require(r.left==164&&r.top==0&&r.right==2086&&r.bottom==1078,"Probe sampled a rectangle outside the real window");
  require(Boolean.TRUE.equals(report.get("available")),"Successful probe must identify availability");require(report.get("sdk").equals(35),"SDK metadata missing");
  Bitmap.color=0xff08090b;report=run(10,10,100,100);org.json.JSONArray cols=(org.json.JSONArray)report.get("columns");require(((JSONObject)cols.get(0)).get("black").equals(100),"Near-black blank viewport must count as black");Bitmap.color=0xff222222;
  PixelCopy.status=3;report=run(10,10,100,100);require(Boolean.FALSE.equals(report.get("available")),"Failed PixelCopy reported available");require(report.get("pixelCopy").equals(3),"PixelCopy error code lost");require(report.get("reason").equals("pixel-copy-failed"),"Failure stage not preserved");
  PixelCopy.status=0;PixelCopy.fail=true;report=run(10,10,100,100);PixelCopy.fail=false;require(Boolean.FALSE.equals(report.get("available")),"Throwing platform must complete with failure metadata");require(report.get("reason").equals("pixel-copy-request"),"Request failure stage missing");require(!report.toString().contains("private-password"),"Platform exception text leaked");
  report=run(-10,0,100,100);require(PixelCopy.calls==0,"Invalid geometry reached PixelCopy");require(report.get("reason").equals("invalid-geometry"),"Bad geometry failure hidden");
  System.out.println("Reported edge geometry, window clipping, error metadata, bitmap cleanup and error privacy passed (Android API fakes; not a handset rendering test)");
 }
}'''
}
@unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK required for native probe boundary regression')
class DesktopProbeTests(unittest.TestCase):
 def test_fractional_landscape_and_native_errors(self):
  with tempfile.TemporaryDirectory(prefix='pi-console-probe-test-') as tmp:
   base=Path(tmp)
   for name,source in SDK.items():
    p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source)
   result=subprocess.run(['javac','--release','8','-d',str(base),str(ROOT/'android/src/dev/piconsole/DesktopProbe.java'),*map(str,base.rglob('*.java'))],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run(['java','-cp',str(base),'dev.piconsole.DesktopProbeTest'],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   print(result.stdout.strip())
if __name__=='__main__':unittest.main()
