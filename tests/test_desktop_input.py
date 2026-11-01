# SPDX-License-Identifier: Apache-2.0
"""Exercise actual native input routing against small Android boundary fakes."""
import os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SDK={
 'android/content/Context.java':'package android.content; public class Context {public static final String CLIPBOARD_SERVICE="clipboard";public Object getSystemService(String s){return new ClipboardManager();}}',
 'android/app/Activity.java':'package android.app; public class Activity extends android.content.Context {}',
 'android/content/ClipData.java':'package android.content; public class ClipData {public static ClipData newPlainText(String l,String t){return new ClipData();}public int getItemCount(){return 0;}public Item getItemAt(int i){return new Item();}public static class Item {public CharSequence getText(){return "";}}}',
 'android/content/ClipboardManager.java':'package android.content; public class ClipboardManager {public boolean hasPrimaryClip(){return false;}public ClipData getPrimaryClip(){return null;}public void setPrimaryClip(ClipData d){}}',
 'android/view/InputDevice.java':'package android.view; public class InputDevice {public static final int SOURCE_MOUSE=8194;}',
 'android/view/KeyCharacterMap.java':'package android.view; public class KeyCharacterMap {public static final int VIRTUAL_KEYBOARD=-1;}',
 'android/view/KeyEvent.java':'''package android.view;public class KeyEvent {
 public static final int KEYCODE_BACK=4,ACTION_DOWN=0,ACTION_UP=1,META_CTRL_MASK=0x7000,META_ALT_MASK=0x32,META_META_MASK=0x70000;
 public int device=1,code,action,repeat;public boolean ctrl,alt;
 public KeyEvent(int c,boolean down,boolean control,boolean alternate,int r){code=c;action=down?0:1;ctrl=control;alt=alternate;repeat=r;}
 public int getDeviceId(){return device;}public int getKeyCode(){return code;}public int getAction(){return action;}public int getRepeatCount(){return repeat;}
 public boolean isCtrlPressed(){return ctrl;}public boolean isAltPressed(){return alt;}public int getMetaState(){return 0;}public int getUnicodeChar(int m){return code==29?97:code==62?32:0;}
 }''',
 'android/view/MotionEvent.java':'''package android.view;public class MotionEvent {
 public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,ACTION_HOVER_MOVE=7,ACTION_SCROLL=8,ACTION_BUTTON_PRESS=11,ACTION_BUTTON_RELEASE=12,AXIS_VSCROLL=9,AXIS_HSCROLL=10;
 public int action=0,buttons=1;public float x=100,y=100;public MotionEvent(){}public MotionEvent(int a,float xx,float yy,int b){action=a;x=xx;y=yy;buttons=b;}public boolean isFromSource(int s){return true;}public int getActionMasked(){return action;}public int getButtonState(){return buttons;}public float getX(){return x;}public float getY(){return y;}public float getAxisValue(int a){return 0;}
 }''',
 'android/webkit/WebView.java':'''package android.webkit;public class WebView {
 public interface MotionListener {boolean event(WebView v,android.view.MotionEvent e);}
 public java.util.List<String> events=new java.util.ArrayList<>();public MotionListener touch;public int left,right,top,bottom;public int getPaddingLeft(){return left;}public int getPaddingRight(){return right;}public int getPaddingTop(){return top;}public int getPaddingBottom(){return bottom;}
 public void setOnGenericMotionListener(MotionListener l){}public void setOnTouchListener(MotionListener l){touch=l;}
 public void evaluateJavascript(String s,Object cb){events.add(s);}public int getWidth(){return 1000;}public int getHeight(){return 500;}
 }''',
 'org/json/JSONArray.java':'package org.json;public class JSONArray {private java.util.List<JSONObject> items=new java.util.ArrayList<>();public JSONArray put(JSONObject e){items.add(e);return this;}public int length(){return items.size();}public JSONObject getJSONObject(int i){return items.get(i);}}',
 'org/json/JSONObject.java':'''package org.json;public class JSONObject {private java.util.Map<String,Object> data=new java.util.LinkedHashMap<>();public JSONObject put(String k,Object v){data.put(k,v);return this;}public double getDouble(String k){return ((Number)data.get(k)).doubleValue();}public JSONArray optJSONArray(String k){Object v=data.get(k);return v instanceof JSONArray?(JSONArray)v:null;}public String toString(){return data.toString();}}''',
 'dev/piconsole/DesktopInputRoutingTest.java':'''package dev.piconsole;
 import android.view.KeyEvent;import android.webkit.WebView;import org.json.JSONObject;
 public class DesktopInputRoutingTest {
 static void check(boolean b,String m){if(!b)throw new AssertionError(m);}
 static boolean key(DesktopInput d,int code,boolean down,boolean ctrl,boolean alt,int repeat){return d.key(new KeyEvent(code,down,ctrl,alt,repeat));}
 public static void main(String[] args)throws Exception{
  WebView w=new WebView();DesktopInput d=new DesktopInput(new android.app.Activity(),w);
  d.setShortcutSession("sid");d.setSession("sid");
  check(key(d,113,true,true,false,0),"remote Ctrl consumed");check(key(d,57,true,true,true,0),"remote Alt consumed");key(d,29,true,true,true,0);
  check(key(d,62,true,true,true,0),"chord consumed before WebView");
  String out=w.events.toString();check(out.contains("keysym=97, down=false"),"held character released");check(out.contains("keysym=65507, down=false"),"Ctrl released");
  check(out.contains("type=reset")&&out.contains("type=toggle-target, session=sid"),"release and session-scoped toggle emitted");check(!out.contains("keysym=32"),"toggle Space never forwarded");
  check(out.indexOf("type=reset")<out.indexOf("toggle-target"),"remote reset precedes target switch");
  check(!key(d,29,true,false,false,0),"capture stops immediately before asynchronous JS response");
  w.events.clear();d.setSession("sid");check(key(d,62,true,true,true,1),"repeat consumed after JS restored capture");check(w.events.isEmpty(),"repeat does not toggle or forward");
  check(key(d,62,false,false,false,0),"Space up consumed after modifiers released first");check(w.events.isEmpty(),"Space release never forwarded");
  d.focusChanged(false);check(!key(d,62,true,true,true,0),"unfocused Activity ignores shortcut");d.focusChanged(true);
  KeyEvent virtual=new KeyEvent(62,true,true,true,0);virtual.device=-1;check(!d.key(virtual),"IME keyboard stays local");check(!key(d,4,true,true,true,0),"Android Back stays local");
  d.setSession("");w.events.clear();check(key(d,62,true,true,true,0),"local target can still invoke shortcut");check(w.events.toString().contains("toggle-target"),"return-to-remote shortcut emitted");
  d.setShortcutSession("");w.events.clear();check(!key(d,62,true,true,true,0),"disconnected session has no hotkey");check(w.events.isEmpty(),"no stale session event after disconnect");
  d.setShortcutSession("new");d.setSession("new");d.setRegion(new JSONObject().put("left",0).put("top",0).put("right",1).put("bottom",1));check(w.touch.event(w,new android.view.MotionEvent()),"remote mouse consumed");
  d.setSession("");check(!w.touch.event(w,new android.view.MotionEvent()),"phone target mouse passed to WebView");d.readClipboard();
  d.setSession("new");w.left=49;w.right=49;w.top=11;w.bottom=11;w.events.clear();
  d.setRegion(new JSONObject().put("left",0).put("top",0).put("right",1).put("bottom",1));
  check(w.touch.event(w,new android.view.MotionEvent(0,274.5f,130.5f,1)),"padded content mouse consumed");
  check(w.events.toString().contains("x=0.25, y=0.25"),"mouse coordinates must exclude native safe padding before CSS normalization");
  check(w.touch.event(w,new android.view.MotionEvent(1,0,0,0)),"drag release in safe padding still reaches remote");
  check(!w.touch.event(w,new android.view.MotionEvent(7,0,0,0)),"safe padding hover stays local after release");
  d.setRegion(new JSONObject().put("left",0).put("top",0).put("right",1).put("bottom",1).put("exclude",new org.json.JSONArray().put(new JSONObject().put("left",.2).put("top",.2).put("right",.3).put("bottom",.3))));
  check(!w.touch.event(w,new android.view.MotionEvent(0,274.5f,130.5f,1)),"padded CSS local control remains local");
  w.left=500;w.right=500;check(!w.touch.event(w,new android.view.MotionEvent()),"empty content refuses mouse");
  w.left=0;w.right=0;w.top=0;w.bottom=0;
  d.setRegion(new JSONObject().put("left",0).put("top",0).put("right",1).put("bottom",1).put("exclude",new org.json.JSONArray().put(new JSONObject().put("left",.05).put("top",.05).put("right",.2).put("bottom",.4))));check(!w.touch.event(w,new android.view.MotionEvent()),"overlaid local control bypasses native mouse forwarding");d.setSession("");
  d.setShortcutSession("");boolean refused=false;try{d.readClipboard();}catch(IllegalStateException expected){refused=true;}check(refused,"clipboard requires registered foreground desktop");
  System.out.println("Native routing releases keys, consumes chord/repeats, scopes sessions/focus/IME, restores phone mouse and bounds clipboard access (Android API fakes)");
 }
 }'''
}
@unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK required for native input routing boundary')
class DesktopInputTests(unittest.TestCase):
 def test_foreground_target_routing(self):
  with tempfile.TemporaryDirectory(prefix='pi-console-input-test-') as tmp:
   base=Path(tmp)
   for name,source in SDK.items():
    p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source)
   sources=[ROOT/'android/src/dev/piconsole'/name for name in ('DesktopInput.java','DesktopKeys.java','DesktopPointer.java','DesktopShortcut.java')]
   result=subprocess.run(['javac','--release','8','-d',str(base),*map(str,sources),*map(str,base.rglob('*.java'))],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run(['java','-cp',str(base),'dev.piconsole.DesktopInputRoutingTest'],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   print(result.stdout.strip())
if __name__=='__main__':unittest.main()
