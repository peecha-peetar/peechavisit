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
    const wait = options.timeout || 15000;               // پیش‌فرض ۱۵ ثانیه؛ گزارش بیشتر
    const tid  = setTimeout(() => ctrl.abort(), wait);

    return fetch(`${API}${endpoint}`, {
        ...options,
        pvTimeout: wait + 2000,
        signal: ctrl.signal,
        headers: {
            'Content-Type': 'application/json',
            'X-Auth-Token': token,
            'X-Device': pvDeviceHeader(),
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

// عدد فارسی با جداکنندهٔ سه‌رقمی — بدون وابستگی به زبان‌های نصب‌شدهٔ WebView گوشی
function fmt(n) {
    const v = Number(n || 0);
    const neg = v < 0, abs = Math.abs(v);
    let [i, d] = (Math.round(abs * 100) / 100).toString().split('.');
    i = i.replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
    const s = (neg ? '-' : '') + i + (d ? '٫' + d : '');
    return s.replace(/\d/g, x => '۰۱۲۳۴۵۶۷۸۹'[x]);
}

// ══════════════════════════════════════════
// مبلغ: ارقام فارسی با جداکنندهٔ سه‌رقمی، هنگام تایپ هم
// ══════════════════════════════════════════
const toLatinDigits = s => String(s ?? '').replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
                                          .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const parseAmt = s => Number(toLatinDigits(s).replace(/[^0-9]/g, '')) || 0;
function formatMoneyInput(el) {
    const digits = toLatinDigits(el.value).replace(/[^0-9]/g, '').replace(/^0+(?=\d)/, '');
    // تعداد رقم‌های بعد از مکان‌نما ثابت می‌ماند تا مکان‌نما نپرد
    const after = toLatinDigits(el.value.slice(el.selectionStart ?? el.value.length)).replace(/[^0-9]/g, '').length;
    el.value = digits ? fmt(Number(digits)) : '';
    let pos = el.value.length, seen = 0;
    while (pos > 0 && seen < after) { pos--; if (/[۰-۹]/.test(el.value[pos])) seen++; }
    try { el.setSelectionRange(pos, pos); } catch { }
}
document.addEventListener('input', e => { if (e.target.classList && e.target.classList.contains('money-input')) formatMoneyInput(e.target); });
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
    items: () => allCustomers(),
    label: c => c.name || c.code,
    sub: c => c.is_new ? `<span class="new-tag">مشتری جدید</span> ${escHtml(c.mobile || c.phone || '')}` : `کد ${faDigits(escHtml(c.code))}`,
    emptyText: 'لیست مشتریان هنوز دریافت نشده — «همگام‌سازی» را بزنید',
});

const articlePicker = makePicker({
    root: 'article-picker', hidden: 'order-article-select',
    items: () => allArticlesRaw,
    label: a => a.name || a.code,
    sub: a => [
        `کد ${faDigits(escHtml(a.code))}`,
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
            markServerCustomers(d.customers);
            pushPendingCustomers();
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
// مشتری جدید — فقط در دیتابیس tracking ثبت می‌شود (نه دیتابیس فروش)
// ──────────────────────────────────────────
// کد موقت (N...) در خود گوشی ساخته می‌شود تا آفلاین هم بشود برایش ویزیت و سفارش ثبت کرد؛
// اطلاعات مشتری همراه هر ثبت هم فرستاده می‌شود تا سرور آن را قبل از سفارش بسازد.
// ══════════════════════════════════════════
const NC_KEY = 'pv_new_customers_v1';
let newCustomers = (() => { try { return JSON.parse(localStorage.getItem(NC_KEY)) || []; } catch { return []; } })();
const saveNC = () => { try { localStorage.setItem(NC_KEY, JSON.stringify(newCustomers)); } catch { } };

function allCustomers() {
    const known = new Set(allCustomersRaw.map(c => String(c.code)));
    return [...newCustomers.filter(c => !known.has(c.code)).map(c => ({ ...c, is_new: true })), ...allCustomersRaw];
}
function localNewCustomer(code) {
    const c = newCustomers.find(x => x.code === code);
    if (!c) return null;
    const { synced, ...data } = c;
    return data;
}
function newCustomerCode() {
    const t = Date.now().toString(36).toUpperCase().slice(-7);
    const r = Math.random().toString(36).toUpperCase().slice(2, 4).padEnd(2, '0');
    return 'N' + t + r;              // ۱۰ کاراکتر (اندازهٔ ستون کد مشتری)
}
function markServerCustomers(list) {
    const codes = new Set((list || []).filter(c => c.is_new).map(c => c.code));
    let ch = false;
    newCustomers.forEach(c => { if (codes.has(c.code) && !c.synced) { c.synced = true; ch = true; } });
    // مشتری‌هایی که روی سرور هستند دیگر لازم نیست در گوشی نگه داشته شوند
    const before = newCustomers.length;
    newCustomers = newCustomers.filter(c => !(c.synced && codes.has(c.code)));
    if (ch || before !== newCustomers.length) saveNC();
}
async function pushPendingCustomers() {
    if (!navigator.onLine) return;
    for (const c of newCustomers.filter(x => !x.synced)) {
        try {
            const r = await apiFetch('/new-customer', { method: 'POST', body: JSON.stringify(localNewCustomer(c.code)) });
            const d = await r.json();
            if (d.status === 'success') { c.synced = true; saveNC(); }
        } catch (e) { if (e.message === 'TOKEN_EXPIRED') return; }
    }
}

function openNewCustomer() {
    const v = document.getElementById('nc-view');
    ['nc-name','nc-contact','nc-mobile','nc-phone','nc-city','nc-address','nc-nid','nc-desc']
        .forEach(id => { document.getElementById(id).value = ''; });
    const q = document.getElementById('customer-search').value.trim();
    if (q && !document.getElementById('main-customer-select').value) document.getElementById('nc-name').value = q;
    document.getElementById('nc-geo').checked = true;
    v.hidden = false; history.pushState({ pvNC: 1 }, '');
    setTimeout(() => document.getElementById('nc-name').focus(), 50);
}
function closeNewCustomer() {
    if (history.state && history.state.pvNC) history.back();
    else document.getElementById('nc-view').hidden = true;
}
window.addEventListener('popstate', () => { document.getElementById('nc-view').hidden = true; });

function quickPosition() {
    return new Promise(res => {
        if (!navigator.geolocation) { res(null); return; }
        navigator.geolocation.getCurrentPosition(p => res(p.coords), () => res(null),
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
    });
}
async function saveNewCustomer() {
    const val = id => document.getElementById(id).value.trim();
    const name = val('nc-name'), mobile = toLatinDigits(val('nc-mobile')), phone = toLatinDigits(val('nc-phone'));
    if (name.length < 2) { alert('⚠️ نام مشتری (یا فروشگاه) را وارد کنید.'); return; }
    if (!mobile && !phone) { alert('⚠️ دست‌کم یک شمارهٔ تماس (موبایل یا تلفن) وارد کنید.'); return; }
    if (mobile && !/^0?9\d{9}$/.test(mobile.replace(/[\s-]/g, ''))) { alert('⚠️ شمارهٔ موبایل معتبر نیست (مثل ۰۹۱۲۳۴۵۶۷۸۹).'); return; }
    const dup = allCustomers().find(c => normFa(c.name) === normFa(name));
    if (dup && !(await pvConfirm(`مشتری دیگری با نام «${dup.name}» وجود دارد. باز هم مشتری جدید ثبت شود؟`, 'ثبت', 'انصراف'))) return;
    const btn = document.getElementById('nc-save');
    btn.disabled = true; btn.textContent = '⏳ در حال ثبت...';
    const pos = document.getElementById('nc-geo').checked ? await quickPosition() : null;
    const c = {
        code: newCustomerCode(), name, contact: val('nc-contact'), mobile, phone,
        city: val('nc-city'), address: val('nc-address'), national_id: toLatinDigits(val('nc-nid')),
        description: val('nc-desc'),
        latitude: pos ? pos.latitude : null, longitude: pos ? pos.longitude : null,
        created: new Date().toISOString(), synced: false,
    };
    newCustomers.push(c); saveNC();
    let online = false;
    if (navigator.onLine) {
        try {
            const r = await apiFetch('/new-customer', { method: 'POST', body: JSON.stringify(localNewCustomer(c.code)) });
            const d = await r.json();
            if (d.status === 'success') { c.synced = true; saveNC(); online = true; }
            else alert('⚠️ ' + (d.message || 'ثبت در سرور ناموفق بود') + '\nمشتری روی گوشی ذخیره شد و بعداً ارسال می‌شود.');
        } catch (e) { if (e.message === 'TOKEN_EXPIRED') return; }
    }
    btn.disabled = false; btn.textContent = 'ثبت مشتری جدید';
    closeNewCustomer();
    customerPicker.refresh();
    customerPicker.select({ ...c, is_new: true });
    alert((online ? '✅ مشتری جدید در سرور ثبت شد.' : '📴 مشتری جدید روی گوشی ذخیره شد و با اتصال ارسال می‌شود.')
          + '\nحالا می‌توانید برای او ویزیت، سفارش یا دریافت ثبت کنید.');
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
// خطاهای دوربین به فارسی
function camErrFa(err) {
    const n = err && err.name;
    if (n === 'NotAllowedError' || n === 'SecurityError')
        return 'اجازهٔ دسترسی به دوربین داده نشده است.\nاز تنظیمات گوشی ← برنامه‌ها ← پیچا ویزیت ← مجوزها، «دوربین» را فعال کنید.';
    if (n === 'NotFoundError' || n === 'OverconstrainedError') return 'دوربین مناسب روی این گوشی پیدا نشد.';
    if (n === 'NotReadableError' || n === 'AbortError') return 'دوربین در اختیار برنامهٔ دیگری است. آن برنامه را ببندید و دوباره تلاش کنید.';
    return 'باز کردن دوربین ممکن نشد. دوباره تلاش کنید.';
}

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
        alert("⚠️ " + camErrFa(err));
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
        alert("⚠️ " + camErrFa(err));
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
        alert("⚠️ " + camErrFa(err));
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
// خطاهای موقعیت‌یابی به فارسی
function gpsErrFa(e) {
    if (!e) return 'موقعیت مکانی دریافت نشد.';
    if (e.code === 1) return 'اجازهٔ دسترسی به موقعیت مکانی داده نشده است.\nاز تنظیمات گوشی ← برنامه‌ها ← پیچا ویزیت ← مجوزها، «مکان» را فعال کنید.';
    if (e.code === 2) return 'موقعیت پیدا نشد. GPS (مکان) گوشی را روشن کنید و ترجیحاً در فضای باز دوباره تلاش کنید.';
    if (e.code === 3) return 'دریافت موقعیت بیش از حد طول کشید. GPS را روشن کنید و دوباره تلاش کنید.';
    return 'موقعیت مکانی دریافت نشد.';
}

// ══════════════════════════════════════════
// GPS دقیق: چند ثانیه به گوشی فرصت می‌دهیم و دقیق‌ترین موقعیت را برمی‌داریم
// (اولین پاسخ معمولاً از شبکه/وای‌فای است و ده‌ها تا صدها متر خطا دارد)
// ══════════════════════════════════════════
function getGPS(ok, fail, progress) {
    if (!navigator.geolocation) { fail('این گوشی از موقعیت‌یابی پشتیبانی نمی‌کند.'); return; }
    const target = appRules.GPS_MAX_ACCURACY || 30;
    const limit  = (appRules.GPS_TIMEOUT || 25) * 1000;
    let best = null, lastErr = null, finished = false, wid = null, timer = null;
    const finish = () => {
        if (finished) return;
        finished = true;
        if (wid !== null) navigator.geolocation.clearWatch(wid);
        clearTimeout(timer);
        if (best) ok(best.lat, best.lng, best.acc, best.acc <= target);
        else fail(gpsErrFa(lastErr));
    };
    wid = navigator.geolocation.watchPosition(p => {
        const c = p.coords;
        if (!c.latitude || !c.longitude) return;
        if (!best || c.accuracy < best.acc) best = { lat: c.latitude, lng: c.longitude, acc: Math.round(c.accuracy) };
        if (progress) progress(best.acc, target);
        if (best.acc <= target) finish();
    }, e => {
        lastErr = e;
        if (e.code === 1) finish();          // اجازه داده نشده؛ صبر بی‌فایده است
    }, { enableHighAccuracy: true, maximumAge: 0, timeout: limit });
    timer = setTimeout(finish, limit);
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
    const info = { type:t, amount:parseAmt(document.getElementById("pay-amount").value) };
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
    }
    info.description = document.getElementById("cash-desc").value.trim();
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
        const amt = parseAmt(document.getElementById("pay-amount").value);
        if (!amt||amt<=0) { alert("⚠️ مبلغ دریافت را وارد کنید."); return; }
    }

    isSubmitting = true;
    const btn = document.getElementById("submit-btn");
    btn.disabled = true; btn.innerHTML = "⏳ در حال یافتن موقعیت دقیق...";
    const resetBtn = () => { isSubmitting = false; btn.disabled = false; btn.innerHTML = "ثبت و ارسال"; };

    getGPS(async (lat, lng, acc, precise) => {
        if (!precise) {
            const go = await pvConfirm(
                `دقت موقعیت فعلی حدود ${fmt(acc)} متر است (هدف: ${fmt(appRules.GPS_MAX_ACCURACY || 30)} متر).\n` +
                'برای دقت بیشتر GPS را روشن کنید و در فضای باز «تلاش دوباره» را بزنید.',
                'ثبت با همین دقت', 'تلاش دوباره');
            if (!go) { resetBtn(); submitIntegratedForm(); return; }
        }
        btn.innerHTML = "⏳ در حال ثبت...";
        const now = new Date();
        const uid = generateUID();
        const payload = {
            uid, mode: currentMode,
            // ✅ visitor_id از session — نه از کاربر
            visitor_id: getVisitorId(),
            customer_code: customerCode,
            latitude: lat, longitude: lng, accuracy: acc,
            description: document.getElementById("visit-desc").value,
            selfie_b64: selfie,
            client_date: localDateStr(now),
            client_time: now.toTimeString().slice(0,8),
            order_items: currentMode==="order" ? [...orderBasket] : [],
            order_note: currentMode==="order" ? document.getElementById("order-note").value.trim() : "",
            payment_info: currentMode==="pay" ? buildPaymentInfo() : null,
            new_customer: localNewCustomer(customerCode)   // اگر مشتری جدید است (برای ثبت آفلاین)
        };

        saveQueue(payload, () => {
            updateSyncCount();
            if (navigator.onLine) trySend(payload, uid, btn);
            else done(btn, false, payload.client_time);
        });
    }, errMsg => {
        resetBtn();
        alert("❌ " + errMsg);
    }, (acc, target) => {
        btn.innerHTML = `⏳ در حال یافتن موقعیت دقیق... (دقت فعلی ${fmt(acc)} متر)`;
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
    // آفلاین: ارسال ممکن نیست؛ صف ثبت‌ها و آخرین گزارش نمایش داده می‌شود
    if (!navigator.onLine) { openReport(true); return; }
    if (isSyncing||isSubmitting) return;
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
    alert(`✅ ${fmt(ok)} ثبت ارسال شد${skip?` | ${fmt(skip)} تکراری`:''}${fail?` | ❌ ${fmt(fail)} ناموفق`:''}`);
    if (!document.getElementById('report-view').hidden) { renderQueue(); loadReport(); }
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
     'selfie-base64','pay-amount','order-note'].forEach(id => {
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


// ══════════════════════════════════════════
// گزارش کار من
// ──────────────────────────────────────────
// صف ارسال از IndexedDB (آفلاین هم کار می‌کند) + ثبت‌های سرور (/api/my-report)
// که برای مشاهدهٔ آفلاین در کش نگه داشته می‌شود.
// ══════════════════════════════════════════
let repRange = 'today', repCustom = null;
const MODE_LABEL = { visit: 'ویزیت', order: 'ویزیت + سفارش', pay: 'ویزیت + دریافت' };

function jdateFa(iso) {
    const [y, m, d] = String(iso || '').slice(0, 10).split('-').map(Number);
    if (!y) return '—';
    const [jy, jm, jd] = gregorianToJalali(y, m, d);
    return `${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`.replace(/\d/g, x => '۰۱۲۳۴۵۶۷۸۹'[x]);
}
const faDigits = v => String(v ?? '').replace(/\d/g, x => '۰۱۲۳۴۵۶۷۸۹'[x]);

function repDates(r) {
    const now = new Date();
    const to = localDateStr(now);
    if (r === 'week') { const f = new Date(now); f.setDate(f.getDate() - 6); return [localDateStr(f), to]; }
    if (r === 'month') { const [jy, jm] = todayJalali(); return [jalaliToGregorian(jy, jm, 1), to]; }
    if (r === 'q3') { const f = new Date(now); f.setDate(f.getDate() - 89); return [localDateStr(f), to]; }
    if (r === 'year') { const f = new Date(now); f.setDate(f.getDate() - 364); return [localDateStr(f), to]; }
    if (r === 'custom' && repCustom) return repCustom;
    return [to, to];
}

function openReport(focusQueue) {
    const v = document.getElementById('report-view');
    if (v.hidden) { v.hidden = false; history.pushState({ pvReport: 1 }, ''); }
    document.getElementById('rep-sub').textContent = getVisitorName();
    renderQueue();
    loadReport();
    if (focusQueue) setTimeout(() => document.getElementById('rep-queue-card').scrollIntoView({ behavior: 'smooth' }), 50);
}
function closeReport() {
    if (history.state && history.state.pvReport) history.back();
    else document.getElementById('report-view').hidden = true;
}
window.addEventListener('popstate', () => { document.getElementById('report-view').hidden = true; });

function setRepRange(r) {
    repRange = r;
    document.querySelectorAll('#rep-range .menu-btn').forEach(b => b.classList.toggle('active', b.dataset.r === r));
    document.getElementById('rep-custom').hidden = r !== 'custom';
    if (r === 'custom' && !repCustom) { fillCustomRange(); return; }   // اول بازه را انتخاب کند
    loadReport();
}

// ── بازهٔ دلخواه (شمسی) ──
const JMONTHS = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
function fillCustomRange(fromIso, toIso) {
    const [ty] = todayJalali();
    const set = (p, iso) => {
        const [y, m, d] = (iso || localDateStr()).split('-').map(Number);
        const [jy, jm, jd] = gregorianToJalali(y, m, d);
        const fill = (id, items, val) => {
            const s = document.getElementById(id);
            if (!s.options.length) s.innerHTML = items.map(([v, t]) => `<option value="${v}">${t}</option>`).join('');
            s.value = String(val);
        };
        fill(`rc-${p}-day`, Array.from({ length: 31 }, (_, i) => [i + 1, faDigits(i + 1)]), jd);
        fill(`rc-${p}-month`, JMONTHS.map((n, i) => [i + 1, n]), jm);
        fill(`rc-${p}-year`, Array.from({ length: 6 }, (_, i) => [ty - 5 + i, faDigits(ty - 5 + i)]), jy);
    };
    set('from', fromIso || repDates('month')[0]); set('to', toIso);
}
function readCustom(p) {
    const v = k => document.getElementById(`rc-${p}-${k}`).value;
    return jalaliToGregorian(v('year'), v('month'), v('day'));
}
function applyCustomRange() {
    let a = readCustom('from'), b = readCustom('to');
    if (!a || !b) { alert('تاریخ را کامل انتخاب کنید.'); return; }
    if (a > b) [a, b] = [b, a];
    if ((new Date(b) - new Date(a)) / 864e5 > 366) { alert('بازهٔ گزارش حداکثر یک سال است.'); return; }
    repCustom = [a, b];
    loadReport();
}
function showRange(fromIso, toIso) {
    repCustom = [fromIso, toIso];
    fillCustomRange(fromIso, toIso);
    repRange = 'custom';
    document.querySelectorAll('#rep-range .menu-btn').forEach(b => b.classList.toggle('active', b.dataset.r === 'custom'));
    document.getElementById('rep-custom').hidden = false;
    loadReport();
}
// سرور پاسخ‌دهنده: نسخه و دیتابیس فروش (برای تشخیص سرور قدیمی یا تنظیمات اشتباه)
function serverNote(s) {
    return s ? ` — سرور نسخهٔ ${faDigits(s.version || '?')} · دیتابیس فروش: ${s.sales_db} · ردیابی: ${s.tracking_db}` : ' — سرور نسخهٔ قدیمی (به‌روز کنید)';
}
function repAlert(html, isErr) {
    const a = document.getElementById('rep-alert');
    a.hidden = !html; a.innerHTML = html || ''; a.classList.toggle('err', !!isErr);
}

function renderQueue() {
    if (!db) return;
    db.transaction('offline_queue', 'readonly').objectStore('offline_queue').getAll().onsuccess = e => {
        const recs = (e.target.result || []).sort((a, b) => (b.client_date + b.client_time).localeCompare(a.client_date + a.client_time));
        document.getElementById('rep-queue-n').textContent = faDigits(recs.length);
        document.getElementById('rep-queue-n').style.background = recs.length ? '' : '#adb5bd';
        document.getElementById('rep-send').style.display = recs.length ? '' : 'none';
        document.getElementById('rep-queue').innerHTML = recs.map(r => {
            const c = allCustomers().find(x => String(x.code) === String(r.customer_code));
            const amount = r.mode === 'order' ? (r.order_items || []).reduce((t, i) => t + i.qty * i.price, 0)
                         : r.mode === 'pay' && r.payment_info ? r.payment_info.amount : null;
            return `<div class="rep-row">
                ${r.selfie_b64 ? `<img src="${r.selfie_b64}" alt="">` : ''}
                <div class="info"><div class="n">${escHtml(c ? c.name : r.customer_code)}</div>
                <div class="d">${jdateFa(r.client_date)} · ${faDigits(String(r.client_time).slice(0, 5))} · <span class="tag wait">${MODE_LABEL[r.mode] || 'ویزیت'} — در صف</span></div></div>
                ${amount !== null && appRules.SHOW_PRICE ? `<div class="a">${fmt(amount)}</div>` : ''}
            </div>`;
        }).join('');
    };
}

let repData = null;
function renderReport(d, stamp) {
    repData = d;
    const sum = (a, k) => a.reduce((t, x) => t + (x[k] || 0), 0);
    const money = n => appRules.SHOW_PRICE ? `<small>${fmt(n)} ریال</small>` : '';
    document.getElementById('rep-kpis').innerHTML =
        `<div><b>${fmt(d.visits.length)}</b><span>ویزیت</span></div>` +
        `<div><b>${fmt(d.orders.length)}</b><span>سفارش</span>${money(sum(d.orders, 'total'))}</div>` +
        `<div><b>${fmt(d.payments.length)}</b><span>دریافت</span>${money(sum(d.payments, 'amount'))}</div>`;
    const row = (kind, id, name, date, time, extra, amount) => `<div class="rep-row tap" onclick="openRepDetail('${kind}',${Number(id) || 0})"><div class="info">
        <div class="n">${escHtml(name)}</div><div class="d">${jdateFa(date)} · ${faDigits(time)}${extra ? ' · ' + extra : ''}</div></div>
        ${amount !== undefined && appRules.SHOW_PRICE ? `<div class="a">${fmt(amount)}</div>` : ''}<span class="chev">‹</span></div>`;
    document.getElementById('rep-visits').innerHTML = d.visits.map(v => row('visit', v.id, v.customer, v.date, v.time,
        escHtml(v.description || '') + (v.selfie ? ' 📷' : ''))).join('');
    document.getElementById('rep-orders').innerHTML = d.orders.map(o => row('order', o.id, o.customer, o.date, o.time,
        `${fmt(o.items ?? (o.lines || []).length)} قلم`, o.total)).join('');
    document.getElementById('rep-pays').innerHTML = d.payments.map(p => row('pay', p.id, p.customer, p.date, p.time,
        `<span class="tag">${escHtml(p.type)}</span>${p.image ? ' 📷' : ''}`, p.amount)).join('');
    document.getElementById('rep-stamp').textContent = stamp;
}

// ── جزئیات یک ثبت ──
const imgCache = {};
function loadMyImage(path, holder) {
    const show = src => { holder.innerHTML = `<img src="${src}" alt="" onclick="showFullImg(this.src)">`; };
    if (imgCache[path]) { show(imgCache[path]); return; }
    if (!navigator.onLine) { holder.innerHTML = '<div class="hint">برای دیدن عکس به سرور وصل شوید.</div>'; return; }
    holder.innerHTML = '<div class="hint">در حال دریافت عکس...</div>';
    apiFetch(`/my-image?path=${encodeURIComponent(path)}`).then(r => r.json()).then(d => {
        if (d.status !== 'success') { holder.innerHTML = `<div class="hint">${escHtml(d.message || 'عکس دریافت نشد')}</div>`; return; }
        imgCache[path] = d.data; show(d.data);
    }).catch(() => { holder.innerHTML = '<div class="hint">عکس دریافت نشد.</div>'; });
}
function showFullImg(src) { const w = document.getElementById('img-full'); w.querySelector('img').src = src; w.hidden = false; }

function openRepDetail(kind, id) {
    if (!repData) return;
    const kv = rows => '<div class="kv">' + rows.filter(r => r[1]).map(([k, v]) => `<div><small>${k}</small><b>${v}</b></div>`).join('') + '</div>';
    const note = (t, label) => t ? `<div class="note"><b>${label}:</b> ${escHtml(t)}</div>` : '';
    const imgs = [];
    let title = '', body = '';
    if (kind === 'visit') {
        const v = repData.visits.find(x => x.id === id); if (!v) return;
        title = `ویزیت — ${escHtml(v.customer)}`;
        body = kv([['تاریخ', jdateFa(v.date)], ['ساعت', faDigits(v.time)], ['کد مشتری', faDigits(v.customer_code)]])
             + note(v.description, 'توضیح ویزیت');
        // سفارش و دریافت همان ویزیت
        const same = x => x.customer_code === v.customer_code && x.date === v.date && x.time === v.time;
        repData.orders.filter(same).forEach(o => { body += `<div class="sec">سفارش شمارهٔ ${faDigits(o.id)}</div>` + orderLines(o); });
        repData.payments.filter(same).forEach(p => { body += `<div class="sec">دریافت ${escHtml(p.type)}</div>` + payInfo(p, kv, note); if (p.image) imgs.push([p.image, p.type === 'چک' ? 'عکس چک' : 'رسید حواله']); });
        if (v.selfie) imgs.unshift([v.selfie, 'سلفی']);
    } else if (kind === 'order') {
        const o = repData.orders.find(x => x.id === id); if (!o) return;
        title = `سفارش شمارهٔ ${faDigits(o.id)} — ${escHtml(o.customer)}`;
        body = kv([['تاریخ', jdateFa(o.date)], ['ساعت', faDigits(o.time)], ['کد مشتری', faDigits(o.customer_code)]]) + orderLines(o);
    } else {
        const p = repData.payments.find(x => x.id === id); if (!p) return;
        title = `دریافت ${escHtml(p.type)} — ${escHtml(p.customer)}`;
        body = kv([['تاریخ', jdateFa(p.date)], ['ساعت', faDigits(p.time)]]) + payInfo(p, kv, note);
        if (p.image) imgs.push([p.image, p.type === 'چک' ? 'عکس چک' : 'رسید حواله']);
    }
    body += imgs.map((im, i) => `<div class="sec">${im[1]}</div><div class="rep-img" id="rep-img-${i}"></div>`).join('');
    document.getElementById('rep-detail-title').innerHTML = title;
    document.getElementById('rep-detail-body').innerHTML = body;
    document.getElementById('rep-detail').hidden = false;
    imgs.forEach((im, i) => loadMyImage(im[0], document.getElementById(`rep-img-${i}`)));
}
function orderLines(o) {
    const lines = o.lines || [];
    if (!lines.length) return '<div class="hint">اقلام این سفارش در گزارش نیست.</div>';
    const pr = appRules.SHOW_PRICE;
    const rows = lines.map((l, i) => `<tr><td>${faDigits(i + 1)}</td><td>${escHtml(l.name)}<div class="hint">کد ${faDigits(l.code)}</div></td>
        <td>${fmt(l.qty)}</td>${pr ? `<td>${fmt(l.price)}</td><td>${fmt(l.qty * l.price)}</td>` : ''}</tr>`).join('');
    const qty = lines.reduce((t, l) => t + l.qty, 0);
    return `<div class="itm-wrap"><table class="itm"><thead><tr><th>#</th><th>کالا</th><th>تعداد</th>${pr ? '<th>فی</th><th>جمع</th>' : ''}</tr></thead>
        <tbody>${rows}</tbody><tfoot><tr><td></td><td>جمع ${faDigits(lines.length)} قلم</td><td>${fmt(qty)}</td>${pr ? `<td></td><td>${fmt(o.total)}</td>` : ''}</tr></tfoot></table></div>`
        + (o.description ? `<div class="note"><b>توضیح سفارش:</b> ${escHtml(o.description)}</div>` : '');
}
function payInfo(p, kv, note) {
    const rows = [['نوع', escHtml(p.type)], ['مبلغ', appRules.SHOW_PRICE ? `${fmt(p.amount)} ریال` : '']];
    if (p.type === 'چک') rows.push(['شماره چک', faDigits(p.check_number)], ['شماره صیادی', faDigits(p.check_sayyadi)], ['سررسید', p.check_due ? jdateFa(p.check_due) : '']);
    if (p.type === 'حواله') rows.push(['حساب / کارت مقصد', `<span dir="ltr">${faDigits(p.account)}</span>`], ['شماره پیگیری', faDigits(p.tracking)]);
    return kv(rows) + note(p.description, 'توضیح دریافت');
}
function closeRepDetail() { document.getElementById('rep-detail').hidden = true; }

function loadReport() {
    const range = repRange;
    const [from, to] = repDates(range);
    const key = 'report_' + (range === 'custom' ? `custom_${from}_${to}` : range);
    repAlert('');
    const fromCache = (note, isErr) => {
        if (isErr) repAlert(`❌ ${escHtml(note)}<br><small>اتصال گوشی به سرور و «آدرس سرور» را بررسی کنید؛ آخرین گزارش ذخیره‌شده نمایش داده می‌شود.</small>`, true);
        if (!db) return;
        db.transaction('cached_data', 'readonly').objectStore('cached_data').get(key).onsuccess = e => {
            const c = e.target.result;
            if (c && c.list) {
                const t = new Date(c.at);
                renderReport(c.list, `${note} — آخرین بروزرسانی: ${jdateFa(localDateStr(t))} ساعت ${faDigits(t.toTimeString().slice(0, 5))}`);
            } else {
                renderReport({ visits: [], orders: [], payments: [] }, `${note} — گزارشی از قبل ذخیره نشده است.`);
            }
        };
    };
    if (!navigator.onLine) { fromCache('حالت آفلاین', true); return; }
    document.getElementById('rep-stamp').textContent = 'در حال دریافت گزارش...';
    apiFetch(`/my-report?from=${from}&to=${to}`, { timeout: 60000 })
        .then(r => r.json().catch(() => ({ status: 'error', message: `پاسخ نامعتبر از سرور (کد ${r.status}) — نسخهٔ سرور را به‌روز کنید` })))
        .then(d => {
            if (range !== repRange) return;
            if (d.status !== 'success') { fromCache((d.message || 'دریافت گزارش ناموفق بود') + serverNote(d.server), true); return; }
            db.transaction('cached_data', 'readwrite').objectStore('cached_data').put({ type: key, list: d, at: Date.now() });
            renderReport(d, `بازه: ${jdateFa(from)} تا ${jdateFa(to)} — بروز` + serverNote(d.server));
            const empty = !d.visits.length && !d.orders.length && !d.payments.length;
            if (empty && d.last_date && (d.last_date < from || d.last_date > to)) {
                const [y, m, dd] = d.last_date.split('-').map(Number);
                const [jy, jm] = gregorianToJalali(y, m, dd);
                const mStart = jalaliToGregorian(jy, jm, 1);
                repAlert(`در این بازه ثبتی برای شما نیست. آخرین ثبت شما: <b>${jdateFa(d.last_date)}</b>
                    <button type="button" class="btn btn-secondary" onclick="showRange('${mStart}','${d.last_date}')">نمایش ثبت‌های ${JMONTHS[jm - 1]} ${faDigits(jy)}</button>`);
            } else if (empty && !d.last_date) {
                repAlert('هنوز هیچ ویزیت، سفارش یا دریافتی با این حساب کاربری در سرور ثبت نشده است.');
            }
        })
        .catch(err => {
            if (err.message === 'TOKEN_EXPIRED') return;
            fromCache(err.message === 'TIMEOUT' ? 'سرور در ۶۰ ثانیه گزارش را آماده نکرد (بازهٔ کوچک‌تری انتخاب کنید)'
                                                : 'اتصال به سرور برقرار نشد', true);
        });
}

// ══════════════════════════════════════════
// پیام‌ها — گفتگو با مدیر و همکاران
// ──────────────────────────────────────────
// هر ۳۰ ثانیه پیام‌های جدید از سرور گرفته می‌شود؛ آخرین پیام‌ها برای
// مشاهدهٔ آفلاین در گوشی نگه داشته می‌شوند.
// ══════════════════════════════════════════
const MSG_KEY = 'pv_msgs_v1';
let msgState = (() => { try { return JSON.parse(localStorage.getItem(MSG_KEY)) || null; } catch { return null; } })()
            || { me: null, last: 0, list: [], contacts: [] };
let chatWith = null, msgPolling = false;

function saveMsgState() {
    msgState.list = msgState.list.slice(-400);
    try { localStorage.setItem(MSG_KEY, JSON.stringify(msgState)); } catch { }
}
const contactName = id => id === 'all' ? 'همه' :
    ((msgState.contacts.find(c => c.id === id) || {}).name
     || (msgState.list.find(m => m.from === id && m.from_name) || {}).from_name || 'کاربر');
const timeFa = at => { const [d, t] = String(at || '').split(' '); return `${jdateFa(d)} ${faDigits((t || '').slice(0, 5))}`; };

function unreadFrom(id) { return msgState.list.filter(m => Number(m.to) === Number(msgState.me) && !m.read && (id == null || Number(m.from) === Number(id))).length; }
function updateMsgBadge() {
    const n = unreadFrom(null), b = document.getElementById('msg-badge');
    b.textContent = faDigits(n); b.style.display = n ? 'inline-block' : 'none';
}

function pollMessages(showToast = true) {
    if (msgPolling || !navigator.onLine || !getToken()) return Promise.resolve();
    msgPolling = true;
    return apiFetch(`/messages?after=${msgState.last}`).then(r => r.json()).then(d => {
        if (d.status !== 'success') return;
        if (msgState.me !== d.me) msgState = { ...msgState, me: d.me, last: 0, list: [] };
        const fresh = d.messages.filter(m => m.id > msgState.last);
        msgState.list.push(...fresh);
        if (fresh.length) msgState.last = Math.max(...fresh.map(m => m.id));
        saveMsgState(); updateMsgBadge();
        const incoming = fresh.filter(m => m.to === d.me && !m.read && m.from !== chatWith);
        if (showToast && incoming.length) {
            const m = incoming[incoming.length - 1];
            showToastMsg(`💬 ${m.from_name || contactName(m.from)}: ${m.body.slice(0, 60)}`, () => openChat(m.from));
        }
        if (chatWith !== null) renderChat();
        else if (!document.getElementById('msg-view').hidden) renderContacts();
    }).catch(() => { }).finally(() => { msgPolling = false; });
}

function showToastMsg(text, onClick) {
    const t = document.getElementById('pv-toast');
    t.textContent = text; t.hidden = false;
    t.onclick = () => { t.hidden = true; onClick && onClick(); };
    clearTimeout(t._h); t._h = setTimeout(() => { t.hidden = true; }, 6000);
}

function openMsgs() {
    const v = document.getElementById('msg-view');
    if (v.hidden) { v.hidden = false; history.pushState({ pvMsgs: 1 }, ''); }
    closeChat(true);
    renderContacts();
    if (navigator.onLine) {
        apiFetch('/contacts').then(r => r.json()).then(d => {
            if (d.status === 'success') { msgState.contacts = d.contacts; msgState.peer = d.peer; saveMsgState(); renderContacts(); }
            else document.getElementById('msg-stamp').textContent = '❌ ' + (d.message || 'لیست کاربران دریافت نشد.');
        }).catch(err => { if (err.message !== 'TOKEN_EXPIRED') document.getElementById('msg-stamp').textContent = '❌ اتصال به سرور برقرار نشد؛ لیست کاربران دریافت نشد.'; });
        pollMessages(false);
    }
}

function renderContacts() {
    const sess = getSession() || {};
    const rows = msgState.contacts.map(c => {
        const conv = msgState.list.filter(m => Number(m.from) === Number(c.id) || Number(m.to) === Number(c.id));
        const last = conv[conv.length - 1];
        return { c, last, unread: unreadFrom(c.id) };
    }).sort((a, b) => (b.last ? b.last.id : 0) - (a.last ? a.last.id : 0));
    const item = (id, name, sub, unread, av) => `<div class="msg-row" onclick="openChat(${id === 'all' ? "'all'" : id})">
        <div class="msg-av">${av}</div>
        <div class="info"><div class="n">${escHtml(name)}</div><div class="d">${escHtml(sub)}</div></div>
        ${unread ? `<span class="c">${faDigits(unread)}</span>` : ''}</div>`;
    document.getElementById('msg-contacts').innerHTML =
        (sess.role === 'admin' ? item('all', 'پیام به همه', 'ارسال یک پیام برای همهٔ کاربران', 0, '📣') : '') +
        rows.map(r => item(r.c.id, r.c.name + (r.c.role === 'admin' ? ' (مدیر)' : ''),
            r.last ? r.last.body : 'هنوز پیامی نیست', r.unread, escHtml((r.c.name || '؟')[0]))).join('');
    document.getElementById('msg-stamp').textContent = navigator.onLine
        ? (msgState.peer === false && sess.role !== 'admin' ? 'طبق تنظیم مدیر، فقط مدیران در لیست گفتگو هستند.' : '') :
        (msgState.contacts.length ? 'حالت آفلاین — آخرین پیام‌های ذخیره‌شده' : 'برای دیدن پیام‌ها به سرور وصل شوید.');
}

function openChat(id) {
    if (document.getElementById('msg-view').hidden) openMsgs();
    chatWith = id;
    document.getElementById('msg-title').textContent = contactName(id);
    document.getElementById('msg-sub').textContent = id === 'all' ? 'پیام برای همهٔ کاربران' : 'گفتگو';
    document.getElementById('msg-list-box').hidden = true;
    document.getElementById('chat-box').hidden = false;
    renderChat();
    if (id !== 'all' && unreadFrom(id) && navigator.onLine) {
        apiFetch('/messages/read', { method: 'POST', body: JSON.stringify({ with: id }) }).catch(() => { });
        msgState.list.forEach(m => { if (Number(m.from) === Number(id) && Number(m.to) === Number(msgState.me)) m.read = true; });
        saveMsgState(); updateMsgBadge();
    }
}

function renderChat() {
    const box = document.getElementById('chat-msgs');
    const conv = chatWith === 'all' ? [] : msgState.list.filter(m => Number(m.from) === Number(chatWith) || Number(m.to) === Number(chatWith));
    const mine = m => Number(m.from) === Number(msgState.me);
    box.innerHTML = conv.length ? conv.map(m => `<div class="bubble ${mine(m) ? 'me' : 'them'}"><b class="who">${mine(m) ? 'شما' : escHtml(m.from_name || contactName(m.from))}</b>${escHtml(m.body)}<small>${timeFa(m.at)}</small></div>`).join('')
        : `<div class="hint" style="text-align:center;margin-top:20px">${chatWith === 'all' ? 'این پیام برای همهٔ کاربران فرستاده می‌شود.' : 'هنوز پیامی رد و بدل نشده است.'}</div>`;
    box.scrollTop = box.scrollHeight;
}

function sendMsg() {
    const el = document.getElementById('chat-text'), body = el.value.trim();
    if (!body) return;
    if (!navigator.onLine) { alert('برای ارسال پیام باید به سرور وصل باشید.'); return; }
    apiFetch('/messages', { method: 'POST', body: JSON.stringify({ to: chatWith, body }) })
        .then(r => r.json()).then(d => {
            if (d.status !== 'success') { alert('❌ ' + (d.message || 'پیام ارسال نشد.')); return; }
            el.value = '';
            if (chatWith === 'all') { alert(`✅ پیام برای ${fmt(d.count)} نفر ارسال شد.`); return; }
            pollMessages(false);
        }).catch(() => alert('❌ اتصال به سرور برقرار نشد؛ پیام ارسال نشد.'));
}

function closeChat(silent) {
    chatWith = null;
    document.getElementById('chat-box').hidden = true;
    document.getElementById('msg-list-box').hidden = false;
    document.getElementById('msg-title').textContent = 'پیام‌ها';
    document.getElementById('msg-sub').textContent = 'گفتگو با مدیر و همکاران';
    if (!silent) renderContacts();
}
function msgBack() {
    if (chatWith !== null) { closeChat(); return; }
    if (history.state && history.state.pvMsgs) history.back();
    else document.getElementById('msg-view').hidden = true;
}
window.addEventListener('popstate', () => { chatWith = null; document.getElementById('msg-view').hidden = true; });

updateMsgBadge();
setTimeout(() => pollMessages(), 3000);
setInterval(() => pollMessages(), 30000);
window.addEventListener('online', () => pollMessages());
