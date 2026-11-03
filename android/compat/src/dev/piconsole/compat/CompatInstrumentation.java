// SPDX-License-Identifier: Apache-2.0
package dev.piconsole.compat;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageInfo;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Point;
import android.graphics.Rect;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.PixelCopy;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/** Runs in the installed target app process; no JUnit, Gradle or external server. */
public final class CompatInstrumentation extends Instrumentation {
    private Activity activity;
    private WebView web;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final AtomicInteger consoleErrors = new AtomicInteger();
    private final JSONObject report = new JSONObject();
    private final JSONArray scenarios = new JSONArray();
    private String geometryScript;
    private boolean gestureBack;

    private interface Action { void run() throws Exception; }

    @Override public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        gestureBack = arguments != null && "true".equals(arguments.getString("gestureBack"));
        start();
    }

    private static void check(boolean value, String code) {
        if (!value) throw new AssertionError(code);
    }

    private static void await(CountDownLatch latch, String code) throws Exception {
        check(latch.await(15, TimeUnit.SECONDS), code);
    }

    // Post and bound the wait; runOnMainSync itself has no timeout on a hung UI.
    private void main(Action action) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<Throwable> error = new AtomicReference<>();
        ui.post(() -> {
            try { action.run(); } catch (Throwable value) { error.set(value); }
            finally { done.countDown(); }
        });
        await(done, "main-thread-timeout");
        if (error.get() instanceof AssertionError) throw (AssertionError)error.get();
        if (error.get() != null) throw new AssertionError("main-thread-action", error.get());
    }

    private Object js(String expression) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> response = new AtomicReference<>();
        main(() -> web.evaluateJavascript("(()=>{try{return {ok:true,value:(" + expression
                + ")};}catch(e){return {ok:false};}})()", value -> {
                    response.set(value); done.countDown();
                }));
        await(done, "javascript-callback-timeout");
        JSONObject result = new JSONObject(response.get());
        check(result.optBoolean("ok"), "javascript-evaluation");
        return result.opt("value");
    }

    private void waitJs(String condition, String code) throws Exception {
        long deadline = SystemClock.uptimeMillis() + 20000;
        while (SystemClock.uptimeMillis() < deadline) {
            if (Boolean.TRUE.equals(js(condition))) return;
            Thread.sleep(100);
        }
        throw new AssertionError(code);
    }

    private JSONObject asyncJs(String expression) throws Exception {
        js("(()=>{window.__compatAsync={done:false};Promise.resolve(" + expression
            + ").then(value=>window.__compatAsync={done:true,value},"
            + "()=>window.__compatAsync={done:true,error:true});return true;})()");
        waitJs("window.__compatAsync.done", "native-bridge-timeout");
        JSONObject result = (JSONObject) js("window.__compatAsync");
        check(!result.optBoolean("error"), "native-bridge-failed");
        return result.getJSONObject("value");
    }

    private String asset(String name) throws Exception {
        try (InputStream in = getContext().getAssets().open(name);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
            return out.toString("UTF-8");
        }
    }

    private WebView findWeb(View root) {
        if (root instanceof WebView) return (WebView) root;
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int i = 0; i < group.getChildCount(); i++) {
                WebView found = findWeb(group.getChildAt(i));
                if (found != null) return found;
            }
        }
        return null;
    }

    private boolean hasUpdateText(View root) {
        if (root instanceof TextView && ((TextView)root).getText().length() > 10) return true;
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup)root;
            for (int i = 0; i < group.getChildCount(); i++)
                if (hasUpdateText(group.getChildAt(i))) return true;
        }
        return false;
    }

    private boolean awaitAppReady() throws Exception {
        long deadline = SystemClock.uptimeMillis() + 40000;
        while (SystemClock.uptimeMillis() < deadline) {
            AtomicInteger state = new AtomicInteger();
            main(() -> {
                View root = activity.getWindow().getDecorView();
                check(root.findViewWithTag("webview-load-failed") == null, "app-startup-failure-is-not-provider-recovery");
                View recovery = root.findViewWithTag("webview-update-required");
                if (recovery != null && recovery.isShown()) {
                    View settings = root.findViewWithTag("webview-open-settings");
                    View retry = root.findViewWithTag("webview-retry");
                    check(hasUpdateText(recovery), "native-update-message-missing");
                    check(settings != null && settings.isShown() && settings.isClickable(), "native-update-settings-control");
                    check(retry != null && retry.isShown() && retry.isClickable(), "native-update-retry-control");
                    state.set(2);
                } else {
                    // Read the target's real readiness gate; initial loading is not recovery.
                    java.lang.reflect.Field ready = activity.getClass().getDeclaredField("webReady");
                    ready.setAccessible(true);
                    if (ready.getBoolean(activity)) state.set(1);
                }
            });
            if (state.get() == 1) return true;
            if (state.get() == 2) return false;
            Thread.sleep(100);
        }
        throw new AssertionError("app-readiness-timeout");
    }

    private void recordProvider() throws Exception {
        try {
            PackageInfo provider = WebView.getCurrentWebViewPackage();
            if (provider != null) {
                report.put("webview", provider.packageName + " " + provider.versionName);
                return;
            }
        } catch (RuntimeException | LinkageError ignored) { }
        report.put("webview", JSONObject.NULL).put("webview_provider_available", false);
    }

    private static JSONArray numbers(int... values) {
        JSONArray result = new JSONArray();
        for (int value : values) result.put(Math.max(-131072, Math.min(131072, value)));
        return result;
    }

    private JSONObject nativeGeometry(boolean fullscreen) throws Exception {
        JSONObject result = new JSONObject();
        main(() -> {
            View decor = activity.getWindow().getDecorView();
            View parent = (View) web.getParent();
            int[] location = new int[2];
            web.getLocationInWindow(location);
            int l = parent.getPaddingLeft(), t = parent.getPaddingTop();
            int r = parent.getPaddingRight(), b = parent.getPaddingBottom();
            check(web.getWidth() > 0 && web.getHeight() > 0, "native-web-size");
            check(location[0] >= 0 && location[1] >= 0
                && location[0] + web.getWidth() <= decor.getWidth() + 2
                && location[1] + web.getHeight() <= decor.getHeight() + 2, "native-web-window-bounds");
            check(l >= 0 && t >= 0 && r >= 0 && b >= 0, "negative-native-insets");
            if (fullscreen) check(l == r && t == b, "unbalanced-fullscreen-cutout-margins");
            boolean keepScreen = (activity.getWindow().getAttributes().flags
                & WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) != 0;
            check(keepScreen == fullscreen, "native-fullscreen-state");
            if (Build.VERSION.SDK_INT >= 30) {
                android.view.WindowInsetsController controller=activity.getWindow().getInsetsController();
                check(controller!=null,"native-insets-controller-missing");
                int behavior=controller.getSystemBarsBehavior();
                result.put("systemBarsBehavior",behavior);
                if(fullscreen) check(behavior==android.view.WindowInsetsController.BEHAVIOR_DEFAULT,
                    "fullscreen-blocks-system-back-gestures");
            }
            WindowInsets insets = decor.getRootWindowInsets();
            result.put("web", numbers(web.getWidth(), web.getHeight()));
            result.put("window", numbers(decor.getWidth(), decor.getHeight()));
            result.put("inWindow", numbers(location[0], location[1]));
            result.put("parentPadding", numbers(l, t, r, b));
            result.put("hardwareAccelerated", web.isHardwareAccelerated());
            result.put("layerType", web.getLayerType());
            if (Build.VERSION.SDK_INT >= 28)
                result.put("cutoutMode", activity.getWindow().getAttributes().layoutInDisplayCutoutMode);
            result.put("keepScreenOn", keepScreen);
            if (insets != null) {
                result.put("systemInsets", numbers(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom()));
                if (Build.VERSION.SDK_INT >= 30) {
                    result.put("systemBarsVisible", insets.isVisible(WindowInsets.Type.systemBars()));
                    result.put("statusBarVisible", insets.isVisible(WindowInsets.Type.statusBars()));
                    result.put("navigationBarVisible", insets.isVisible(WindowInsets.Type.navigationBars()));
                }
                if (!fullscreen) {
                    int el = insets.getSystemWindowInsetLeft(), et = insets.getSystemWindowInsetTop();
                    int er = insets.getSystemWindowInsetRight(), eb = insets.getSystemWindowInsetBottom();
                    if (Build.VERSION.SDK_INT >= 30) {
                        android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                        el=bars.left; et=bars.top; er=bars.right;
                        eb=Math.max(bars.bottom,insets.getInsets(WindowInsets.Type.ime()).bottom);
                    }
                    if (Build.VERSION.SDK_INT >= 28 && insets.getDisplayCutout() != null) {
                        android.view.DisplayCutout cutout = insets.getDisplayCutout();
                        el=Math.max(el,cutout.getSafeInsetLeft()); et=Math.max(et,cutout.getSafeInsetTop());
                        er=Math.max(er,cutout.getSafeInsetRight()); eb=Math.max(eb,cutout.getSafeInsetBottom());
                    }
                    // Decor fitting may already reserve bars outside this parent
                    // (API33), while enforced edge-to-edge leaves all reservation
                    // to the parent (API35+). Count each safe edge exactly once.
                    int[] parentLocation = new int[2]; parent.getLocationInWindow(parentLocation);
                    el=Math.max(0,el-parentLocation[0]); et=Math.max(0,et-parentLocation[1]);
                    er=Math.max(0,er-(decor.getWidth()-parentLocation[0]-parent.getWidth()));
                    eb=Math.max(0,eb-(decor.getHeight()-parentLocation[1]-parent.getHeight()));
                    result.put("parent", numbers(parentLocation[0],parentLocation[1],parent.getWidth(),parent.getHeight()));
                    result.put("expectedNormalPadding", numbers(el,et,er,eb));
                    check(l==el && t==et && r==er && b==eb, "normal-padding-current-system-insets");
                    check(web.getWidth()==parent.getWidth()-l-r && web.getHeight()==parent.getHeight()-t-b,
                        "normal-content-fills-safe-parent");
                }
            }
            Point screen = new Point();
            web.getDisplay().getRealSize(screen);
            result.put("display", numbers(screen.x, screen.y));
        });
        return result;
    }

    private JSONObject pixelColor(JSONObject geometry) throws Exception {
        JSONArray frame = geometry.getJSONArray("frame"), viewport = geometry.getJSONArray("viewport");
        JSONArray overlay = geometry.getJSONArray("overlay");
        CountDownLatch done = new CountDownLatch(1);
        JSONObject result = new JSONObject();
        AtomicReference<Throwable> error = new AtomicReference<>();
        main(() -> {
            int[] location = new int[2];
            web.getLocationInWindow(location);
            double sx = web.getWidth() / viewport.getDouble(0), sy = web.getHeight() / viewport.getDouble(1);
            Rect source = new Rect((int)Math.round(location[0] + frame.getDouble(0) * sx),
                (int)Math.round(location[1] + frame.getDouble(1) * sy),
                (int)Math.round(location[0] + (frame.getDouble(0) + frame.getDouble(2)) * sx),
                (int)Math.round(location[1] + (frame.getDouble(1) + frame.getDouble(3)) * sy));
            View decor = activity.getWindow().getDecorView();
            Rect visible = new Rect(Math.max(0, location[0]), Math.max(0, location[1]),
                Math.min(decor.getWidth(), location[0] + web.getWidth()),
                Math.min(decor.getHeight(), location[1] + web.getHeight()));
            check(source.intersect(visible) && source.width() > 0 && source.height() > 0, "pixelcopy-visible-frame");
            Bitmap bitmap = Bitmap.createBitmap(160, 100, Bitmap.Config.ARGB_8888);
            try {
                PixelCopy.request(activity.getWindow(), source, bitmap, status -> {
                    try {
                        result.put("status", status);
                        check(status == PixelCopy.SUCCESS, "pixelcopy-status");
                        int matched = 0, samples = 0, excludedOverlay = 0;
                        // Includes old/new resize boundary, center, right edge and all quadrants.
                        for (int x : new int[]{8, 40, 80, 92, 112, 144, 157}) {
                            for (int y : new int[]{10, 25, 55, 75, 90}) {
                                double cx = (source.left + source.width() * (x + .5) / 160 - location[0]) / sx;
                                double cy = (source.top + source.height() * (y + .5) / 100 - location[1]) / sy;
                                if (overlay.getDouble(2) > 0 && overlay.getDouble(3) > 0
                                    && cx >= overlay.getDouble(0) && cx <= overlay.getDouble(0) + overlay.getDouble(2)
                                    && cy >= overlay.getDouble(1) && cy <= overlay.getDouble(1) + overlay.getDouble(3)) {
                                    excludedOverlay++; continue;
                                }
                                int color = bitmap.getPixel(x, y);
                                int[] expected = x < 53 ? new int[]{31,177,107}
                                    : x < 106 ? new int[]{40,120,220} : new int[]{220,130,40};
                                samples++;
                                if (Math.abs(Color.red(color) - expected[0]) <= 12
                                    && Math.abs(Color.green(color) - expected[1]) <= 12
                                    && Math.abs(Color.blue(color) - expected[2]) <= 12) matched++;
                            }
                        }
                        result.put("matched", matched).put("samples", samples).put("excludedControlSamples", excludedOverlay);
                        check(samples >= 30 && matched == samples, "presented-frame-color");
                    } catch (Throwable value) { error.set(value); }
                    finally { bitmap.recycle(); done.countDown(); }
                }, ui);
            } catch (Throwable value) {
                bitmap.recycle(); throw new AssertionError("pixelcopy-request", value);
            }
        });
        await(done, "pixelcopy-timeout");
        if (error.get() instanceof AssertionError) throw (AssertionError)error.get();
        if (error.get() != null) throw new AssertionError("pixelcopy-frame", error.get());
        return result;
    }

    private JSONObject scenario(String name, boolean fullscreen) throws Exception {
        // Readiness is condition-based; the short settling window also allows bars to animate.
        waitJs("Boolean(desktopClient&&desktopClient.getDisplay().getWidth())"
            + "&&!$('desktop').getAnimations().some(a=>a.playState==='running')", "desktop-ready");
        Thread.sleep(800);
        js("(()=>{const d=desktopClient.getDisplay(),c=d.getCursorLayer();c.resize(16,16);"
            + "d.cursorHotspotX=3;d.cursorHotspotY=4;d.showCursor(true);"
            + "d.moveCursor(Math.floor(d.getWidth()/2),Math.floor(d.getHeight()/2));"
            + "$('toast').hidden=true;return true;})()");
        JSONObject result = new JSONObject().put("name", name);
        scenarios.put(result); // Preserve completed geometry if a later assertion fails.
        JSONObject geometry = (JSONObject) js(geometryScript);
        result.put("javascript", geometry);
        for (String key : new String[]{"fit", "centered", "contentAligned", "cursorAligned"})
            check(geometry.getBoolean(key), name + "-" + key);
        check(geometry.getBoolean("fullscreen") == fullscreen, name + "-fullscreen");
        if (fullscreen) check(Boolean.TRUE.equals(js("$('desk-controls').hidden&&!document.body.classList.contains('desktop-controls-open')")),
            "fullscreen-has-visible-controls");
        check(geometry.getInt("errors") == 0 && consoleErrors.get() == 0, "javascript-errors");
        result.put("native", nativeGeometry(fullscreen));
        js("(()=>{desktopClient.getDisplay().showCursor(false);return true;})()");
        Thread.sleep(100);
        // Exercise the app's existing Pi.local/native DesktopProbe bridge as well.
        JSONObject probe = asyncJs("desktopSample(desktopClient)");
        check(probe.getJSONObject("window").optBoolean("available"), "native-desktop-probe");
        result.put("nativeProbe", probe.getJSONObject("window"));
        result.put("pixels", pixelColor(geometry));
        return result;
    }

    private void selectResolution(String value) throws Exception {
        js("(()=>{$('desk-display').click();return true;})()");
        waitJs("$('sheet').open&&Boolean($('desktop-size-choice')&&$('desktop-ratio-choice')"
            + "&&$('desktop-custom-width')&&$('desktop-custom-height')&&$('desktop-display-apply'))", "resolution-selectors");
        js("(()=>{$('desktop-size-choice').value=" + JSONObject.quote(value)
            + ";$('desktop-size-choice').dispatchEvent(new Event('change'));$('desktop-display-apply').click();return true;})()");
        waitJs("!$('sheet').open&&$('resolution').value===" + JSONObject.quote(value), "fixed-resolution-setting");
    }

    private void waitNativeFullscreen(boolean expected) throws Exception {
        long deadline = SystemClock.uptimeMillis() + 10000;
        while (SystemClock.uptimeMillis() < deadline) {
            AtomicInteger matched = new AtomicInteger();
            main(() -> matched.set(((activity.getWindow().getAttributes().flags
                & WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) != 0) == expected ? 1 : 0));
            if (matched.get() == 1) return;
            Thread.sleep(50);
        }
        throw new AssertionError("native-fullscreen-transition-timeout");
    }

    private void waitInputFocus() throws Exception {
        long deadline = SystemClock.uptimeMillis() + 10000;
        while (SystemClock.uptimeMillis() < deadline) {
            AtomicInteger focus = new AtomicInteger();
            main(() -> {
                report.put("backWindowFocused", activity.hasWindowFocus());
                report.put("backDisplayState", activity.getWindow().getDecorView().getDisplay().getState());
                android.app.KeyguardManager keyguard=(android.app.KeyguardManager)activity.getSystemService(android.content.Context.KEYGUARD_SERVICE);
                report.put("backKeyguardLocked", keyguard!=null&&keyguard.isKeyguardLocked());
                if(activity.hasWindowFocus()) focus.set(1);
            });
            if(focus.get()==1) return;
            Thread.sleep(100);
        }
        recordFocusedWindow();
        throw new AssertionError("back-input-target-window-not-focused");
    }

    private void recordFocusedWindow() throws Exception {
        // Identify a focus blocker without exporting window contents or clicking it.
        String windows;
        try (InputStream stream = new android.os.ParcelFileDescriptor.AutoCloseInputStream(
                getUiAutomation().executeShellCommand("dumpsys window displays"));
             ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096]; int count;
            while((count=stream.read(buffer))!=-1) {
                check(bytes.size()+count<=2*1024*1024,"window-diagnostic-too-large");
                bytes.write(buffer,0,count);
            }
            windows=bytes.toString("UTF-8");
        }
        String focused="";
        for(String line:windows.split("\n")) if(line.contains("mCurrentFocus=")) {focused=line;break;}
        boolean tutorial=focused.contains("ImmersiveModeConfirmation");
        report.put("backFocusedWindowKind",tutorial?"immersive-tutorial":focused.contains("dev.piconsole/")?"app"
            :focused.isEmpty()?"unavailable":focused.contains("mCurrentFocus=null")?"none":"other");
        report.put("immersiveTutorialObserved",tutorial);
    }

    private void pressSystemBack() throws Exception {
        waitInputFocus();
        if (!gestureBack) { sendKeyDownUpSync(android.view.KeyEvent.KEYCODE_BACK); recordBackState(); return; }
        AtomicInteger width = new AtomicInteger(), height = new AtomicInteger();
        main(() -> {width.set(activity.getWindow().getDecorView().getWidth());height.set(activity.getWindow().getDecorView().getHeight());});
        String command = "input swipe 1 " + height.get()/2 + " " + width.get()/3 + " " + height.get()/2 + " 350";
        try (InputStream stream = new android.os.ParcelFileDescriptor.AutoCloseInputStream(getUiAutomation().executeShellCommand(command))) {
            byte[] buffer = new byte[128]; while (stream.read(buffer) != -1) { }
        }
        recordBackState();
    }

    private void recordBackState() throws Exception {
        Thread.sleep(250);
        report.put("backState", js("({calls:window.__backCalls,fullscreen:fullscreenDesktop,controlsOpen:document.body.classList.contains('desktop-controls-open'),buttonHidden:$('desk-controls').hidden,clientAlive:Boolean(desktopClient),sheetOpen:$('sheet').open})"));
    }

    private void controlsBackFlow() throws Exception {
        waitJs("fullscreenDesktop&&$('desk-controls').hidden", "fullscreen-controls-not-hidden");
        js("(()=>{window.__backClient=desktopClient;window.__backKeyCount=__compatKeyEvents;window.__backCalls=0;const original=window.appBack;window.appBack=()=>{window.__backCalls++;return original();};return true;})()");
        pressSystemBack();
        waitJs("fullscreenDesktop&&!$('desk-controls').hidden&&document.body.classList.contains('desktop-controls-open')",
            "native-back-must-show-controls");
        js("(()=>{$('desk-display').click();return true;})()");
        waitJs("$('sheet').open", "native-back-modal-setup");
        pressSystemBack();
        waitJs("!$('sheet').open&&fullscreenDesktop&&document.body.classList.contains('desktop-controls-open')",
            "native-back-must-close-modal-first");
        js("(()=>{$('desk-controls').click();return true;})()");
        waitJs("fullscreenDesktop&&$('desk-controls').hidden&&$('desk-controls').getClientRects().length===0",
            "collapse-must-remove-control-hit-area");
        pressSystemBack();
        waitJs("document.body.classList.contains('desktop-controls-open')", "native-back-must-reopen-controls");
        pressSystemBack();
        waitJs("!fullscreenDesktop&&desktopClient===window.__backClient", "second-native-back-must-exit-fullscreen-only");
        waitNativeFullscreen(false);
        nativeGeometry(false);
        Thread.sleep(100);
        check(Boolean.TRUE.equals(js("__compatKeyEvents===window.__backKeyCount")), "system-back-forwarded-to-remote");
        report.put("controlsBackNavigation", true).put("systemBackForwarded", false).put("backInput", gestureBack?"system-gesture":"key");
        js("(()=>{$('desk-fullscreen').click();return true;})()");
        waitJs("fullscreenDesktop&&$('desk-controls').hidden", "fullscreen-reentry-must-hide-controls");
    }

    private void rotate(int requested, int configuration, boolean landscape) throws Exception {
        main(() -> activity.setRequestedOrientation(requested));
        long deadline = SystemClock.uptimeMillis() + 15000;
        while (SystemClock.uptimeMillis() < deadline) {
            AtomicInteger orientation = new AtomicInteger();
            main(() -> orientation.set(activity.getResources().getConfiguration().orientation));
            if (orientation.get() == configuration) {
                waitJs("isDesktopLandscape()===" + landscape, "javascript-orientation");
                return;
            }
            Thread.sleep(100);
        }
        throw new AssertionError("native-orientation-timeout");
    }

    @Override public void onStart() {
        boolean passed = false;
        try {
            report.put("sdk", Build.VERSION.SDK_INT).put("scenarios", scenarios)
                .put("full_ui_tested", false).put("recovery_ui_tested", false);
            PackageInfo app = getTargetContext().getPackageManager().getPackageInfo("dev.piconsole", 0);
            report.put("appVersion", app.versionName).put("appVersionCode", app.versionCode);
            Intent launch = new Intent(Intent.ACTION_MAIN).setComponent(
                new ComponentName("dev.piconsole", "dev.piconsole.MainActivity"));
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            activity = startActivitySync(launch);
            main(() -> {
                web = findWeb(activity.getWindow().getDecorView());
                if (web != null) web.setWebChromeClient(new WebChromeClient() {
                    @Override public boolean onConsoleMessage(ConsoleMessage message) {
                        if (message.messageLevel() == ConsoleMessage.MessageLevel.ERROR) consoleErrors.incrementAndGet();
                        return true; // Never retain page text, URLs or credentials in artifacts.
                    }
                });
            });
            boolean fullUiReady = awaitAppReady();
            recordProvider();
            if (!fullUiReady) {
                scenarios.put(new JSONObject().put("name", "native-webview-update-recovery")
                    .put("native_update_message", true).put("settings_control", true).put("retry_control", true));
                report.put("result_kind", "requires-webview-update").put("recovery_ui_tested", true);
                passed = true;
                return;
            }
            check(web != null, "target-webview-missing");
            waitJs("document.readyState==='complete'&&typeof fitDesktop==='function'"
                + "&&typeof Guacamole!=='undefined'&&typeof local==='function'"
                + "&&typeof isDesktopLandscape==='function'&&typeof desktopSample==='function'"
                + "&&Boolean($('resolution')&&$('desktop-ratio')&&$('desktop-display-options'))", "app-javascript-features");
            JSONObject settings = asyncJs("local('serverSettings')");
            check(!settings.optBoolean("paired") && settings.optString("url").isEmpty(), "first-launch-not-offline");
            report.put("offlineFirstLaunch", true);
            geometryScript = asset("geometry.js");
            rotate(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT, Configuration.ORIENTATION_PORTRAIT, false);
            // Listener installation and synthetic transport occur only inside this test APK.
            String setup = asset("setup.js");
            js("(()=>{" + setup + "\nreturn true;})()");
            waitJs("Boolean(desktopClient&&desktopClient.getDisplay().getWidth()===1280)", "initial-frame");
            check(Boolean.TRUE.equals(js("window.__compatOpened.width===1280&&window.__compatOpened.height===800")),
                "initial-open-dimensions");
            JSONObject normal = scenario("portrait-1280", false).getJSONObject("native");
            selectResolution("2560,1440");
            waitJs("window.__compatSizes.some(s=>s[0]===2560&&s[1]===1440)", "outbound-2560-request");
            waitJs("desktopClient.getDisplay().getWidth()===2560", "resized-frame");
            scenario("portrait-2560", false);
            js("(()=>{$('desk-fullscreen').click();return true;})()");
            scenario("fullscreen-portrait-2560", true);
            controlsBackFlow();
            rotate(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE, Configuration.ORIENTATION_LANDSCAPE, true);
            scenario("fullscreen-landscape-2560", true);
            rotate(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT, Configuration.ORIENTATION_PORTRAIT, false);
            JSONObject restored = scenario("restored-portrait-2560", false).getJSONObject("native");
            // Rotation can change Android's navigation-bar height. Verify the
            // restored policy against CURRENT framework insets, not stale pixels.
            if (Build.VERSION.SDK_INT >= 28)
                check(normal.getInt("cutoutMode")==restored.getInt("cutoutMode"), "normal-cutout-mode-not-restored");
            if (Build.VERSION.SDK_INT >= 30) {
                check(normal.getBoolean("statusBarVisible")==restored.getBoolean("statusBarVisible"),
                    "normal-status-bar-policy-not-restored");
                check(normal.getBoolean("navigationBarVisible")==restored.getBoolean("navigationBarVisible"),
                    "normal-navigation-bar-policy-not-restored");
            }
            selectResolution("1920,1080");
            waitJs("window.__compatSizes.some(s=>s[0]===1920&&s[1]===1080)", "outbound-1920-request");
            waitJs("desktopClient.getDisplay().getWidth()===1920&&desktopClient.getDisplay().getHeight()===1080",
                "fixed-resolution-acknowledgement");
            report.put("requestedSizes", js("window.__compatSizes"));
            report.put("resolutionSelectors", true).put("syntheticTransport", true);
            check(Boolean.TRUE.equals(js("window.__compatTransportCalls>0&&window.__compatErrors===0")), "transport-or-js-errors");
            js("(()=>{stopDesktop();pauseApp();return true;})()");
            nativeGeometry(false);
            check(consoleErrors.get() == 0, "console-errors");
            report.put("result_kind", "full-ui").put("full_ui_tested", true);
            passed = true;
        } catch (Throwable error) {
            // Fixed assertion codes only. Do not export screenshots, page contents or exception stacks.
            try { report.put("failure", error instanceof AssertionError ? String.valueOf(error.getMessage()) : error.getClass().getSimpleName()); }
            catch (Exception ignored) { }
        } finally {
            try { report.put("passed", passed); } catch (Exception ignored) { }
            Bundle results = new Bundle();
            results.putString("compat_success", String.valueOf(passed));
            results.putString("compat_report", report.toString());
            finish(passed ? Activity.RESULT_OK : Activity.RESULT_CANCELED, results);
        }
    }
}
