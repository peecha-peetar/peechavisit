// env.js - پیچا ویزیت | تنظیمات محیط اجرا (وب‌اپ یا اپ اندروید)
'use strict';

// ══════════════════════════════════════════
// تشخیص اجرا داخل اپ اندروید
// ──────────────────────────────────────────
// اپ اندروید صفحات را از دامنهٔ امن appassets.androidplatform.net
// بارگذاری می‌کند تا دوربین و GPS کار کنند.
// ══════════════════════════════════════════
const PV_IS_APP     = window.location.hostname === 'appassets.androidplatform.net';
const PV_SERVER_KEY = 'pv_server';
const PV_API_PORT   = 5000;

// آدرس سرور ذخیره‌شده را به شکل کامل برمی‌گرداند: http://IP:5000
function normalizeServer(raw) {
    let s = (raw || '').trim().replace(/\/+$/, '').replace(/\/api$/, '');
    if (!s) return '';
    if (!/^https?:\/\//i.test(s)) s = 'http://' + s;
    try {
        const u = new URL(s);
        if (!u.port) u.port = String(PV_API_PORT);
        return `${u.protocol}//${u.host}`;
    } catch { return ''; }
}

function getServerBase() {
    const saved = normalizeServer(localStorage.getItem(PV_SERVER_KEY));
    if (saved) return saved;
    // وب‌اپ: همان سروری که صفحه از آن باز شده
    return PV_IS_APP ? '' : `http://${window.location.hostname}:${PV_API_PORT}`;
}

function setServerBase(raw) {
    const s = normalizeServer(raw);
    if (s) localStorage.setItem(PV_SERVER_KEY, s);
    else   localStorage.removeItem(PV_SERVER_KEY);
    return s;
}

function getApiBase() {
    const b = getServerBase();
    return b ? `${b}/api` : '';
}

// ══════════════════════════════════════════
// اپ اندروید: ارسال درخواست‌های سرور از طریق کد بومی اندروید
// ──────────────────────────────────────────
// WebView ممکن است درخواست از صفحهٔ امن (https) به سرور http داخل شبکه
// را مسدود کند (Mixed Content / Local Network Access).
// برای همین fetch به آدرس‌های بیرونی به PeechaNative سپرده می‌شود.
// ══════════════════════════════════════════
if (PV_IS_APP && window.PeechaNative) {
    const nativeFetchOrig = window.fetch.bind(window);
    const pending = {};
    let seq = 0;

    // پاسخ از سمت اندروید: {id, status, body, type} یا {id, error}
    window.__pvNativeDone = raw => {
        const r = JSON.parse(raw);
        const p = pending[r.id];
        if (!p) return;                     // قبلاً abort شده
        delete pending[r.id];
        if (r.error || r.status < 200 || r.status > 599) {
            p.reject(new TypeError(r.error || 'Network request failed'));
            return;
        }
        const noBody = [204, 205, 304].includes(r.status);
        p.resolve(new Response(noBody ? null : r.body,
            { status: r.status, headers: { 'Content-Type': r.type || 'application/json' } }));
    };

    window.fetch = (input, init = {}) => {
        const url = new URL(typeof input === 'string' ? input : input.url, window.location.href);
        if (url.host === window.location.host || !/^https?:$/.test(url.protocol))
            return nativeFetchOrig(input, init);

        return new Promise((resolve, reject) => {
            const id = String(++seq);
            const signal = init.signal;
            if (signal) {
                if (signal.aborted) { reject(new DOMException('Aborted', 'AbortError')); return; }
                signal.addEventListener('abort', () => {
                    if (pending[id]) { delete pending[id]; reject(new DOMException('Aborted', 'AbortError')); }
                });
            }
            pending[id] = { resolve, reject };
            const headers = init.headers instanceof Headers
                ? Object.fromEntries(init.headers.entries()) : (init.headers || {});
            window.PeechaNative.request(id, (init.method || 'GET').toUpperCase(), url.href,
                JSON.stringify(headers), init.body == null ? '' : String(init.body), init.pvTimeout || 30000);
        });
    };
}

// ══════════════════════════════════════════
// ذخیرهٔ token
// ──────────────────────────────────────────
// وب‌اپ → sessionStorage (با بستن مرورگر پاک می‌شود)
// اپ اندروید → localStorage (تا پایان اعتبار token ماندگار است)
// ══════════════════════════════════════════
const PV_TOKEN_KEY   = 'pv_token_v2';
const PV_TOKEN_STORE = PV_IS_APP ? localStorage : sessionStorage;

// ══════════════════════════════════════════
// تاریخ محلی (نه UTC)
// ══════════════════════════════════════════
function localDateStr(d = new Date()) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ══════════════════════════════════════════
// تبدیل میلادی → شمسی
// ══════════════════════════════════════════
function gregorianToJalali(gy, gm, gd) {
    const gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    const gy2 = gm > 2 ? gy + 1 : gy;
    let days = 355666 + 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100)
             + Math.floor((gy2 + 399) / 400) + gd + gdm[gm - 1];
    let jy = -1595 + 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
        jy += Math.floor((days - 1) / 365);
        days = (days - 1) % 365;
    }
    const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
    const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
    return [jy, jm, jd];
}

