// app.js - پیچا ویزیت v4.0 | آفلاین-First
'use strict';

// آدرس API — همیشه همون سرور که PWA روشه
const _HOST = window.location.hostname;
const API   = `http://${_HOST}:5000/api`;
console.log('[PeechaVisit] API:', API);

// ══════════════════════════════════════════
// مدیریت Session — آفلاین-First
// ──────────────────────────────────────────
// localStorage  → اطلاعات کاربر (ماندگار، آفلاین کار می‌کنه)
// sessionStorage → token (امنیت، با بستن مرورگر پاک میشه)
// ══════════════════════════════════════════
const LS_KEY     = 'pv_user_v2';   // localStorage
const SS_KEY     = 'pv_token_v2';  // sessionStorage
const MAX_DAYS   = 30;             // انقضای session

function setSession(data) {
    localStorage.setItem(LS_KEY, JSON.stringify({
        id: data.id, name: data.name,
        role: data.role, username: data.username,
        loginAt: Date.now()
    }));
    if (data.token) sessionStorage.setItem(SS_KEY, data.token);
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
    sessionStorage.removeItem(SS_KEY);
}

function getToken()       { return sessionStorage.getItem(SS_KEY) || ''; }
function getVisitorId()   { const s=getSession(); return s?(s.id||1):1; }
function getVisitorName() { const s=getSession(); return s?(s.name||''):''; }

