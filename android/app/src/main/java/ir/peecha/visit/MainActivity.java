// MainActivity.java - پیچا ویزیت | اپ اندروید
// ════════════════════════════════════════════════
// اپ موبایل (pwa_client) را از داخل خود APK اجرا می‌کند.
// صفحات از دامنهٔ امن https://appassets.androidplatform.net بارگذاری می‌شوند
// تا دوربین و GPS (که فقط روی مبدأ امن کار می‌کنند) فعال باشند؛
// درخواست‌های API از طریق PeechaNative (کد بومی) به سرور داخلی
// (http://IP:5000) می‌روند تا محدودیت‌های شبکهٔ WebView مانع نشوند.
// ════════════════════════════════════════════════
package ir.peecha.visit;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.WindowInsets;
import android.widget.FrameLayout;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.webkit.WebViewAssetLoader;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {

    private static final String APP_HOST  = "appassets.androidplatform.net";
    private static final String START_URL = "https://" + APP_HOST + "/assets/index.html";
    private static final int    REQ_PERMS = 1001;

    private WebView webView;
    private WebViewAssetLoader assetLoader;

    // درخواست‌های مجوز صفحه که منتظر پاسخ کاربر به مجوز اندروید هستند
    private PermissionRequest pendingMediaRequest;
    private GeolocationPermissions.Callback pendingGeoCallback;
    private String pendingGeoOrigin;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        assetLoader = new WebViewAssetLoader.Builder()
                .setDomain(APP_HOST)
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        webView = new WebView(this);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#020025"));   // رنگ پشت نوار وضعیت
        root.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);
        applySystemBarInsets(root);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // localStorage
        s.setDatabaseEnabled(true);            // IndexedDB (صف آفلاین)
        s.setGeolocationEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false); // پیش‌نمایش زندهٔ دوربین
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        // صفحه روی https است ولی سرور داخلی روی http
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                return assetLoader.shouldInterceptRequest(req.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri uri = req.getUrl();
                if (APP_HOST.equals(uri.getHost())) return false;
                // لینک‌های بیرونی (مثل peecha.ir) در مرورگر گوشی باز شوند
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (Exception ignored) { }
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> handleMediaRequest(request));
            }

            @Override
            public void onPermissionRequestCanceled(PermissionRequest request) {
                if (request == pendingMediaRequest) pendingMediaRequest = null;
            }

            @Override
            public void onGeolocationPermissionsShowPrompt(String origin,
                                                           GeolocationPermissions.Callback callback) {
                handleGeoRequest(origin, callback);
            }
        });

        webView.addJavascriptInterface(new NativeHttp(), "PeechaNative");

        // مجوزها را از ابتدا بگیریم تا اولین ثبت ویزیت معطل نشود
        requestMissing(Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION);

        if (savedInstanceState != null) webView.restoreState(savedInstanceState);
        else webView.loadUrl(START_URL);
    }

    // ── نوار وضعیت / ناوبری / کیبورد ──
    // اندروید ۱۵ (targetSdk 35) محتوا را زیر نوار وضعیت می‌کشد؛ آن فضا را
    // به‌صورت padding خالی می‌گذاریم تا هدر اپ زیر ساعت و باتری پنهان نشود.
    // کیبورد هم همین‌جا حساب می‌شود (جای adjustResize).
    private void applySystemBarInsets(FrameLayout root) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return;   // نسخه‌های قدیمی خودشان مدیریت می‌کنند
        getWindow().setDecorFitsSystemWindows(false);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            Insets ime  = insets.getInsets(WindowInsets.Type.ime());
            v.setPadding(bars.left, bars.top, bars.right, Math.max(bars.bottom, ime.bottom));
            return WindowInsets.CONSUMED;
        });
    }

    // ── درخواست HTTP بومی (env.js آن را جایگزین fetch می‌کند) ──
    private class NativeHttp {
        private final ExecutorService pool = Executors.newFixedThreadPool(3);

        // برند، مدل، نسخهٔ اندروید و نسخهٔ اپ — همراه هر درخواست به سرور فرستاده می‌شود
        @JavascriptInterface
        public String deviceInfo() {
            String app = "";
            try { app = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; }
            catch (Exception ignored) { }
            String brand = Build.MANUFACTURER == null ? "" : Build.MANUFACTURER;
            return (brand.isEmpty() ? "" : brand.substring(0, 1).toUpperCase() + brand.substring(1) + " ")
                    + Build.MODEL + " · Android " + Build.VERSION.RELEASE + " · app " + app;
        }

        @JavascriptInterface
        public void request(String id, String method, String url, String headersJson,
                            String body, int timeoutMs) {
            pool.execute(() -> {
                JSONObject res = new JSONObject();
                HttpURLConnection conn = null;
                try {
                    res.put("id", id);
                    URL u = new URL(url);
                    String proto = u.getProtocol();
                    if (!"http".equals(proto) && !"https".equals(proto))
                        throw new IllegalArgumentException("unsupported scheme");

                    conn = (HttpURLConnection) u.openConnection();
                    conn.setRequestMethod(method);
                    conn.setConnectTimeout(Math.min(timeoutMs, 10000));
                    conn.setReadTimeout(timeoutMs);
                    conn.setUseCaches(false);
                    JSONObject headers = new JSONObject(headersJson == null || headersJson.isEmpty() ? "{}" : headersJson);
                    for (Iterator<String> it = headers.keys(); it.hasNext(); ) {
                        String k = it.next();
                        conn.setRequestProperty(k, headers.optString(k));
                    }
                    if (body != null && !body.isEmpty() && !"GET".equals(method)) {
                        byte[] data = body.getBytes(StandardCharsets.UTF_8);
                        conn.setDoOutput(true);
                        conn.setFixedLengthStreamingMode(data.length);
                        try (OutputStream os = conn.getOutputStream()) { os.write(data); }
                    }
                    int status = conn.getResponseCode();
                    InputStream is = status >= 400 ? conn.getErrorStream() : conn.getInputStream();
                    res.put("status", status);
                    res.put("type", conn.getContentType());
                    res.put("body", is == null ? "" : readAll(is));
                } catch (Exception e) {
                    try { res.put("error", e.getClass().getSimpleName() + ": " + e.getMessage()); }
                    catch (Exception ignored) { }
                } finally {
                    if (conn != null) conn.disconnect();
                }
                String js = "window.__pvNativeDone(" + JSONObject.quote(res.toString()) + ")";
                runOnUiThread(() -> { if (webView != null) webView.evaluateJavascript(js, null); });
            });
        }
    }

    private static String readAll(InputStream is) throws java.io.IOException {
        try (InputStream in = is) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return out.toString("UTF-8");
        }
    }

    // ── دوربین ──
    private void handleMediaRequest(PermissionRequest request) {
        if (!APP_HOST.equals(request.getOrigin().getHost())) { request.deny(); return; }
        List<String> grant = new ArrayList<>();
        for (String r : request.getResources()) {
            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r)) grant.add(r);
        }
        if (grant.isEmpty()) { request.deny(); return; }
        if (has(Manifest.permission.CAMERA)) {
            request.grant(grant.toArray(new String[0]));
        } else {
            pendingMediaRequest = request;
            requestMissing(Manifest.permission.CAMERA);
        }
    }

    // ── GPS ──
    private void handleGeoRequest(String origin, GeolocationPermissions.Callback callback) {
        if (!Uri.parse(origin).getHost().equals(APP_HOST)) { callback.invoke(origin, false, false); return; }
        if (has(Manifest.permission.ACCESS_FINE_LOCATION) || has(Manifest.permission.ACCESS_COARSE_LOCATION)) {
            callback.invoke(origin, true, false);
        } else {
            pendingGeoOrigin = origin;
            pendingGeoCallback = callback;
            requestMissing(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION);
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        if (pendingMediaRequest != null) {
            if (has(Manifest.permission.CAMERA))
                pendingMediaRequest.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            else
                pendingMediaRequest.deny();
            pendingMediaRequest = null;
        }
        if (pendingGeoCallback != null) {
            boolean ok = has(Manifest.permission.ACCESS_FINE_LOCATION)
                    || has(Manifest.permission.ACCESS_COARSE_LOCATION);
            pendingGeoCallback.invoke(pendingGeoOrigin, ok, false);
            pendingGeoCallback = null;
            pendingGeoOrigin = null;
        }
    }

    private boolean has(String perm) {
        return checkSelfPermission(perm) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestMissing(String... perms) {
        List<String> missing = new ArrayList<>();
        for (String p : perms) if (!has(p)) missing.add(p);
        if (!missing.isEmpty()) requestPermissions(missing.toArray(new String[0]), REQ_PERMS);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @SuppressWarnings("deprecation")
    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
