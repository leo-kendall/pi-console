// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public final class WebActivity extends Activity {
    private WebView web;
    private TextView status;
    private boolean pageFailed;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        String start;
        try { start = UrlRules.validate(getIntent().getStringExtra("url")); }
        catch (IllegalArgumentException ex) { finish(); return; }
        LinearLayout root = Ui.column(this);
        root.setBackgroundColor(Ui.BG);
        root.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override public WindowInsets onApplyWindowInsets(View view, WindowInsets insets) {
                view.setPadding(0, insets.getSystemWindowInsetTop(), 0, insets.getSystemWindowInsetBottom());
                return insets;
            }
        });
        setContentView(root);
        TextView title = Ui.text(this, "‹  内置网页", 20, Ui.TEXT, true);
        title.setPadding(Ui.dp(this, 16), Ui.dp(this, 12), 0, Ui.dp(this, 8));
        title.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { onBackPressed(); } });
        root.addView(title);
        status = Ui.text(this, "正在加载…", 12, Ui.MUTED, false);
        status.setPadding(Ui.dp(this, 16), 0, Ui.dp(this, 16), Ui.dp(this, 8));
        root.addView(status);
        web = new WebView(this);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSafeBrowsingEnabled(true);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) return false;
                String address = request.getUrl().toString();
                try { UrlRules.validate(address); return false; }
                catch (IllegalArgumentException ex) { confirmExternal(address); return true; }
            }
            @Override public void onPageStarted(WebView view, String url, Bitmap icon) {
                pageFailed = false;
                status.setText("正在加载 · " + url);
            }
            @Override public void onPageFinished(WebView view, String url) { if (!pageFailed) status.setText(url); }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) { pageFailed = true; status.setText("页面加载失败，请检查连接后重试"); }
            }
        });
        root.addView(web, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        web.loadUrl(start);
    }

    private void confirmExternal(String address) {
        Uri uri = Uri.parse(address);
        String scheme = uri.getScheme();
        if (scheme == null || !(scheme.equalsIgnoreCase("intent") || scheme.equalsIgnoreCase("mailto")
                || scheme.equalsIgnoreCase("tel") || scheme.equalsIgnoreCase("geo"))) {
            Toast.makeText(this, "不支持此链接类型", Toast.LENGTH_LONG).show();
            return;
        }
        new AlertDialog.Builder(this).setTitle("打开外部应用？")
                .setMessage("这个链接将离开内置网页。")
                .setNegativeButton("取消", null)
                .setPositiveButton("打开", new android.content.DialogInterface.OnClickListener() {
                    @Override public void onClick(android.content.DialogInterface dialog, int which) {
                        try {
                            Intent intent = scheme.equalsIgnoreCase("intent")
                                    ? Intent.parseUri(address, Intent.URI_INTENT_SCHEME)
                                    : new Intent(Intent.ACTION_VIEW, uri);
                            intent.addCategory(Intent.CATEGORY_BROWSABLE);
                            intent.setComponent(null);
                            intent.setSelector(null);
                            startActivity(intent);
                        } catch (ActivityNotFoundException ex) {
                            Toast.makeText(WebActivity.this, "没有可打开此链接的应用", Toast.LENGTH_LONG).show();
                        } catch (Exception ex) {
                            Toast.makeText(WebActivity.this, "无法打开此链接", Toast.LENGTH_LONG).show();
                        }
                    }
                }).show();
    }

    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    @Override protected void onPause() { if (web != null) web.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); if (web != null) web.onResume(); }
    @Override protected void onDestroy() {
        if (web != null) { web.stopLoading(); web.destroy(); web = null; }
        super.onDestroy();
    }
}
