// app.js - پیچا ویزیت v4.0 | آفلاین-First
'use strict';

// آدرس API — از env.js (وب‌اپ: همان سرور PWA | اپ اندروید: آدرس تنظیم‌شده)
const API = getApiBase();
console.log('[PeechaVisit] API:', API);

// ══════════════════════════════════════════
// مدیریت Session — آفلاین-First
// ──────────────────────────────────────────
// localStorage  → اطلاعات کاربر (ماندگار، آفلاین کار می‌کنه)
// PV_TOKEN_STORE → token (env.js: وب‌اپ sessionStorage، اپ اندروید localStorage)
// ══════════════════════════════════════════
const LS_KEY     = 'pv_user_v2';   // localStorage
const SS_KEY     = PV_TOKEN_KEY;
const MAX_DAYS   = 30;             // انقضای session

function setSession(data) {
    localStorage.setItem(LS_KEY, JSON.stringify({
        id: data.id, name: data.name,
        role: data.role, username: data.username,
        loginAt: Date.now()
    }));
    if (data.token) PV_TOKEN_STORE.setItem(SS_KEY, data.token);
}

function getSession() {
    try {
        const raw = localStorage.getItem(LS_KEY);
        if (!raw) return null;
        const s = JSON.parse(raw);
        if (Date.now() - s.loginAt > MAX_DAYS * 86400000) {
            clearSession(); return null;
        }
        return s;
    } catch { return null; }
}

function clearSession() {
    localStorage.removeItem(LS_KEY);
    PV_TOKEN_STORE.removeItem(SS_KEY);
}

function getToken()       { return PV_TOKEN_STORE.getItem(SS_KEY) || ''; }
function getVisitorId()   { const s=getSession(); return s?(s.id||1):1; }
function getVisitorName() { const s=getSession(); return s?(s.name||''):''; }

// ══════════════════════════════════════════
// بررسی auth — آفلاین-First
// ══════════════════════════════════════════
(function checkAuth() {
    const s = getSession();

    // هیچ session‌ای نداریم یا آدرس سرور اپ تنظیم نشده → login
    if (!s || !API) {
        window.location.replace('login.html');
        return;
    }

    // session داریم → اپ رو نشون بده (آفلاین یا آنلاین)
    const hp = document.querySelector('.app-header p');
    if (hp && s.name) hp.textContent = `👤 ${s.name}  |  PeechaVisit`;
})();

// ══════════════════════════════════════════
// apiFetch — با fallback آفلاین
// ══════════════════════════════════════════
function apiFetch(endpoint, options = {}) {
    // اگه آفلاین و POST هست → مستقیم به صف آفلاین
    if (!navigator.onLine && options.method === 'POST') {
        return Promise.reject(new Error('OFFLINE'));
    }

    const token = getToken();
    const ctrl = new AbortController();
    const tid  = setTimeout(() => ctrl.abort(), 15000); // 15s timeout

    return fetch(`${API}${endpoint}`, {
        ...options,
        signal: ctrl.signal,
        headers: {
            'Content-Type': 'application/json',
            'X-Auth-Token': token,
            ...(options.headers || {})
        }
    }).then(res => {
        clearTimeout(tid);
        // 401 فقط وقتی آنلاین هستیم → refresh token
        if (res.status === 401) {
            // token منقضی شده ولی session داریم
            // به login میریم تا token جدید بگیریم
            PV_TOKEN_STORE.removeItem(SS_KEY);
            window.location.replace('login.html?expired=1');
            throw new Error('TOKEN_EXPIRED');
        }
        return res;
    }).catch(err => {
        clearTimeout(tid);
        if (err.name === 'AbortError') throw new Error('TIMEOUT');
        if (err.message === 'TOKEN_EXPIRED') throw err;
        throw new Error('OFFLINE');
    });
}

// ══════════════════════════════════════════
// متغیرهای سراسری
// ══════════════════════════════════════════
let db, currentMode = "visit", orderBasket = [];
let isSyncing = false, isSubmitting = false;
let localStream = null, checkStream = null, transferStream = null;
let allCustomersRaw = [], allArticlesRaw = [];

function generateUID() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
}

