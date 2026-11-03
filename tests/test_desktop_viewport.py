# SPDX-License-Identifier: Apache-2.0
"""Exercise native fullscreen geometry against lightweight Android API boundaries."""
import shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SDK={
 'android/os/Build.java':'''package android.os;public class Build {public static class VERSION {public static int SDK_INT;}}''',
 'android/graphics/Insets.java':'''package android.graphics;public class Insets {public static final Insets NONE=new Insets(0,0,0,0);public int left,top,right,bottom;public Insets(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;}}''',
 'android/view/DisplayCutout.java':'''package android.view;public class DisplayCutout {int l,t,r,b;public DisplayCutout(int ll,int tt,int rr,int bb){l=ll;t=tt;r=rr;b=bb;}public int getSafeInsetLeft(){return l;}public int getSafeInsetTop(){return t;}public int getSafeInsetRight(){return r;}public int getSafeInsetBottom(){return b;}}''',
 'android/view/View.java':'''package android.view;public class View {
 public static final int SYSTEM_UI_FLAG_FULLSCREEN=4,SYSTEM_UI_FLAG_HIDE_NAVIGATION=2,SYSTEM_UI_FLAG_IMMERSIVE_STICKY=4096,SYSTEM_UI_FLAG_IMMERSIVE=2048,SYSTEM_UI_FLAG_LAYOUT_STABLE=256,SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION=512,SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN=1024,SYSTEM_UI_FLAG_LIGHT_STATUS_BAR=8192,SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR=16;
 public int visibility,left,top,right,bottom;public void setSystemUiVisibility(int n){visibility=n;}public void setPadding(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;}
 }''',
 'android/view/WindowManager.java':'''package android.view;public interface WindowManager {public static class LayoutParams {public static final int LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES=1,FLAG_KEEP_SCREEN_ON=128;public int layoutInDisplayCutoutMode=2;}}''',
 'android/view/WindowInsetsController.java':'''package android.view;public class WindowInsetsController {public static final int BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE=2,BEHAVIOR_DEFAULT=1;public int behavior,hidden,shown;public void setSystemBarsBehavior(int b){behavior=b;}public void hide(int t){hidden=t;}public void show(int t){shown=t;}}''',
 'android/view/Window.java':'''package android.view;public class Window {public View decor=new View();public WindowManager.LayoutParams attrs=new WindowManager.LayoutParams();public WindowInsetsController controller=new WindowInsetsController();public int flags,fitCalls;public boolean fits=true;public View getDecorView(){return decor;}public WindowManager.LayoutParams getAttributes(){if(android.os.Build.VERSION.SDK_INT<28)throw new AssertionError("cutout API before 28");return attrs;}public void setAttributes(WindowManager.LayoutParams a){attrs=a;}public void setDecorFitsSystemWindows(boolean b){if(android.os.Build.VERSION.SDK_INT<30)throw new AssertionError("decorFits API before 30");fits=b;fitCalls++;}public WindowInsetsController getInsetsController(){if(android.os.Build.VERSION.SDK_INT<30)throw new AssertionError("controller API before 30");return controller;}public void addFlags(int n){flags|=n;}public void clearFlags(int n){flags&=~n;}}''',
 'android/view/WindowInsets.java':'''package android.view;public class WindowInsets {
 public DisplayCutout cutout=new DisplayCutout(49,0,0,11);public int imeBottom,systemBottom=44,systemLeft=17,systemTop=24,systemRight=33;public boolean consumed;
 public android.graphics.Insets bars=new android.graphics.Insets(17,24,33,44),cutoutInsets=new android.graphics.Insets(49,0,0,11),gestures=new android.graphics.Insets(9,0,9,0);
 public WindowInsets(){}public WindowInsets(WindowInsets source){cutout=source.cutout;imeBottom=source.imeBottom;systemBottom=source.systemBottom;systemLeft=source.systemLeft;systemTop=source.systemTop;systemRight=source.systemRight;bars=source.bars;cutoutInsets=source.cutoutInsets;gestures=source.gestures;consumed=source.consumed;}
 public int getStableInsetBottom(){return 44;}public int getSystemWindowInsetLeft(){return systemLeft;}public int getSystemWindowInsetTop(){return systemTop;}public int getSystemWindowInsetRight(){return systemRight;}public int getSystemWindowInsetBottom(){return systemBottom;}
 public boolean isConsumed(){return consumed;}public DisplayCutout getDisplayCutout(){if(android.os.Build.VERSION.SDK_INT<28)throw new AssertionError("cutout API before 28");return cutout;}
 public WindowInsets replaceSystemWindowInsets(int l,int t,int r,int b){WindowInsets out=new WindowInsets(this);out.systemLeft=l;out.systemTop=t;out.systemRight=r;out.systemBottom=b;return out;}
 public WindowInsets consumeDisplayCutout(){if(android.os.Build.VERSION.SDK_INT<28)throw new AssertionError("consume cutout API before 28");WindowInsets out=new WindowInsets(this);out.cutout=null;out.cutoutInsets=android.graphics.Insets.NONE;return out;}
 public android.graphics.Insets getInsets(int type){if(android.os.Build.VERSION.SDK_INT<30)throw new AssertionError("insets API before 30");if(type==8)return new android.graphics.Insets(0,0,0,imeBottom);if(type==16)return cutoutInsets;if(type==128)return gestures;return bars;}
 public static class Builder {private WindowInsets out;public Builder(WindowInsets source){if(android.os.Build.VERSION.SDK_INT<29)throw new AssertionError("Builder API before 29");out=new WindowInsets(source);}public Builder setInsets(int types,android.graphics.Insets n){if(android.os.Build.VERSION.SDK_INT<30)throw new AssertionError("typed Builder API before 30");if((types&7)!=0)out.bars=n;if((types&8)!=0)out.imeBottom=n.bottom;if((types&16)!=0)out.cutoutInsets=n;return this;}public Builder setDisplayCutout(DisplayCutout c){out.cutout=c;return this;}public WindowInsets build(){return out;}}
 public static class Type {public static int systemBars(){return 7;}public static int ime(){return 8;}public static int displayCutout(){return 16;}public static int systemGestures(){return 128;}}
 }''',
 'dev/piconsole/DesktopViewportTest.java':'''package dev.piconsole;
 import android.os.Build;import android.view.*;import java.lang.reflect.*;
 public class DesktopViewportTest {
 static void check(boolean b,String m){if(!b)throw new AssertionError(m);}
 static void padding(View v,int l,int t,int r,int b){check(v.left==l&&v.top==t&&v.right==r&&v.bottom==b,"Unexpected safe-content padding on SDK "+Build.VERSION.SDK_INT+": "+v.left+","+v.top+","+v.right+","+v.bottom);}
 public static void main(String[] args)throws Exception{
  Class<?> type;try{type=Class.forName("dev.piconsole.DesktopViewport");}catch(ClassNotFoundException e){throw new AssertionError("Native fullscreen must own cutout and edge-to-edge window geometry",e);}
  Constructor<?> constructor=type.getDeclaredConstructor(Window.class);constructor.setAccessible(true);
  Method fullscreen=type.getDeclaredMethod("setFullscreen",boolean.class,boolean.class);fullscreen.setAccessible(true);
  Method apply=type.getDeclaredMethod("applyInsets",View.class,WindowInsets.class);apply.setAccessible(true);
  int[] sdks=args.length==0?new int[]{26,27,28,29,30,33,35,36,37}:new int[]{Integer.parseInt(args[0])};
  Method remaining;try{remaining=type.getDeclaredMethod("remainingInsets",WindowInsets.class);}catch(NoSuchMethodException e){throw new AssertionError("Handled native insets must be zeroed before WebView receives them",e);}remaining.setAccessible(true);
  for(int sdk:sdks){
   Build.VERSION.SDK_INT=sdk;Window window=new Window();Object viewport=constructor.newInstance(window);View view=new View();WindowInsets insets=new WindowInsets();
   fullscreen.invoke(viewport,true,false);
   if(sdk>=28)check(window.attrs.layoutInDisplayCutoutMode==1,"Fullscreen still permits OEM landscape cutout letterboxing on SDK "+sdk);
   if(sdk>=30){check(!window.fits,"Immersive decor must fill the window");check(window.controller.hidden==7&&window.controller.behavior==1,"Fullscreen must keep system Back gestures enabled while bars are hidden");}
   else {check((window.decor.visibility&3590)==3590,"Legacy immersive layout must retain Back gestures behind hidden bars");check((window.decor.visibility&4096)==0,"Sticky immersion blocks system Back gestures");}
   check((window.flags&128)!=0,"Fullscreen stopped keeping the desktop awake");
   apply.invoke(viewport,view,insets);if(sdk>=28)padding(view,49,11,49,11);else padding(view,0,0,0,0);
   // Layout behind system bars must still keep the local text editor above the IME.
   insets.imeBottom=344;insets.systemBottom=344;apply.invoke(viewport,view,insets);
   if(sdk>=28)padding(view,49,11,49,344);else padding(view,0,0,0,344);
   // Closing the keyboard restores symmetric cutout margins; transient bars stay ignored.
   insets.imeBottom=0;insets.systemBottom=44;apply.invoke(viewport,view,insets);
   if(sdk>=28)padding(view,49,11,49,11);else padding(view,0,0,0,0);
   if(sdk>=28){insets.cutout=new DisplayCutout(0,19,71,0);apply.invoke(viewport,view,insets);padding(view,71,19,71,19);}
   // A new WebView must receive zeros so old CSS/visual viewport insets reset.
   insets.imeBottom=344;insets.systemBottom=344;
   WindowInsets forwarded=(WindowInsets)remaining.invoke(viewport,insets);
   check(forwarded!=insets&&!forwarded.isConsumed(),"Forwarded zero insets must still reach WebView after an inset change");
   if(sdk>=30){
    for(int kind:new int[]{WindowInsets.Type.systemBars(),WindowInsets.Type.displayCutout(),WindowInsets.Type.ime()}){
     android.graphics.Insets n=forwarded.getInsets(kind);check(n.left==0&&n.top==0&&n.right==0&&n.bottom==0,"App-handled inset still reaches WebView on SDK "+sdk);
    }
    check(forwarded.getInsets(WindowInsets.Type.systemGestures()).left==9,"Unrelated gesture insets were discarded");
    check(insets.getInsets(WindowInsets.Type.ime()).bottom==344,"Forwarding mutated the original window insets");
   }else check(forwarded.getSystemWindowInsetLeft()==0&&forwarded.getSystemWindowInsetTop()==0&&forwarded.getSystemWindowInsetRight()==0&&forwarded.getSystemWindowInsetBottom()==0,"Legacy handled bars/IME still reach WebView");
   if(sdk>=28)check(forwarded.getDisplayCutout()==null&&insets.getDisplayCutout()!=null,"Forwarded cutout not cleared or original changed");
   insets.imeBottom=0;insets.systemBottom=44;
   forwarded=(WindowInsets)remaining.invoke(viewport,insets);check(!forwarded.isConsumed(),"Closed-keyboard reset stopped before reaching WebView");
   // Rotation/focus reapplication must not replace the original cutout mode.
   fullscreen.invoke(viewport,true,false);fullscreen.invoke(viewport,false,false);
   if(sdk>=28)check(window.attrs.layoutInDisplayCutoutMode==2,"Leaving fullscreen did not restore the original cutout mode");
   if(sdk>=30)check(window.fits&&window.controller.shown==7,"Normal decor/system bars were not restored");
   else check(window.decor.visibility==8208,"Normal light system-bar appearance was not restored");
   check((window.flags&128)==0,"Fullscreen keep-awake flag leaked");
   insets.cutout=new DisplayCutout(49,0,0,11);apply.invoke(viewport,view,insets);if(sdk>=28)padding(view,49,24,33,44);else padding(view,17,24,33,44);
   insets.imeBottom=344;insets.systemBottom=344;apply.invoke(viewport,view,insets);
   if(sdk>=28)padding(view,49,24,33,344);else padding(view,17,24,33,344);
   insets.imeBottom=0;insets.systemBottom=44;apply.invoke(viewport,view,insets);
   if(sdk>=28)padding(view,49,24,33,44);else padding(view,17,24,33,44);
   fullscreen.invoke(viewport,true,true);fullscreen.invoke(viewport,false,true);if(sdk<30)check(window.decor.visibility==0,"Normal dark bars were not restored");
   if(sdk>=28){insets.cutout=null;fullscreen.invoke(viewport,true,true);apply.invoke(viewport,view,insets);padding(view,0,0,0,0);insets.imeBottom=344;insets.systemBottom=344;apply.invoke(viewport,view,insets);padding(view,0,0,0,344);insets.imeBottom=0;insets.systemBottom=0;apply.invoke(viewport,view,insets);padding(view,0,0,0,0);}
  }
  System.out.println("Fullscreen applies/restores native window geometry on APIs 26/27/28/29/30/33/35; cutouts stay symmetric, IME transitions pad only the bottom, and normal bars remain safe (Android API fakes, not a handset test)");
 }
 }'''
}
@unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK required for native viewport boundary regression')
class DesktopViewportTests(unittest.TestCase):
 def test_fullscreen_window_and_safe_content(self):
  with tempfile.TemporaryDirectory(prefix='pi-console-viewport-test-') as tmp:
   base=Path(tmp)
   for name,source in SDK.items():
    p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source)
   source=ROOT/'android/src/dev/piconsole/DesktopViewport.java'
   sources=([source] if source.exists() else [])+list(base.rglob('*.java'))
   result=subprocess.run(['javac','--release','8','-d',str(base),*map(str,sources)],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   for sdk in (26,27,28,29,30,33,35,36,37):
    with self.subTest(sdk=sdk):
     result=subprocess.run(['java','-cp',str(base),'dev.piconsole.DesktopViewportTest',str(sdk)],capture_output=True,text=True)
     self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
