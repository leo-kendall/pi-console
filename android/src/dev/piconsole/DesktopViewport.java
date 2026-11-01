// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import android.os.Build;
import android.view.DisplayCutout;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

/** Owns the desktop's immersive window and the WebView's safe content bounds. */
final class DesktopViewport {
 private final Window window;
 private final int originalCutoutMode;
 private boolean fullscreen;
 DesktopViewport(Window window){
  this.window=window;
  originalCutoutMode=Build.VERSION.SDK_INT>=28?window.getAttributes().layoutInDisplayCutoutMode:0;
 }
 void setFullscreen(boolean enabled,boolean dark){
  fullscreen=enabled;
  if(Build.VERSION.SDK_INT>=28){
   WindowManager.LayoutParams attributes=window.getAttributes();
   attributes.layoutInDisplayCutoutMode=enabled?WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES:originalCutoutMode;
   window.setAttributes(attributes);
  }
  if(Build.VERSION.SDK_INT>=30){
   window.setDecorFitsSystemWindows(!enabled);
   WindowInsetsController controller=window.getInsetsController();
   if(controller!=null){
    if(enabled){controller.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);controller.hide(WindowInsets.Type.systemBars());}
    else controller.show(WindowInsets.Type.systemBars());
   }
  }else{
   window.getDecorView().setSystemUiVisibility(enabled?View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|View.SYSTEM_UI_FLAG_LAYOUT_STABLE|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION:(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR));
  }
  if(enabled)window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
 }
 WindowInsets remainingInsets(WindowInsets insets){
  // Notify WebView of zero handled insets, so its CSS/visual viewport state resets.
  // Returning CONSUMED would stop that notification at the padded parent view.
  if(Build.VERSION.SDK_INT>=30){
   int handled=WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime();
   return new WindowInsets.Builder(insets).setInsets(handled,android.graphics.Insets.NONE).setDisplayCutout(null).build();
  }
  WindowInsets remaining=insets.replaceSystemWindowInsets(0,0,0,0);
  return Build.VERSION.SDK_INT>=28?remaining.consumeDisplayCutout():remaining;
 }
 void applyInsets(View view,WindowInsets insets){
  int left=0,top=0,right=0,bottom=0;
  if(!fullscreen){
   if(Build.VERSION.SDK_INT>=30){
    android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars());
    left=bars.left;top=bars.top;right=bars.right;bottom=bars.bottom;
   }else{left=insets.getSystemWindowInsetLeft();top=insets.getSystemWindowInsetTop();right=insets.getSystemWindowInsetRight();bottom=insets.getSystemWindowInsetBottom();}
  }
  if(Build.VERSION.SDK_INT>=28){
   DisplayCutout cutout=insets.getDisplayCutout();
   if(cutout!=null){
    if(fullscreen){
     // Equal opposite margins keep the desktop centered on the physical screen.
     // Hidden/transient bars must not shift the desktop when they appear.
     left=right=Math.max(cutout.getSafeInsetLeft(),cutout.getSafeInsetRight());
     top=bottom=Math.max(cutout.getSafeInsetTop(),cutout.getSafeInsetBottom());
    }else{
     left=Math.max(left,cutout.getSafeInsetLeft());top=Math.max(top,cutout.getSafeInsetTop());
     right=Math.max(right,cutout.getSafeInsetRight());bottom=Math.max(bottom,cutout.getSafeInsetBottom());
    }
   }
  }
  // Edge-to-edge windows receive IME occlusion instead of adjustResize fitting.
  // The IME overlaps bottom safety; reserve it once, without moving the top edge.
  if(Build.VERSION.SDK_INT>=30)bottom=Math.max(bottom,insets.getInsets(WindowInsets.Type.ime()).bottom);
  else if(fullscreen){
   // Older APIs combine bars and IME. Stable bars alone must not shift immersion.
   int systemBottom=insets.getSystemWindowInsetBottom();
   if(systemBottom>insets.getStableInsetBottom())bottom=Math.max(bottom,systemBottom);
  }
  view.setPadding(left,top,right,bottom);
 }
}