// ══════════════════════════════════════════
// بخش‌نمایی
// ══════════════════════════════════════════
function showSection(mode) {
    currentMode = mode;
    ['visit','order','pay'].forEach(m =>
        document.getElementById(`btn-menu-${m}`).classList.remove('active'));
    document.getElementById('section-order').classList.remove('visible');
    document.getElementById('section-pay').classList.remove('visible');
    document.getElementById(`btn-menu-${mode}`).classList.add('active');
    if (mode === 'order') document.getElementById('section-order').classList.add('visible');
    if (mode === 'pay')   document.getElementById('section-pay').classList.add('visible');
}
showSection('visit');

// ══════════════════════════════════════════
// نوع پرداخت
// ══════════════════════════════════════════
function handlePayTypeChange() {
    const t = document.getElementById("pay-type").value;
    document.getElementById("cash-section").classList.toggle("active", t === "نقدی");
    document.getElementById("check-section").classList.toggle("active", t === "چک");
    document.getElementById("transfer-section").classList.toggle("active", t === "حواله");
    if (t !== "چک")    stopCheckCamera();
    if (t !== "حواله") stopTransferCamera();
}

// ══════════════════════════════════════════
// IndexedDB
// ══════════════════════════════════════════
const dbReq = indexedDB.open("PeichaVisitDB_V3", 3);
dbReq.onupgradeneeded = e => {
    const d = e.target.result;
    ['offline_queue','integrated_offline_data'].forEach(n => {
        if (d.objectStoreNames.contains(n)) d.deleteObjectStore(n);
    });
    if (!d.objectStoreNames.contains("offline_queue"))
        d.createObjectStore("offline_queue", { keyPath: "uid" });
    if (!d.objectStoreNames.contains("cached_data"))
        d.createObjectStore("cached_data", { keyPath: "type" });
    if (!d.objectStoreNames.contains("sent_uids"))
        d.createObjectStore("sent_uids", { keyPath: "uid" });
};
dbReq.onsuccess = e => {
    db = e.target.result;
    loadCache();
    checkNetwork();
    updateSyncCount();
    handlePayTypeChange();
};

// ══════════════════════════════════════════
// شبکه
// ══════════════════════════════════════════
function checkNetwork() {
    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('net-status');
    if (navigator.onLine) {
        dot.className = 'status-dot online';
        fetchServerData();
    } else {
        dot.className = 'status-dot offline';
    }
    updateSyncCount();
}
window.addEventListener('online',  () => {
    checkNetwork();
    setTimeout(() => { if (!isSyncing && !isSubmitting) autoSync(); }, 5000);
});
window.addEventListener('offline', checkNetwork);

function autoSync() {
    if (!db) return;
    const tx = db.transaction("offline_queue","readonly");
    tx.objectStore("offline_queue").count().onsuccess = e => {
        if (e.target.result > 0) syncLocalDataToServer();
    };
}

// ══════════════════════════════════════════
// داده پایه — با token
// ══════════════════════════════════════════
// ══════════════════════════════════════════
// تنظیمات اپ (از پنل مدیریت، همراه sync-data)
// ══════════════════════════════════════════
const DEFAULT_RULES = { REQUIRE_SELFIE: true, SHOW_PRICE: true, SHOW_STOCK: true,
                        ONLY_IN_STOCK: false, ALLOW_OVERSELL: false };
let appRules = { ...DEFAULT_RULES };

function applyRules(r) {
    appRules = { ...DEFAULT_RULES, ...(r || {}) };
    document.body.classList.toggle('hide-price', !appRules.SHOW_PRICE);
    document.getElementById('selfie-label').innerHTML =
        `سلفی حضور در محل <span class="tag">(${appRules.REQUIRE_SELFIE ? 'اجباری' : 'اختیاری'})</span>`;
    renderBasket();
    updateArticleInfo(articlePicker.value);
    articlePicker.refresh();
}

const fmt = n => Number(n || 0).toLocaleString('fa-IR');
const escHtml = v => String(v ?? '').replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// جستجو بدون حساسیت به ی/ي، ک/ك و ارقام فارسی
function normFa(v) {
    return String(v ?? '').toLowerCase()
        .replace(/[يى]/g, 'ی').replace(/ك/g, 'ک')
        .replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
        .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
        .replace(/\s+/g, ' ').trim();
}

// ══════════════════════════════════════════
// انتخابگر جستجوپذیر: یک فیلد برای جستجو و انتخاب
// ══════════════════════════════════════════
const PICKER_LIMIT = 60;

