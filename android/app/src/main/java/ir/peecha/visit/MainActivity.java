// MainActivity.java - پیچا ویزیت | اپ اندروید
// ════════════════════════════════════════════════
// اپ موبایل (pwa_client) را از داخل خود APK اجرا می‌کند.
// صفحات از دامنهٔ امن https://appassets.androidplatform.net بارگذاری می‌شوند
// تا دوربین و GPS (که فقط روی مبدأ امن کار می‌کنند) فعال باشند؛
// درخواست‌های API مستقیماً به سرور داخلی (http://IP:5000) می‌روند.
// ════════════════════════════════════════════════
package ir.peecha.visit;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.GeolocationPermissions;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.webkit.WebViewAssetLoader;

import java.util.ArrayList;
import java.util.List;

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
        setContentView(webView);

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

        // مجوزها را از ابتدا بگیریم تا اولین ثبت ویزیت معطل نشود
        requestMissing(Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION);

        if (savedInstanceState != null) webView.restoreState(savedInstanceState);
        else webView.loadUrl(START_URL);
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