function todayJalali() {
    const n = new Date();
    return gregorianToJalali(n.getFullYear(), n.getMonth() + 1, n.getDate());
}

// ══════════════════════════════════════════
// تبدیل شمسی → میلادی  (خروجی: YYYY-MM-DD)
// ══════════════════════════════════════════
function jalaliToGregorian(jy, jm, jd) {
    jy = parseInt(jy, 10); jm = parseInt(jm, 10); jd = parseInt(jd, 10);
    if (!jy || !jm || !jd) return null;
    jy += 1595;
    let days = -355668 + 365 * jy + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4)
             + jd + (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186);
    let gy = 400 * Math.floor(days / 146097);
    days %= 146097;
    if (days > 36524) {
        gy += 100 * Math.floor(--days / 36524);
        days %= 36524;
        if (days >= 365) days++;
    }
    gy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
        gy += Math.floor((days - 1) / 365);
        days = (days - 1) % 365;
    }
    let gd = days + 1;
    const leap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0;
    const gmd = [0, 31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let gm = 0;
    for (gm = 1; gm <= 12 && gd > gmd[gm]; gm++) gd -= gmd[gm];
    return `${gy}-${String(gm).padStart(2, '0')}-${String(gd).padStart(2, '0')}`;
}

// ══════════════════════════════════════════
// پیام‌های فارسی داخل اپ
// ──────────────────────────────────────────
// alert/confirm مرورگر در اندروید عنوانی با آدرس داخلی صفحه دارد؛
// به‌جای آن یک پنجرهٔ فارسی با فونت وزیر نمایش داده می‌شود.
// ══════════════════════════════════════════
function pvDialog(msg, buttons = [{ text: 'باشه', primary: true, value: true }]) {
    return new Promise(resolve => {
        const wrap = document.createElement('div');
        wrap.className = 'pv-dlg-wrap';
        wrap.innerHTML = '<div class="pv-dlg" role="alertdialog"><div class="pv-dlg-msg"></div><div class="pv-dlg-btns"></div></div>';
        wrap.querySelector('.pv-dlg-msg').textContent = String(msg ?? '');
        const box = wrap.querySelector('.pv-dlg-btns');
        buttons.forEach(b => {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'btn ' + (b.primary ? 'btn-primary' : 'btn-outline');
            el.textContent = b.text;
            el.onclick = () => { wrap.remove(); resolve(b.value); };
            box.appendChild(el);
        });
        document.body.appendChild(wrap);
    });
}
window.alert = msg => { pvDialog(msg); };
function pvConfirm(msg, okText = 'بله', cancelText = 'انصراف') {
    return pvDialog(msg, [{ text: cancelText, value: false }, { text: okText, primary: true, value: true }]);
}

// ══════════════════════════════════════════
// اطلاعات دستگاه — همراه هر درخواست (هدر X-Device، URL-encode شده)
// ══════════════════════════════════════════
function pvDevice() {
    try { if (window.PeechaNative && window.PeechaNative.deviceInfo) return window.PeechaNative.deviceInfo(); } catch { }
    const ua = navigator.userAgent || '';
    const m = ua.match(/Android ([\d.]+); ([^;)]+)/);
    return m ? `${m[2].trim()} · Android ${m[1]} · web` : ua.slice(0, 120);
}
const pvDeviceHeader = () => encodeURIComponent(pvDevice());