function makePicker({ root, hidden, items, label, sub, onSelect, emptyText }) {
    const wrap  = document.getElementById(root);
    const input = wrap.querySelector('input');
    const list  = wrap.querySelector('.picker-list');
    const clear = wrap.querySelector('.picker-clear');
    const hid   = document.getElementById(hidden);
    let selected = null, shown = [];

    function render() {
        const all = items();
        const q = selected ? '' : normFa(input.value);
        const matches = q ? all.filter(it => normFa(label(it)).includes(q) || normFa(it.code).includes(q)) : all;
        shown = matches.slice(0, PICKER_LIMIT);
        list.innerHTML = shown.length
            ? shown.map((it, i) => `<div class="picker-item${selected && it.code === selected.code ? ' active' : ''}" data-i="${i}" role="option">
                   <div class="t">${escHtml(label(it))}</div><div class="s">${sub(it)}</div></div>`).join('')
              + (matches.length > PICKER_LIMIT
                  ? `<div class="picker-empty">${fmt(matches.length - PICKER_LIMIT)} مورد دیگر — برای دیدن، بیشتر تایپ کنید</div>` : '')
            : `<div class="picker-empty">${all.length ? 'موردی پیدا نشد' : emptyText}</div>`;
    }
    const open  = () => { render(); wrap.classList.add('open'); };
    const close = () => wrap.classList.remove('open');

    function select(it) {
        selected = it || null;
        hid.value = selected ? selected.code : '';
        input.value = selected ? label(selected) : '';
        input.classList.toggle('has-value', !!selected);
        close();
        if (onSelect) onSelect(selected);
    }

    input.addEventListener('focus', open);
    input.addEventListener('input', () => {
        if (selected) { selected = null; hid.value = ''; input.classList.remove('has-value'); if (onSelect) onSelect(null); }
        open();
    });
    input.addEventListener('blur', () => setTimeout(close, 150));
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && shown.length) { e.preventDefault(); select(shown[0]); input.blur(); }
    });
    // mousedown: فوکوس فیلد حفظ شود تا لمس آیتم ثبت شود (اسکرول لیست را مختل نمی‌کند)
    list.addEventListener('mousedown', e => e.preventDefault());
    list.addEventListener('click', e => {
        const el = e.target.closest('.picker-item');
        if (el) { select(shown[+el.dataset.i]); input.blur(); }
    });
    clear.addEventListener('mousedown', e => e.preventDefault());
    clear.addEventListener('click', () => { select(null); input.focus(); });

    return {
        get value() { return selected; },
        select,
        setPlaceholder(t) { input.placeholder = t; },
        refresh() {
            if (selected) {
                const fresh = items().find(x => x.code === selected.code);
                if (fresh !== selected) select(fresh || null);
            }
            if (wrap.classList.contains('open')) render();
        },
    };
}

const customerPicker = makePicker({
    root: 'customer-picker', hidden: 'main-customer-select',
    items: () => allCustomersRaw,
    label: c => c.name || c.code,
    sub: c => `کد ${escHtml(c.code)}`,
    emptyText: 'لیست مشتریان هنوز دریافت نشده — «همگام‌سازی» را بزنید',
});

const articlePicker = makePicker({
    root: 'article-picker', hidden: 'order-article-select',
    items: () => allArticlesRaw,
    label: a => a.name || a.code,
    sub: a => [
        `کد ${escHtml(a.code)}`,
        appRules.SHOW_PRICE ? `${fmt(a.price)} ریال` : '',
        appRules.SHOW_STOCK ? (a.stock > 0 ? `موجودی ${fmt(a.stock)}` : '<span class="out">ناموجود</span>') : '',
    ].filter(Boolean).join(' · '),
    onSelect: a => updateArticleInfo(a),
    emptyText: 'لیست کالاها هنوز دریافت نشده — «همگام‌سازی» را بزنید',
});

applyRules();   // پیش‌فرض‌ها تا رسیدن تنظیمات از کش یا سرور

function updateArticleInfo(a) {
    document.getElementById('order-price').value = a ? fmt(a.price) : '';
    const hint = document.getElementById('stock-hint');
    hint.className = 'hint';
    hint.textContent = '';
    if (!a || !appRules.SHOW_STOCK) return;
    if (a.stock > 0) hint.textContent = `موجودی: ${fmt(a.stock)}`;
    else { hint.textContent = appRules.ALLOW_OVERSELL ? 'ناموجود (سفارش بدون موجودی مجاز است)' : 'این کالا موجودی ندارد'; hint.classList.add('warn'); }
}

