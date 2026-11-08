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
                JSON.stringify(headers), init.body == null ? '' : String(init.body), 30000);
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