// ══════════════════════════════════════════
// ورود آفلاین — وقتی سرور در دسترس نیست
// ──────────────────────────────────────────
// بعد از هر ورود موفق آنلاین، فقط «اثر» رمز (هش تکرارشده با salt تصادفی) روی گوشی
// ذخیره می‌شود — خود رمز هرگز ذخیره نمی‌شود. اگر سرور جواب ندهد، همان نام کاربری و رمز
// با این اثر مقایسه می‌شود و اپ در حالت آفلاین باز می‌شود (ثبت‌ها در صف می‌مانند).
// ══════════════════════════════════════════
function pvSha256Hex(str) {
    const K = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    const bytes = Array.from(new TextEncoder().encode(str));
    const bitLen = bytes.length * 8;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) bytes.push(0);
    for (let i = 7; i >= 0; i--) bytes.push(i >= 4 ? 0 : (bitLen >>> (i * 8)) & 0xff);
    let h = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    const w = new Array(64);
    const r = (x, n) => (x >>> n) | (x << (32 - n));
    for (let o = 0; o < bytes.length; o += 64) {
        for (let i = 0; i < 16; i++) w[i] = (bytes[o+4*i] << 24) | (bytes[o+4*i+1] << 16) | (bytes[o+4*i+2] << 8) | bytes[o+4*i+3];
        for (let i = 16; i < 64; i++) {
            const s0 = r(w[i-15], 7) ^ r(w[i-15], 18) ^ (w[i-15] >>> 3);
            const s1 = r(w[i-2], 17) ^ r(w[i-2], 19) ^ (w[i-2] >>> 10);
            w[i] = (w[i-16] + s0 + w[i-7] + s1) | 0;
        }
        let [a, b, c, d, e, f, g, hh] = h;
        for (let i = 0; i < 64; i++) {
            const t1 = (hh + (r(e, 6) ^ r(e, 11) ^ r(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0;
            const t2 = ((r(a, 2) ^ r(a, 13) ^ r(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
            hh = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
        }
        h = [h[0]+a|0, h[1]+b|0, h[2]+c|0, h[3]+d|0, h[4]+e|0, h[5]+f|0, h[6]+g|0, h[7]+hh|0];
    }
    return h.map(x => (x >>> 0).toString(16).padStart(8, '0')).join('');
}
const PV_OFF_KEY = 'pv_offline_cred_v1';
function pvVerifier(username, password, salt) {
    let v = pvSha256Hex(`${salt}|${String(username).toLowerCase()}|${password}`);
    for (let i = 0; i < 4000; i++) v = pvSha256Hex(salt + v);      // کند کردن حدس زدن رمز
    return v;
}
function pvSaveOfflineCred(username, password, user) {
    try {
        const list = (JSON.parse(localStorage.getItem(PV_OFF_KEY)) || []).filter(x => x.u !== String(username).toLowerCase());
        const salt = Array.from(crypto.getRandomValues ? crypto.getRandomValues(new Uint8Array(16)) : [Date.now() % 256])
            .map(b => b.toString(16).padStart(2, '0')).join('') + Date.now().toString(36);
        list.unshift({ u: String(username).toLowerCase(), salt, v: pvVerifier(username, password, salt), user, at: Date.now() });
        localStorage.setItem(PV_OFF_KEY, JSON.stringify(list.slice(0, 5)));
    } catch { }
}
function pvCheckOfflineCred(username, password) {
    try {
        const rec = (JSON.parse(localStorage.getItem(PV_OFF_KEY)) || []).find(x => x.u === String(username).toLowerCase());
        if (!rec) return { ok: false, reason: 'none' };
        if (Date.now() - rec.at > 60 * 86400000) return { ok: false, reason: 'old' };   // حداکثر ۶۰ روز بعد از آخرین ورود آنلاین
        return pvVerifier(username, password, rec.salt) === rec.v ? { ok: true, user: rec.user } : { ok: false, reason: 'wrong' };
    } catch { return { ok: false, reason: 'none' }; }
}
