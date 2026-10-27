// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.webkit.WebView;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
/** Only the app's trusted WebView may enable desktop input; callbacks carry a session token. */
final class DesktopInput {
 private static final int MAX_CLIPBOARD=16384;
 private final Activity activity;private final WebView web;
 private final DesktopKeys.Pressed pressed=new DesktopKeys.Pressed();
 private String session="";private boolean focused=true;private final DesktopPointer pointer=new DesktopPointer();
 DesktopInput(Activity activity,WebView web){
  this.activity=activity;this.web=web;
  web.setOnKeyListener((view,code,event)->key(event));
  web.setOnGenericMotionListener((view,event)->mouse(event));
  web.setOnTouchListener((view,event)->mouse(event));
 }
 void setSession(String value){
  if(value==null||value.length()>128)throw new IllegalArgumentException("Invalid desktop session");
  if(!session.equals(value)){release();session=value;}
 }
 void setRegion(JSONObject bounds)throws Exception{
  pointer.set(bounds.getDouble("left"),bounds.getDouble("top"),bounds.getDouble("right"),bounds.getDouble("bottom"));
 }
 void focusChanged(boolean value){if(!value)release();focused=value;}
 private void emit(JSONObject event){
  if(session.isEmpty())return;
  try{event.put("session",session);web.evaluateJavascript("window.desktopNativeInput&&window.desktopNativeInput("+event.toString()+")",null);}catch(Exception ignored){}
 }
 private void keyEvent(int sym,boolean down){try{emit(new JSONObject().put("type","key").put("keysym",sym).put("down",down));}catch(Exception ignored){}}
 private void release(){
  pointer.reset();
  for(int sym:pressed.release())keyEvent(sym,false);
  try{emit(new JSONObject().put("type","reset"));}catch(Exception ignored){}
 }
 private boolean key(KeyEvent event){
  if(session.isEmpty()||!focused||event.getDeviceId()==android.view.KeyCharacterMap.VIRTUAL_KEYBOARD||event.getKeyCode()==KeyEvent.KEYCODE_BACK)return false;
  if(event.getAction()!=KeyEvent.ACTION_DOWN&&event.getAction()!=KeyEvent.ACTION_UP)return false;
  // Ctrl/Alt/Meta affect the remote modifier state, not the translated character.
  int meta=event.getMetaState()&~(KeyEvent.META_CTRL_MASK|KeyEvent.META_ALT_MASK|KeyEvent.META_META_MASK);
  int sym=DesktopKeys.keysym(event.getKeyCode(),event.getUnicodeChar(meta));
  if(event.getAction()==KeyEvent.ACTION_DOWN){if(sym==0)return false;keyEvent(pressed.down(event.getKeyCode(),sym),true);}
  else {sym=pressed.up(event.getKeyCode(),sym);if(sym==0)return false;keyEvent(sym,false);}
  return true;
 }
 private boolean mouse(MotionEvent event){
  if(session.isEmpty()||!focused||!event.isFromSource(InputDevice.SOURCE_MOUSE))return false;
  int action=event.getActionMasked();
  if(action!=MotionEvent.ACTION_DOWN&&action!=MotionEvent.ACTION_UP&&action!=MotionEvent.ACTION_MOVE&&action!=MotionEvent.ACTION_HOVER_MOVE&&action!=MotionEvent.ACTION_SCROLL&&action!=MotionEvent.ACTION_BUTTON_PRESS&&action!=MotionEvent.ACTION_BUTTON_RELEASE&&action!=MotionEvent.ACTION_CANCEL)return false;
  if(web.getWidth()<=0||web.getHeight()<=0)return false;
  int buttons=action==MotionEvent.ACTION_CANCEL?0:event.getButtonState();
  double[] point=pointer.sample(event.getX()/web.getWidth(),event.getY()/web.getHeight(),buttons);if(point==null)return false;
  try{
   emit(new JSONObject().put("type","mouse").put("x",point[0]).put("y",point[1]).put("buttons",buttons).put("wheel",action==MotionEvent.ACTION_SCROLL?event.getAxisValue(MotionEvent.AXIS_VSCROLL):0).put("horizontal",action==MotionEvent.ACTION_SCROLL?event.getAxisValue(MotionEvent.AXIS_HSCROLL):0));
  }catch(Exception ignored){}
  return true;
 }
 static String checkedClipboard(String text){
  if(text==null||text.length()>MAX_CLIPBOARD||text.getBytes(StandardCharsets.UTF_8).length>MAX_CLIPBOARD)throw new IllegalArgumentException("剪贴板文字最多 16 KiB");
  return text;
 }
 private void requireSession(){if(session.isEmpty()||!focused)throw new IllegalStateException("请先连接远程桌面");}
 JSONObject readClipboard()throws Exception{
  requireSession();
  ClipboardManager clipboard=(ClipboardManager)activity.getSystemService(Context.CLIPBOARD_SERVICE);String text="";
  // Plain text only: do not coerce URIs or invoke remote clipboard providers.
  if(clipboard!=null&&clipboard.hasPrimaryClip()){
   ClipData data=clipboard.getPrimaryClip();
   if(data!=null&&data.getItemCount()>0&&data.getItemAt(0).getText()!=null)text=data.getItemAt(0).getText().toString();
  }
  return new JSONObject().put("text",checkedClipboard(text));
 }
 JSONObject writeClipboard(String text)throws Exception{
  requireSession();checkedClipboard(text);
  ClipboardManager clipboard=(ClipboardManager)activity.getSystemService(Context.CLIPBOARD_SERVICE);
  if(clipboard==null)throw new IllegalStateException("剪贴板不可用");
  clipboard.setPrimaryClip(ClipData.newPlainText("Pi Console desktop",text));return new JSONObject().put("ok",true);
 }
}