function setListPlaceholders() {
    customerPicker.setPlaceholder(allCustomersRaw.length ? 'نام یا کد مشتری را جستجو کنید' : 'لیست مشتریان دریافت نشده');
    articlePicker.setPlaceholder(allArticlesRaw.length ? 'نام یا کد کالا را جستجو کنید' : 'لیست کالاها دریافت نشده');
}

// خطای دریافت داده پایه را به کاربر نشان بده (به‌جای «در حال بارگذاری...» دائمی)
function showSyncError(msg) {
    console.warn('[PeechaVisit] sync-data:', msg);
    if (!allCustomersRaw.length) customerPicker.setPlaceholder('❌ دریافت لیست ناموفق');
    if (!allArticlesRaw.length)  articlePicker.setPlaceholder('❌ دریافت لیست ناموفق');
    alert('❌ لیست مشتری و کالا از سرور دریافت نشد:\n' + msg);
}

function fetchServerData() {
    apiFetch('/sync-data')
        .then(r => r.json().catch(() => ({ message: `پاسخ نامعتبر از سرور (کد ${r.status})` })))
        .then(d => {
            if (!d.customers) { showSyncError(d.message || 'خطای نامشخص سرور'); return; }
            allCustomersRaw = d.customers;
            allArticlesRaw  = d.articles;
            const tx = db.transaction("cached_data","readwrite");
            tx.objectStore("cached_data").put({ type:"customers", list:d.customers });
            tx.objectStore("cached_data").put({ type:"articles",  list:d.articles  });
            tx.objectStore("cached_data").put({ type:"settings",  list:d.settings || {} });
            applyRules(d.settings);
            customerPicker.refresh();
            setListPlaceholders();
        }).catch(err => {
            if (err.message === 'TOKEN_EXPIRED') return;
            // آفلاین: اگر کش داریم همان نمایش داده می‌شود
            if (allCustomersRaw.length) console.warn('داده از کش محلی بارگذاری میشه');
            else showSyncError(err.message === 'TIMEOUT' ? 'سرور دیر جواب داد' : 'اتصال به سرور برقرار نشد');
        });
}

function loadCache() {
    if (!db) return;
    const tx = db.transaction("cached_data","readonly"), s = tx.objectStore("cached_data");
    s.get("settings").onsuccess = e => { if (e.target.result) applyRules(e.target.result.list); };
    s.get("customers").onsuccess = e => {
        if (e.target.result) { allCustomersRaw = e.target.result.list; setListPlaceholders(); }
    };
    s.get("articles").onsuccess = e => {
        if (e.target.result) { allArticlesRaw = e.target.result.list; setListPlaceholders(); }
    };
}

// ══════════════════════════════════════════
// سبد
// ══════════════════════════════════════════
function stepQty(d) {
    const el = document.getElementById("order-qty");
    el.value = Math.max(1, (parseFloat(el.value) || 0) + d);
}

function addArticleToBasket() {
    const it = articlePicker.value;
    if (!it) { alert("ابتدا کالا را انتخاب کنید."); return; }
    const qty = parseFloat(document.getElementById("order-qty").value);
    if (!qty || qty <= 0) { alert("تعداد معتبر نیست."); return; }
    const existing = orderBasket.find(b => b.code === it.code);
    const total = qty + (existing ? existing.qty : 0);
    if (!appRules.ALLOW_OVERSELL && total > (it.stock || 0)) {
        alert(appRules.SHOW_STOCK
            ? `موجودی کافی نیست (موجودی: ${fmt(it.stock)}${existing ? ` — ${fmt(existing.qty)} عدد در سبد است` : ''})`
            : 'موجودی این کالا برای این تعداد کافی نیست.');
        return;
    }
    if (existing) existing.qty = total;
    else orderBasket.push({ code: it.code, name: it.name, qty, price: parseFloat(it.price) || 0 });
    renderBasket();
    document.getElementById("order-qty").value = "1";
    articlePicker.select(null);
}

function removeArticleFromBasket(i) { orderBasket.splice(i,1); renderBasket(); }

function renderBasket() {
    document.getElementById("basket-body").innerHTML = orderBasket.map((it, i) => `
        <div class="basket-row">
            <div class="info">
                <div class="n">${escHtml(it.name)}</div>
                <div class="d">${fmt(it.qty)} عدد${appRules.SHOW_PRICE ? ` × ${fmt(it.price)} = ${fmt(it.qty * it.price)} ریال` : ''}</div>
            </div>
            <button type="button" class="rm" onclick="removeArticleFromBasket(${i})" aria-label="حذف">✕</button>
        </div>`).join('');
    const sum = orderBasket.reduce((t, it) => t + it.qty * it.price, 0);
    document.getElementById("basket-total").textContent =
        orderBasket.length ? `جمع سبد: ${fmt(sum)} ریال` : '';
}