// ══════════════════════════════════════════
// بررسی auth — آفلاین-First
// ══════════════════════════════════════════
(function checkAuth() {
    const s = getSession();

    // هیچ session‌ای نداریم → login
    if (!s) {
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
            sessionStorage.removeItem(SS_KEY);
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
function fetchServerData() {
    apiFetch('/sync-data')
        .then(r => r.json())
        .then(d => {
            if (!d.customers) return;
            allCustomersRaw = d.customers;
            allArticlesRaw  = d.articles;
            const tx = db.transaction("cached_data","readwrite");
            tx.objectStore("cached_data").put({ type:"customers", list:d.customers });
            tx.objectStore("cached_data").put({ type:"articles",  list:d.articles  });
            renderCustomers(allCustomersRaw);
            renderArticles(allArticlesRaw);
        }).catch(err => {
            if (err.message !== 'احراز هویت منقضی شده')
                console.warn('داده از کش محلی بارگذاری میشه');
        });
}

function loadCache() {
    if (!db) return;
    const tx = db.transaction("cached_data","readonly"), s = tx.objectStore("cached_data");
    s.get("customers").onsuccess = e => {
        if (e.target.result) { allCustomersRaw = e.target.result.list; renderCustomers(allCustomersRaw); }
    };
    s.get("articles").onsuccess = e => {
        if (e.target.result) { allArticlesRaw = e.target.result.list; renderArticles(allArticlesRaw); }
    };
}

function renderCustomers(list) {
    const s = document.getElementById("main-customer-select");
    s.innerHTML = (list||[]).length
        ? list.map(c=>`<option value="${c.code}">${c.name} (${c.code})</option>`).join('')
        : '<option>مشتری یافت نشد</option>';
}
function renderArticles(list) {
    const s = document.getElementById("order-article-select");
    s.innerHTML = (list||[]).length
        ? list.map(a=>`<option value="${a.code}" data-price="${a.price}" data-stock="${a.stock}">${a.name} | موجودی:${a.stock}</option>`).join('')
        : '<option>کالا یافت نشد</option>';
    updatePrice();
}
function filterCustomers() {
    const q = document.getElementById("customer-search").value.toLowerCase().trim();
    renderCustomers(q ? allCustomersRaw.filter(c=>
        c.name.toLowerCase().includes(q)||String(c.code).includes(q)) : allCustomersRaw);
}
function filterArticles() {
    const q = document.getElementById("article-search").value.toLowerCase().trim();
    renderArticles(q ? allArticlesRaw.filter(a=>
        a.name.toLowerCase().includes(q)||String(a.code).includes(q)) : allArticlesRaw);
}
function updatePrice() {
    const s = document.getElementById("order-article-select"), o = s.options[s.selectedIndex];
    document.getElementById("order-price").value = o ? (o.getAttribute("data-price")||0) : 0;
}

// ══════════════════════════════════════════
// سبد
// ══════════════════════════════════════════
function addArticleToBasket() {
    const s = document.getElementById("order-article-select"), o = s.options[s.selectedIndex];
    if (!o) return;
    const qty = parseFloat(document.getElementById("order-qty").value);
    const max = parseFloat(o.getAttribute("data-stock")||0);
    if (!qty||qty<1) { alert("تعداد معتبر نیست"); return; }
    if (qty>max) { alert(`موجودی کافی نیست (موجودی: ${max})`); return; }
    orderBasket.push({ code:s.value, name:o.text.split('|')[0].trim(),
                       qty, price:parseFloat(document.getElementById("order-price").value) });
    renderBasketTable();
    document.getElementById("order-qty").value = "1";
}
function removeArticleFromBasket(i) { orderBasket.splice(i,1); renderBasketTable(); }
function renderBasketTable() {
    document.getElementById("basket-body").innerHTML = orderBasket.length
        ? orderBasket.map((it,i)=>`<tr>
            <td style="text-align:right">${it.name}</td>
            <td>${it.qty}</td>
            <td>${it.price.toLocaleString()}</td>
            <td><button class="btn btn-danger" onclick="removeArticleFromBasket(${i})">❌</button></td>
          </tr>`).join('')
        : '<tr><td colspan="4" style="color:#94a3b8;padding:12px;text-align:center">سبد خالی</td></tr>';
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
                ? `آنلاین - ${n} رکورد در صف 🟡`
                : `آفلاین - ${n} رکورد در صف 🔴`;
        else
            txt.textContent = navigator.onLine
                ? "اتصال برقرار است 🟢"
                : "حالت آفلاین - داده ذخیره می‌شود 🔴";
    };
}

// ══════════════════════════════════════════
// ساخت payment_info با تاریخ شمسی
// ══════════════════════════════════════════
function jalaliToGregorian(jy,jm,jd) {
    jy=parseInt(jy); jm=parseInt(jm); jd=parseInt(jd);
    if(!jy||!jm||!jd) return null;
    const jy2=jy-979,jm2=jm-1,jd2=jd-1;
    let jdn=365*jy2+Math.floor(jy2/4)-Math.floor(jy2/100)+Math.floor(jy2/400);
    const jmd=[31,31,31,31,31,31,30,30,30,30,30,29];
    for(let i=0;i<jm2;i++) jdn+=jmd[i];
    jdn+=jd2; let gdn=jdn+79;
    let gy=1600+400*Math.floor(gdn/146097); gdn%=146097;
    let leap=true;
    if(gdn>=36525){gdn--;gy+=100*Math.floor(gdn/36524);gdn%=36524;
        if(gdn>=365)gdn++;else leap=false;}
    gy+=4*Math.floor(gdn/1461); gdn%=1461;
    if(gdn>=366){leap=false;gdn--;gy+=Math.floor(gdn/365);gdn%=365;}
    const gmd=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
    let gm=0;
    for(gm=0;gm<12&&gdn>=gmd[gm];gm++)gdn-=gmd[gm];
    return `${gy}-${String(gm+1).padStart(2,'0')}-${String(gdn+1).padStart(2,'0')}`;
}
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
    if (!customerCode||customerCode.includes("بارگذاری")) { alert("⚠️ یک مشتری انتخاب کنید."); return; }
    if (!selfie) { alert("⚠️ عکس سلفی الزامی است."); return; }
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
            client_date: now.toISOString().slice(0,10),
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
        btn.innerHTML = "💾 ثبت نهایی و ارسال به پیچا";
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
    btn.innerHTML = "💾 ثبت نهایی و ارسال به پیچا";
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
    isSyncing = true;

    const records = await new Promise(res => {
        const tx = db.transaction("offline_queue","readonly");
        tx.objectStore("offline_queue").getAll().onsuccess = e => res(e.target.result||[]);
    });
    if (!records.length) { isSyncing=false; alert("✅ صف آفلاین خالی."); return; }

    let ok=0, skip=0, fail=0;
    for (const rec of records) {
        if (await isSent(rec.uid)) { deleteQueue(rec.uid); skip++; updateSyncCount(); continue; }
        try {
            await sendToServer(rec);
            deleteQueue(rec.uid); markSent(rec.uid); ok++; updateSyncCount();
        } catch(e) {
            if (e.message==='احراز هویت منقضی شده') break;
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
    orderBasket = []; renderBasketTable();
    renderCustomers(allCustomersRaw);
    stopCamera(); stopCheckCamera(); stopTransferCamera();
}

// ══════════════════════════════════════════
// پر کردن سال‌های شمسی
// ══════════════════════════════════════════
(function fillJalaliYears() {
    const curYear = 1405;
    ['check-due-year','transfer-date-year'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        for (let y = curYear; y <= curYear + 3; y++) {
            const o = document.createElement('option');
            o.value = y; o.textContent = y; sel.appendChild(o);
        }
        sel.value = curYear;
    });
    ['check-due-day','transfer-date-day'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        for (let d = 1; d <= 31; d++) {
            const o = document.createElement('option');
            o.value = String(d).padStart(2,'0'); o.textContent = d; sel.appendChild(o);
        }
    });
    // پیش‌فرض ماه امروز
    const now = new Date();
    let jm = now.getMonth() + 1 - 3;
    if (jm <= 0) jm += 12;
    ['check-due-month','transfer-date-month'].forEach(id => {
        const sel = document.getElementById(id);
        if (sel) sel.value = String(jm).padStart(2,'0');
    });
})();