// ══════════════════════════════════════════
// دوربین‌ها
// ══════════════════════════════════════════
function openCamera() {
    if (localStream) { stopCamera(); return; }
    const btn = document.getElementById("cam-toggle-btn");
    btn.textContent = "⏳ در حال دسترسی..."; btn.disabled = true;
    navigator.mediaDevices.getUserMedia({
        video:{ facingMode:"user", width:{ideal:640}, height:{ideal:480} }, audio:false
    }).then(stream => {
        localStream = stream;
        document.getElementById("video").srcObject = stream;
        document.getElementById("camera-wrapper").style.display = "block";
        document.getElementById("canvas").style.display = "none";
        btn.textContent = "❌ بستن دوربین";
        btn.disabled = false; btn.style.background = "#dc2626";
    }).catch(err => {
        btn.textContent = "📷 باز کردن دوربین سلفی"; btn.disabled = false;
        alert(err.name==="NotAllowedError" ? "⚠️ دسترسی رد شد." : "⚠️ "+err.message);
    });
}
function stopCamera() {
    if (localStream) { localStream.getTracks().forEach(t=>t.stop()); localStream = null; }
    document.getElementById("camera-wrapper").style.display = "none";
    const btn = document.getElementById("cam-toggle-btn");
    btn.textContent = "📷 باز کردن دوربین سلفی";
    btn.style.background = ""; btn.disabled = false;
}
function takeSnapshot() {
    const v = document.getElementById("video"), c = document.getElementById("canvas");
    const ctx = c.getContext("2d");
    c.width = v.videoWidth||640; c.height = v.videoHeight||480;
    ctx.save(); ctx.translate(c.width,0); ctx.scale(-1,1);
    ctx.drawImage(v,0,0,c.width,c.height); ctx.restore();
    document.getElementById("selfie-base64").value = c.toDataURL("image/jpeg",0.82);
    stopCamera(); c.style.display = "block";
    showOk("selfie-ok");
}

function openCheckCamera() {
    if (checkStream) { stopCheckCamera(); return; }
    const btn = document.getElementById("check-cam-btn");
    btn.textContent = "⏳ در حال دسترسی..."; btn.disabled = true;
    navigator.mediaDevices.getUserMedia({
        video:{ facingMode:{ideal:"environment"}, width:{ideal:1280}, height:{ideal:720} }, audio:false
    }).then(stream => {
        checkStream = stream;
        document.getElementById("check-video").srcObject = stream;
        document.getElementById("check-cam-wrap").style.display = "block";
        document.getElementById("check-canvas").style.display = "none";
        btn.textContent = "❌ بستن دوربین"; btn.disabled = false; btn.style.background = "#dc2626";
    }).catch(err => {
        btn.textContent = "📸 عکس از چک بگیر"; btn.disabled = false;
        alert("⚠️ " + (err.name==="NotAllowedError"?"دسترسی رد شد":err.message));
    });
}
function stopCheckCamera() {
    if (checkStream) { checkStream.getTracks().forEach(t=>t.stop()); checkStream = null; }
    const w = document.getElementById("check-cam-wrap");
    if (w) w.style.display = "none";
    const btn = document.getElementById("check-cam-btn");
    if (btn) { btn.textContent = "📸 عکس از چک بگیر"; btn.style.background = ""; btn.disabled = false; }
}
function takeCheckSnapshot() {
    const v = document.getElementById("check-video"), c = document.getElementById("check-canvas");
    c.width = v.videoWidth||1280; c.height = v.videoHeight||720;
    c.getContext("2d").drawImage(v,0,0);
    document.getElementById("check-image-b64").value = c.toDataURL("image/jpeg",0.88);
    stopCheckCamera(); c.style.display = "block"; showOk("check-img-ok");
}

function openTransferCamera() {
    if (transferStream) { stopTransferCamera(); return; }
    const btn = document.getElementById("transfer-cam-btn");
    btn.textContent = "⏳ در حال دسترسی..."; btn.disabled = true;
    navigator.mediaDevices.getUserMedia({
        video:{ facingMode:{ideal:"environment"}, width:{ideal:1280}, height:{ideal:720} }, audio:false
    }).then(stream => {
        transferStream = stream;
        document.getElementById("transfer-video").srcObject = stream;
        document.getElementById("transfer-cam-wrap").style.display = "block";
        document.getElementById("transfer-canvas").style.display = "none";
        btn.textContent = "❌ بستن دوربین"; btn.disabled = false; btn.style.background = "#dc2626";
    }).catch(err => {
        btn.textContent = "📸 عکس از رسید حواله"; btn.disabled = false;
        alert("⚠️ " + (err.name==="NotAllowedError"?"دسترسی رد شد":err.message));
    });
}
function stopTransferCamera() {
    if (transferStream) { transferStream.getTracks().forEach(t=>t.stop()); transferStream = null; }
    const w = document.getElementById("transfer-cam-wrap");
    if (w) w.style.display = "none";
    const btn = document.getElementById("transfer-cam-btn");
    if (btn) { btn.textContent = "📸 عکس از رسید حواله"; btn.style.background = ""; btn.disabled = false; }
}
function takeTransferSnapshot() {
    const v = document.getElementById("transfer-video"), c = document.getElementById("transfer-canvas");
    c.width = v.videoWidth||1280; c.height = v.videoHeight||720;
    c.getContext("2d").drawImage(v,0,0);
    document.getElementById("transfer-image-b64").value = c.toDataURL("image/jpeg",0.88);
    stopTransferCamera(); c.style.display = "block"; showOk("transfer-img-ok");
}

function showOk(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = "block";
    setTimeout(() => el.style.display = "none", 3000);
}

// ══════════════════════════════════════════
// GPS
// ══════════════════════════════════════════
function getGPS(ok, fail) {
    if (!navigator.geolocation) { fail("GPS پشتیبانی نمیشه"); return; }
    navigator.geolocation.getCurrentPosition(
        p => (p.coords.latitude&&p.coords.longitude)
            ? ok(p.coords.latitude,p.coords.longitude) : fail("مختصات نامعتبر"),
        e => fail(e.message),
        { enableHighAccuracy:true, timeout:12000, maximumAge:0 }
    );
}

// ══════════════════════════════════════════
// شمارنده آفلاین
// ══════════════════════════════════════════
function updateSyncCount() {
    if (!db) return;
    const tx = db.transaction("offline_queue","readonly");
    tx.objectStore("offline_queue").count().onsuccess = e => {
        const n = e.target.result;
        const badge = document.getElementById("sync-count");
        badge.textContent = n; badge.style.display = n>0?"inline-block":"none";
        const txt = document.getElementById("net-status");
        if (n > 0)
            txt.textContent = navigator.onLine
                ? `${n} رکورد در صف ارسال`
                : `آفلاین — ${n} رکورد در صف ارسال`;
        else
            txt.textContent = navigator.onLine
                ? "متصل"
                : "آفلاین — ثبت‌ها در گوشی ذخیره می‌شوند";
    };
}

// ══════════════════════════════════════════
// ساخت payment_info با تاریخ شمسی
// ══════════════════════════════════════════
// jalaliToGregorian در env.js تعریف شده است
function getJalaliDate(prefix) {
    const y=document.getElementById(prefix+'-year')?.value;
    const m=document.getElementById(prefix+'-month')?.value;
    const d=document.getElementById(prefix+'-day')?.value;
    if(!y||!m||!d) return null;
    return { jalali:`${y}/${m}/${d}`, gregorian:jalaliToGregorian(y,m,d) };
}

function buildPaymentInfo() {
    const t = document.getElementById("pay-type").value;
    const info = { type:t, amount:parseFloat(document.getElementById("pay-amount").value||0) };
    if (t==="چک") {
        info.check_number  = document.getElementById("check-number").value.trim();
        info.check_sayyadi = document.getElementById("check-sayyadi").value.trim();
        const due = getJalaliDate("check-due");
        info.check_due = due ? due.gregorian : null;
        info.check_due_jalali = due ? due.jalali : null;
        info.check_image = document.getElementById("check-image-b64").value || null;
    } else if (t==="حواله") {
        info.transfer_account  = document.getElementById("transfer-account").value.trim();
        info.transfer_tracking = document.getElementById("transfer-tracking").value.trim();
        const td = getJalaliDate("transfer-date");
        info.transfer_date = td ? td.gregorian : null;
        info.transfer_image = document.getElementById("transfer-image-b64").value || null;
    } else {
        info.cash_desc = document.getElementById("cash-desc").value;
    }
    return info;
}

// ══════════════════════════════════════════
// ثبت فرم
// ══════════════════════════════════════════
function submitIntegratedForm() {
    if (isSubmitting) return;
    // بررسی session (آفلاین هم کار می‌کنه)
    if (!getSession()) { window.location.replace('login.html'); return; }

    const customerCode = document.getElementById("main-customer-select").value;
    const selfie       = document.getElementById("selfie-base64").value;
    if (!customerCode) { alert("⚠️ یک مشتری انتخاب کنید."); return; }
    if (appRules.REQUIRE_SELFIE && !selfie) { alert("⚠️ عکس سلفی الزامی است."); return; }
    if (currentMode==="order" && !orderBasket.length) { alert("⚠️ سبد سفارش خالی است."); return; }
    if (currentMode==="pay") {
        const amt = parseFloat(document.getElementById("pay-amount").value||0);
        if (!amt||amt<=0) { alert("⚠️ مبلغ دریافت را وارد کنید."); return; }
    }

    isSubmitting = true;
    const btn = document.getElementById("submit-btn");
    btn.disabled = true; btn.innerHTML = "⏳ دریافت موقعیت GPS...";

    getGPS((lat,lng) => {
        btn.innerHTML = "⏳ در حال پردازش...";
        const now = new Date();
        const uid = generateUID();
        const payload = {
            uid, mode: currentMode,
            // ✅ visitor_id از session — نه از کاربر
            visitor_id: getVisitorId(),
            customer_code: customerCode,
            latitude: lat, longitude: lng,
            description: document.getElementById("visit-desc").value,
            selfie_b64: selfie,
            client_date: localDateStr(now),
            client_time: now.toTimeString().slice(0,8),
            order_items: currentMode==="order" ? [...orderBasket] : [],
            payment_info: currentMode==="pay" ? buildPaymentInfo() : null
        };

        saveQueue(payload, () => {
            updateSyncCount();
            if (navigator.onLine) trySend(payload, uid, btn);
            else done(btn, false, payload.client_time);
        });
    }, errMsg => {
        isSubmitting = false; btn.disabled = false;
        btn.innerHTML = "ثبت و ارسال";
        alert("❌ GPS دریافت نشد: " + (errMsg||""));
    });
}

// ══════════════════════════════════════════
// ارسال به سرور — با token
// ══════════════════════════════════════════
function sendToServer(p) {
    return apiFetch('/submit-visit', {
        method:'POST', body:JSON.stringify(p)
    })
    .then(r => { if(!r.ok) throw new Error("visit failed"); return r.json(); })
    .then(() => {
        if (p.mode==="order" && p.order_items && p.order_items.length>0)
            return apiFetch('/submit-order', { method:'POST', body:JSON.stringify(p) })
                .then(r => { if(!r.ok) throw new Error("order failed"); });
        if (p.mode==="pay" && p.payment_info && p.payment_info.amount>0)
            return apiFetch('/submit-payment', { method:'POST', body:JSON.stringify(p) })
                .then(r => { if(!r.ok) throw new Error("payment failed"); });
    });
}

// ══════════════════════════════════════════
// عملیات IndexedDB
// ══════════════════════════════════════════
function saveQueue(payload, cb) {
    if (!db) { cb(); return; }
    const tx = db.transaction("offline_queue","readwrite");
    tx.objectStore("offline_queue").put(payload);
    tx.oncomplete = cb; tx.onerror = cb;
}
function deleteQueue(uid) {
    if (!db) return;
    db.transaction("offline_queue","readwrite").objectStore("offline_queue").delete(uid);
}
function markSent(uid) {
    if (!db) return;
    db.transaction("sent_uids","readwrite")
      .objectStore("sent_uids").put({uid, at:new Date().toISOString()});
}
function isSent(uid) {
    return new Promise(res => {
        if (!db) { res(false); return; }
        const r = db.transaction("sent_uids","readonly").objectStore("sent_uids").get(uid);
        r.onsuccess = () => res(!!r.result); r.onerror = () => res(false);
    });
}

function trySend(payload, uid, btn) {
    sendToServer(payload)
        .then(() => { deleteQueue(uid); markSent(uid); done(btn, true, payload.client_time); })
        .catch(err => {
            if (err.message === 'TOKEN_EXPIRED') return; // redirect در apiFetch
            // آفلاین یا خطای شبکه → ذخیره در صف
            done(btn, false, payload.client_time);
        });
}

function done(btn, sent, t) {
    isSubmitting = false; btn.disabled = false;
    btn.innerHTML = "ثبت و ارسال";
    resetForm(); updateSyncCount();
    alert(sent
        ? `✅ با موفقیت ثبت شد\n⏱️ ${t}`
        : `📴 در صف آفلاین ذخیره شد\n⏱️ ${t}\nبه محض اتصال ارسال می‌شود`);
}

// ══════════════════════════════════════════
// همگام‌سازی
// ══════════════════════════════════════════
async function syncLocalDataToServer() {
    if (!navigator.onLine) { alert("❌ اینترنت ندارید."); return; }
    if (isSyncing||isSubmitting) return;
    if (!navigator.onLine) { alert("❌ اینترنت وصل نیست. لطفاً بعداً امتحان کنید."); return; }
    if (!getSession()) { window.location.replace('login.html'); return; }
    fetchServerData();   // لیست مشتری، کالا و تنظیمات هم بروز شود
    isSyncing = true;

    const records = await new Promise(res => {
        const tx = db.transaction("offline_queue","readonly");
        tx.objectStore("offline_queue").getAll().onsuccess = e => res(e.target.result||[]);
    });
    if (!records.length) { isSyncing=false; alert("✅ چیزی در صف ارسال نیست. لیست‌ها بروز شد."); return; }

    let ok=0, skip=0, fail=0;
    for (const rec of records) {
        if (await isSent(rec.uid)) { deleteQueue(rec.uid); skip++; updateSyncCount(); continue; }
        try {
            await sendToServer(rec);
            deleteQueue(rec.uid); markSent(rec.uid); ok++; updateSyncCount();
        } catch(e) {
            if (e.message==='TOKEN_EXPIRED') break;
            fail++;
        }
    }
    isSyncing = false; updateSyncCount();
    alert(`✅ ${ok} ثبت${skip?` | ⏭️ ${skip} تکراری`:''}${fail?` | ❌ ${fail} ناموفق`:''}`);
}

// ══════════════════════════════════════════
// خروج
// ══════════════════════════════════════════
function logout() {
    clearSession();
    window.location.replace('login.html');
}

// ══════════════════════════════════════════
// ریست فرم
// ══════════════════════════════════════════
function resetForm() {
    ['visit-desc','customer-search','article-search','cash-desc',
     'check-number','check-sayyadi','check-image-b64',
     'transfer-account','transfer-tracking','transfer-image-b64',
     'selfie-base64','pay-amount'].forEach(id => {
        const el = document.getElementById(id); if (el) el.value = "";
    });
    ['canvas','check-canvas','transfer-canvas'].forEach(id => {
        const el = document.getElementById(id); if (el) el.style.display = "none";
    });
    document.getElementById("pay-type").value = "نقدی";
    handlePayTypeChange();
    orderBasket = []; renderBasket();
    customerPicker.select(null); articlePicker.select(null);
    document.getElementById("order-qty").value = "1";
    stopCamera(); stopCheckCamera(); stopTransferCamera();
}

// ══════════════════════════════════════════
// پر کردن سال‌های شمسی
// ══════════════════════════════════════════
(function fillJalaliDates() {
    const [jy, jm, jd] = todayJalali();
    ['check-due-year','transfer-date-year'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        [...sel.options].forEach(o => { if (o.value) o.remove(); }); // جلوگیری از گزینهٔ تکراری
        for (let y = jy - 1; y <= jy + 3; y++) {
            const o = document.createElement('option');
            o.value = y; o.textContent = y; sel.appendChild(o);
        }
        sel.value = jy;
    });
    ['check-due-day','transfer-date-day'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        [...sel.options].forEach(o => { if (o.value) o.remove(); }); // جلوگیری از گزینهٔ تکراری
        for (let d = 1; d <= 31; d++) {
            const o = document.createElement('option');
            o.value = String(d).padStart(2,'0'); o.textContent = d; sel.appendChild(o);
        }
        sel.value = String(jd).padStart(2,'0');
    });
    // پیش‌فرض: تاریخ شمسی امروز
    ['check-due-month','transfer-date-month'].forEach(id => {
        const sel = document.getElementById(id);
        if (sel) sel.value = String(jm).padStart(2,'0');
    });
})();
