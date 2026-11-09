# dashboard.py - پیچا ویزیت | داشبورد v9
# ════════════════════════════════════════════════
# اجرا:  streamlit run dashboard.py --server.port 8501
# صفحه‌ها: نقشه و لیست · گزارش‌ساز · پیام‌ها · لاگ ورود
# هر «توقف» روی نقشه = یک ویزیت (+ سفارش و دریافتی که همان لحظه ثبت شده)
# ════════════════════════════════════════════════
import base64
import io
import json
import os
import re
import time
import zlib
from datetime import date, timedelta

import folium
import jdatetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

st.set_page_config(page_title="داشبورد | پیچا ویزیت", page_icon="📍",
                   layout="wide", initial_sidebar_state="collapsed")

from db import get_conn, SALES_DB
from panel_auth import require_dashboard, logout
from ui_font import font_css
from ui_theme import theme_css, app_bar
import audit
import report
from config import APP

APP_NAME = APP.get("NAME") or "پیچا ویزیت"

import paths
BASE_DIR   = paths.DATA_DIR
STATIC_DIR = os.path.realpath(paths.STATIC_DIR)
MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
          "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
SALES = f"[{SALES_DB}].dbo" if re.fullmatch(r"[A-Za-z0-9_]+", SALES_DB) else "dbo"

# رنگ‌ها: یک رنگ ثابت برای هر نوع، همه‌جا (نقشه، اعلان، جزئیات)
KIND_COLOR = {"visit": "#3b5bdb", "order": "#7c3aed", "pay": "#12805c"}
KIND_SOFT = {"visit": "#edf1ff", "order": "#f3edff", "pay": "#e6f6ef"}
STOP_COLORS = {
    "visit": ("#3b5bdb", "فقط ویزیت"),
    "order": ("#7c3aed", "ویزیت + سفارش"),
    "pay":   ("#12805c", "ویزیت + دریافت"),
    "both":  ("#e8590c", "سفارش + دریافت"),
}
ROUTE_COLORS = ["#4c6ef5", "#f76707", "#37b24d", "#d6336c", "#1098ad", "#7048e8", "#f59f00", "#868e96"]
PAGES = ["🗺️ نقشه و لیست", "📊 گزارش‌ساز", "📦 گزارش کالا", "💬 پیام‌ها", "📜 لاگ ورود"]
P_MAP, P_REPORT, P_PRODUCTS, P_MSGS, P_LOGS = PAGES

st.markdown(font_css() + "\n" + theme_css(), unsafe_allow_html=True)
st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display:none !important; }
/* هنگام بروزرسانی صفحه کم‌رنگ و چشمک‌زن نشود */
[data-stale="true"], .stale-element, [data-testid="stElementContainer"][data-stale] { opacity:1 !important; transition:none !important; }
/* iframeهای اسکریپت (ارتفاع صفر) جا نگیرند */
[data-testid="stElementContainer"]:has(iframe[height="0"]) { display:none; }
body:has([data-testid="stDialog"]) [data-testid="stPopoverBody"] { display:none !important; }
.st-key-filters [data-testid="stHorizontalBlock"], .st-key-pager [data-testid="stHorizontalBlock"] { gap:8px !important; align-items:center; }
.legend { display:flex; flex-wrap:wrap; gap:6px; margin:0 0 6px; font-size:12px; min-height:26px; }
.legend span { display:inline-flex; align-items:center; gap:5px; background:#fff; border:1px solid #e3e7ef;
               border-radius:20px; padding:2px 10px; }
.legend i { width:10px; height:10px; border-radius:50%; display:inline-block; box-shadow:0 0 0 3px rgba(0,0,0,.04); }
.legend .r { border-radius:2px; height:3px; width:14px; }
.hint { font-size:12px; color:#6b7686; margin:2px 0 6px; min-height:18px; }
[class*="st-key-jp_"] [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; gap:6px !important; }
[class*="st-key-jp_"] [data-testid="stColumn"] { min-width:0 !important; width:auto !important; flex:1 1 0 !important; }

/* ── پنجرهٔ جزئیات ── */
.dh { border-radius:14px; padding:14px 16px; margin-bottom:12px; display:flex; gap:16px; align-items:center; }
.dh .time { text-align:center; min-width:96px; padding-left:16px; border-left:1px solid rgba(0,0,0,.08); }
.dh .time b { display:block; font-size:30px; font-weight:900; line-height:1.1; letter-spacing:.5px; }
.dh .time small { font-size:12px; color:#495057; }
.dh .who { flex:1; min-width:0; }
.dh .kind { display:inline-block; border-radius:20px; padding:2px 12px; font-size:12px; font-weight:800; color:#fff; }
.dh .name { font-size:20px; font-weight:800; color:#17202e; margin:4px 0 2px; }
.dh .amount { font-size:20px; font-weight:900; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
.chips span { background:rgba(255,255,255,.75); border:1px solid rgba(0,0,0,.06); border-radius:20px;
              padding:2px 10px; font-size:12px; color:#343a40; }
.note { background:#fff8e6; border:1px solid #ffe3a3; border-radius:12px; padding:10px 14px; margin-bottom:10px;
        font-size:14px; line-height:1.9; }
.note b { color:#9a6700; }
.sec { font-size:15px; font-weight:800; margin:2px 0 8px; display:flex; align-items:center; gap:6px; }
.sec i { width:8px; height:8px; border-radius:50%; display:inline-block; }
.box { background:#fff; border:1px solid #e3e7ef; border-radius:12px; padding:12px 14px; margin-bottom:10px; }
.muted { color:#868e96; font-size:13px; }
.kv { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:8px; }
.kv div { background:#f6f7fa; border-radius:8px; padding:6px 10px; }
.kv small { display:block; font-size:11px; color:#6b7686; }
.kv b { font-size:14px; color:#17202e; font-weight:600; }
.itm { width:100%; border-collapse:collapse; font-size:13px; }
.itm th { text-align:right; color:#6b7686; font-weight:600; border-bottom:1px solid #e3e7ef; padding:5px 4px; }
.itm td { border-bottom:1px solid #f1f3f5; padding:6px 4px; }
.itm tfoot td { font-weight:800; border-bottom:0; background:#f6f7fb; }
.itm td.c { width:26px; color:#6b7686; } .itm td.nm { white-space:nowrap; }
.itm-scroll { max-height:380px; overflow:auto; border:1px solid #eef0f4; border-radius:10px; }
.itm-scroll thead th { position:sticky; top:0; background:#f6f7fb; z-index:1; }
.itm-scroll tfoot td { position:sticky; bottom:0; }
.gal { display:flex; flex-wrap:wrap; gap:10px; margin:0 0 12px; }
.gal figure { margin:0; width:132px; }
.gal .th img { width:132px; height:96px; object-fit:cover; border-radius:10px; border:1px solid #dfe3ea; cursor:zoom-in;
               display:block; transition:transform .15s ease, box-shadow .15s ease; }
.gal .th img:hover { transform:translateY(-2px); box-shadow:0 6px 16px rgba(16,24,40,.16); }
.gal figcaption { font-size:12px; color:#6b7686; text-align:center; margin-top:3px; }
.gal .lbt { display:none; }
.gal .lb { display:none; position:fixed; inset:0; z-index:100000; background:rgba(10,12,20,.88);
           align-items:center; justify-content:center; flex-direction:column; }
.gal .lbt:checked ~ .lb { display:flex; animation:fadeIn .2s ease; }
.gal .lb img { max-width:92vw; max-height:84vh; border-radius:8px; cursor:zoom-out; }
.gal .lb span { color:#fff; margin-top:8px; font-size:14px; }
.gal .nophoto { width:132px; height:96px; border-radius:10px; border:1px dashed #ced4da; color:#adb5bd;
                display:flex; align-items:center; justify-content:center; font-size:12px; text-align:center; padding:4px; }
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }

/* ── اعلان‌ها (لایهٔ ثابت؛ صفحه را جابه‌جا نمی‌کند) ── */
.st-key-pvnotes { position:fixed !important; left:16px; bottom:16px; z-index:99999; width:340px; gap:8px !important; }
.st-key-pvnotes [data-testid="stElementContainer"] { margin:0 !important; }
[class*="st-key-note_"] { background:#fff; border:1px solid #e3e7ef; border-radius:14px; padding:10px 12px !important;
    box-shadow:0 12px 32px rgba(16,24,40,.16); animation:noteIn .35s ease; gap:8px !important; }
[class*="st-key-note_"] > div { gap:8px !important; }
[class*="st-key-note_"] .stButton { width:100%; }
[class*="st-key-note_"] .stButton > button { width:100%; min-height:32px !important; padding:2px 10px !important; font-size:12px !important;
    background:#f8f9fb !important; }
.pv-note { display:flex; gap:10px; align-items:center; direction:rtl; padding-bottom:18px; }
.pv-note img { width:52px; height:52px; border-radius:10px; object-fit:cover; flex-shrink:0; }
.pv-note .i { width:52px; height:52px; border-radius:10px; display:flex; align-items:center; justify-content:center;
              font-size:24px; flex-shrink:0; }
.pv-note .t { font-weight:800; font-size:13px; }
.pv-note .n { font-weight:700; font-size:14px; color:#17202e; }
.pv-note .m { font-size:12px; color:#6b7686; }
@keyframes noteIn { from { opacity:0; transform:translateY(14px) scale(.98); } to { opacity:1; transform:none; } }

/* ── پیام‌ها ── */
.chat { background:#fff; border:1px solid #e3e7ef; border-radius:14px; padding:12px; height:470px; overflow-y:auto;
        display:flex; flex-direction:column; gap:6px; }
.bub { max-width:75%; padding:8px 12px; border-radius:14px; font-size:14px; line-height:1.8; white-space:pre-wrap; }
.bub.me { align-self:flex-start; background:#3b5bdb; color:#fff; border-bottom-right-radius:4px; }
.bub.them { align-self:flex-end; background:#e6f4ea; color:#14361f; border:1px solid #c8e6d0; border-bottom-left-radius:4px; }
.bub small { display:block; font-size:11px; opacity:.7; }
.bub .who { display:block; font-size:11px; font-weight:800; opacity:.85; }
</style>
""", unsafe_allow_html=True)

USER = require_dashboard("داشبورد پیچا ویزیت", "📍")
PERM = USER["perms"]
SHOW_MONEY, SHOW_PHOTOS, CAN_EXPORT = PERM["money"], PERM["photos"], PERM["export"]
IS_ADMIN = USER.get("role") == "admin"
ALLOWED = tuple(PERM["visitors"]) or None          # None = همهٔ ویزیتورها


@st.cache_resource
def _schema_ready():
    try:
        audit.ensure_schema()
    except Exception as e:
        print(f"⚠️ ensure_schema: {e}")
    return True


_schema_ready()


# ══════════════════════════════════════════════
# توابع کمکی
# ══════════════════════════════════════════════
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa(v) -> str:
    return str(v).translate(_FA)


def money(n) -> str:
    if not SHOW_MONEY:
        return "—"
    try:
        return fa(f"{float(n):,.0f}").replace(",", "٬") + " ریال"
    except (TypeError, ValueError):
        return "—"


def jdate(d) -> str:
    if d is None or (not isinstance(d, (str, date)) and pd.isna(d)):
        return "—"
    try:
        d = pd.Timestamp(d).date()
        return fa(jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d"))
    except Exception:
        return fa(str(d)[:10])


def jweekday(d) -> str:
    try:
        return ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"][
            jdatetime.date.fromgregorian(date=pd.Timestamp(d).date()).weekday()]
    except Exception:
        return ""


def hhmm(t) -> str:
    return fa(str(t or "")[:5]) or "—"


def esc(s) -> str:
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def img_file(rel) -> str | None:
    """مسیر ذخیره‌شده در دیتابیس (/static/...) → فایل روی دیسک (فقط داخل پوشهٔ static)"""
    if not SHOW_PHOTOS or not rel or str(rel).strip() in ("", "None", "nan"):
        return None
    p = os.path.realpath(os.path.join(BASE_DIR, str(rel).strip().lstrip("/\\")))
    return p if p.startswith(STATIC_DIR + os.sep) and os.path.isfile(p) else None


@st.cache_data(show_spinner=False, max_entries=3000)
def img_b64(path: str, mtime: float, box: tuple) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail(box)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82 if box[0] > 400 else 70)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def img_src(rel, box=(220, 150)) -> str | None:
    p = img_file(rel)
    if not p:
        return None
    try:
        return "data:image/jpeg;base64," + img_b64(p, os.path.getmtime(p), box)
    except Exception:
        return None


def gallery(images, uid) -> str:
    """[(مسیر, عنوان)] → بند انگشتی‌ها؛ کلیک = بزرگ‌نمایی، کلیک دوباره = بستن"""
    if not SHOW_PHOTOS:
        return ""
    out = []
    for i, (rel, cap) in enumerate(images):
        th = img_src(rel, (300, 220))
        if not th:
            out.append(f"<figure><div class='nophoto'>{'عکس پیدا نشد' if rel else 'بدون عکس'}</div>"
                       f"<figcaption>{cap}</figcaption></figure>")
            continue
        big = img_src(rel, (1600, 1600))
        k = f"lb_{uid}_{i}"
        out.append(f"<figure><input type='checkbox' id='{k}' class='lbt'>"
                   f"<label for='{k}' class='th'><img src='{th}' alt='{cap}'></label>"
                   f"<figcaption>{cap}</figcaption>"
                   f"<label for='{k}' class='lb'><img src='{big}' alt='{cap}'><span>{cap} — برای بستن کلیک کنید</span></label>"
                   f"</figure>")
    return "<div class='gal'>" + "".join(out) + "</div>" if out else ""


def read_sql(sql, params=()):
    conn = get_conn()
    try:
        return pd.read_sql(sql, conn, params=list(params))
    finally:
        conn.close()


def run_sql(sql, params=()):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(sql, params); conn.commit()
    finally:
        cur.close(); conn.close()


def stop_kind(s) -> str:
    if s["orders"] and s["pays"]:
        return "both"
    return "order" if s["orders"] else "pay" if s["pays"] else "visit"


def stabilize(el, n=None):
    """شناسه‌های ثابت برای اجزای نقشه: HTML یکسان → نقشه دوباره ساخته نمی‌شود (بدون چشمک)"""
    n = n if n is not None else [0]
    el._id = f"pv{n[0]}"
    n[0] += 1
    for ch in list(getattr(el, "_children", {}).values()):
        stabilize(ch, n)
    return el


# ══════════════════════════════════════════════
# داده‌ها
# ══════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def load_visitors():
    return read_sql("SELECT id, full_name, ISNULL(role,'visitor') AS role, ISNULL(is_active,1) AS active "
                    "FROM visitors ORDER BY full_name")


def _vis_filter(alias, vids):
    if not vids:
        return "", ()
    return f"AND {alias}.visitor_id IN ({','.join('?' * len(vids))})", tuple(vids)


@st.cache_data(ttl=60, show_spinner="در حال دریافت اطلاعات...")
def load_data(g0: str, g1: str, vids: tuple | None):
    def q(sql, alias):
        f, p = _vis_filter(alias, vids)
        return read_sql(sql.replace("{VF}", f), (g0, g1) + p)
    visits = q(f"""
        SELECT v.id, v.visitor_id, ISNULL(u.full_name, N'نامشخص') AS visitor,
               v.customer_code, COALESCE(CAST(c.C_Name AS NVARCHAR(200)), nc.name + N' (جدید)', v.customer_code) AS customer,
               v.visit_date AS d, CONVERT(VARCHAR(8), v.visit_time, 108) AS t,
               v.latitude AS lat, v.longitude AS lng, v.gps_accuracy AS acc, v.device,
               ISNULL(v.selfie_path,'') AS selfie, ISNULL(v.description,'') AS descr
        FROM visits v
        LEFT JOIN visitors u ON u.id = v.visitor_id
        LEFT JOIN {SALES}.customer c ON c.C_Code = v.customer_code
        LEFT JOIN new_customers nc ON nc.code = v.customer_code
        WHERE v.visit_date BETWEEN ? AND ? {{VF}}
        ORDER BY v.visit_date, v.visit_time""", "v")
    orders = q(f"""
        SELECT o.id, o.visitor_id, ISNULL(u.full_name, N'نامشخص') AS visitor,
               o.customer_code, COALESCE(CAST(c.C_Name AS NVARCHAR(200)), nc.name + N' (جدید)', o.customer_code) AS customer,
               o.order_date AS d, CONVERT(VARCHAR(8), o.order_time, 108) AS t,
               o.latitude AS lat, o.longitude AS lng, o.total_amount AS total,
               ISNULL(o.description,'') AS descr, o.device
        FROM orders o
        LEFT JOIN visitors u ON u.id = o.visitor_id
        LEFT JOIN {SALES}.customer c ON c.C_Code = o.customer_code
        LEFT JOIN new_customers nc ON nc.code = o.customer_code
        WHERE o.order_date BETWEEN ? AND ? {{VF}}
        ORDER BY o.order_date, o.order_time""", "o")
    pays = q(f"""
        SELECT p.id, p.visitor_id, ISNULL(u.full_name, N'نامشخص') AS visitor,
               p.customer_code, COALESCE(CAST(c.C_Name AS NVARCHAR(200)), nc.name + N' (جدید)', p.customer_code) AS customer,
               p.payment_date AS d, CONVERT(VARCHAR(8), p.payment_time, 108) AS t,
               p.latitude AS lat, p.longitude AS lng, p.payment_type AS ptype, p.amount,
               ISNULL(p.check_number,'') AS check_number, ISNULL(p.check_sayyadi,'') AS check_sayyadi,
               p.check_due_date AS check_due, ISNULL(p.check_image_path,'') AS check_img,
               ISNULL(p.transfer_account,'') AS tr_account, ISNULL(p.transfer_tracking,'') AS tr_tracking,
               ISNULL(p.transfer_image_path,'') AS tr_img, ISNULL(p.tracking_number,'') AS tracking,
               ISNULL(p.description,'') AS descr, p.device
        FROM payments p
        LEFT JOIN visitors u ON u.id = p.visitor_id
        LEFT JOIN {SALES}.customer c ON c.C_Code = p.customer_code
        LEFT JOIN new_customers nc ON nc.code = p.customer_code
        WHERE p.payment_date BETWEEN ? AND ? {{VF}}
        ORDER BY p.payment_date, p.payment_time""", "p")
    items = q(f"""
        SELECT oi.order_id, oi.article_code AS code,
               ISNULL(CAST(a.A_Name AS NVARCHAR(200)), oi.article_code) AS name,
               CAST(oi.quantity AS FLOAT) AS qty, CAST(oi.price AS FLOAT) AS price
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        LEFT JOIN {SALES}.article a ON a.A_Code = oi.article_code
        WHERE o.order_date BETWEEN ? AND ? {{VF}}
        ORDER BY oi.order_id, oi.id""", "o")
    return visits, orders, pays, items


def build_stops(visits, orders, pays):
    """ویزیت + سفارش/دریافتِ همان لحظه = یک توقف؛ سفارش/دریافت بی‌ویزیت هم توقف جدا"""
    key = lambda r: f"{r['visitor_id']}|{r['customer_code']}|{r['d']}|{r['t']}"
    stops, by_key = [], {}
    for _, v in visits.iterrows():
        s = {**v.to_dict(), "kind": "visit", "visit": v.to_dict(), "orders": [], "pays": []}
        by_key.setdefault(key(v), s)
        stops.append(s)
    for df, field, kind in ((orders, "orders", "order"), (pays, "pays", "pay")):
        for _, r in df.iterrows():
            s = by_key.get(key(r))
            if s is None:
                s = {**r.to_dict(), "kind": kind, "visit": None, "orders": [], "pays": [], "acc": None}
                by_key[key(r)] = s
                stops.append(s)
            s[field].append(r.to_dict())
    stops.sort(key=lambda s: (str(s["d"]), str(s["t"])))
    return stops


# ══════════════════════════════════════════════
# تاریخ‌ها
# ══════════════════════════════════════════════
today_j = jdatetime.date.today()
today_g = today_j.togregorian()
PERIODS = ["امروز", "دیروز", "۷ روز اخیر", "۳۰ روز اخیر", "این ماه", "ماه قبل", "بازه دلخواه"]


def period_range(name):
    if name == "امروز":
        return today_g, today_g
    if name == "دیروز":
        y = today_g - timedelta(days=1)
        return y, y
    if name == "۷ روز اخیر":
        return today_g - timedelta(days=6), today_g
    if name == "۳۰ روز اخیر":
        return today_g - timedelta(days=29), today_g
    if name == "این ماه":
        return jdatetime.date(today_j.year, today_j.month, 1).togregorian(), today_g
    if name == "ماه قبل":
        first = jdatetime.date(today_j.year, today_j.month, 1)
        prev_last = first - timedelta(days=1)
        return jdatetime.date(prev_last.year, prev_last.month, 1).togregorian(), prev_last.togregorian()
    return None


def jalali_picker(prefix, default_j):
    years = list(range(today_j.year - 3, today_j.year + 1))
    c1, c2, c3 = st.container(key=f"jp_{prefix}").columns([1, 1.4, 1.1])
    d = c1.selectbox("روز", range(1, 32), index=default_j.day - 1, key=f"{prefix}_d", format_func=fa)
    m = c2.selectbox("ماه", range(1, 13), index=default_j.month - 1, key=f"{prefix}_m",
                     format_func=lambda x: MONTHS[x - 1])
    y = c3.selectbox("سال", years, index=years.index(default_j.year), key=f"{prefix}_y", format_func=fa)
    for day in range(d, 0, -1):            # روز بیشتر از طول ماه → آخرین روز ماه
        try:
            return jdatetime.date(y, m, day)
        except ValueError:
            continue


def range_text(j0, j1, g0, g1):
    return (fa(j0.strftime('%Y/%m/%d')) if g0 == g1
            else f"از {fa(j0.strftime('%Y/%m/%d'))} تا {fa(j1.strftime('%Y/%m/%d'))}")


vis_df = load_visitors()
if ALLOWED:
    vis_df = vis_df[vis_df["id"].isin(ALLOWED)]
vis_opts = {"همهٔ ویزیتورها": None}
vis_opts.update({(r["full_name"] + ("" if r["active"] else " (غیرفعال)")): int(r["id"]) for _, r in vis_df.iterrows()})


# ══════════════════════════════════════════════
# اعلان روی کلیک: رفتن به همان ثبت روی نقشه و باز کردن جزئیات
# ══════════════════════════════════════════════
def _current_range():
    ss = st.session_state
    per = ss.get("f_period", "این ماه")
    if per != "بازه دلخواه":
        return period_range(per)
    try:
        return (jdatetime.date(ss["from_y"], ss["from_m"], ss["from_d"]).togregorian(),
                jdatetime.date(ss["to_y"], ss["to_m"], ss["to_d"]).togregorian())
    except Exception:
        return None, None


def open_note(table, rec_id, rec_date):
    ss = st.session_state
    ss["page"] = P_MAP
    ss["f_vis"], ss["f_cust"], ss["f_prod"] = "همهٔ ویزیتورها", [], []
    d = pd.Timestamp(rec_date).date() if rec_date else today_g
    g0, g1 = _current_range()
    if not (g0 and g0 <= d <= g1):          # بازه را طوری عوض کن که همان ثبت دیده شود
        if d == today_g:
            ss["f_period"] = "امروز"
        else:
            jd = jdatetime.date.fromgregorian(date=d)
            ss["f_period"] = "بازه دلخواه"
            for p in ("from", "to"):
                ss[f"{p}_y"], ss[f"{p}_m"], ss[f"{p}_d"] = jd.year, jd.month, jd.day
    ss["pending_open"] = (table, int(rec_id))
    ss.notes = [n for n in ss.get("notes", []) if not (n["t"] == table and n["id"] == rec_id)]
    load_data.clear()


# ══════════════════════════════════════════════
# نوار بالا و انتخاب صفحه
# ══════════════════════════════════════════════
bar = st.empty()
pager = st.container(key="pager")
pg_col, menu_col = pager.columns([6, 1])
pages = PAGES if IS_ADMIN else [p_ for p_ in PAGES if p_ != P_LOGS]
if st.session_state.get("page") not in pages:      # مقدار اولیه فقط از راه session_state
    st.session_state.page = pages[0]
page = pg_col.segmented_control("صفحه", pages, key="page", required=True,
                                label_visibility="collapsed")
REFRESH = {"روشن — فقط وقتی ثبت جدید برسد": True, "خاموش": False}

with menu_col.popover("☰ منو", width="stretch"):
    st.selectbox("🔄 بروزرسانی خودکار", list(REFRESH), key="auto_refresh")
    st.toggle("🔔 اعلان ثبت‌ها و پیام‌های جدید", value=True, key="notify_on")
    st.divider()
    st.caption(f"👤 {USER['name']} (@{USER['username']})")
    if st.button("🚪 خروج", width="stretch"):
        logout()


# ══════════════════════════════════════════════
# پنجرهٔ جزئیات
# ══════════════════════════════════════════════
def _closed():
    ss = st.session_state
    ss["ui_ver"] = ss.get("ui_ver", 0) + 1          # فقط جدول‌ها (پاک شدن انتخاب)
    if ss.pop("map_click_used", False):
        ss["map_key"] = ss.get("map_key", 0) + 1    # تا همان نقطه دوباره قابل کلیک باشد
    ss.pop("want_print", None)
    ss["dlg_open"] = False


def kv(rows) -> str:
    return "<div class='kv'>" + "".join(
        f"<div><small>{k}</small><b>{v if v not in (None, '') else '—'}</b></div>" for k, v in rows) + "</div>"


def acc_txt(s) -> str:
    a = s.get("acc")
    try:
        return f"دقت ±{fa(int(round(float(a))))} متر" if a is not None and not pd.isna(a) else ""
    except (TypeError, ValueError):
        return ""


def stop_images(s):
    imgs = []
    if s["visit"] is not None:
        imgs.append((s["visit"]["selfie"], "سلفی ویزیت"))
    for p in s["pays"]:
        if p["ptype"] == "چک":
            imgs.append((p["check_img"], "عکس چک"))
        elif p["ptype"] == "حواله":
            imgs.append((p["tr_img"], "رسید حواله"))
    return imgs


def order_html(o, items_by_order) -> str:
    """جدول اقلام سفارش؛ سفارش‌های پرقلم داخل کادر قابل اسکرول با سرستون ثابت"""
    its = items_by_order.get(int(o["id"]), [])
    note = f"<div class='note' style='margin-top:8px'><b>توضیح سفارش:</b> {esc(o['descr'])}</div>" if txt(o.get("descr")) else ""
    if not its:
        return "<div class='muted'>اقلامی ثبت نشده است.</div>" + note
    head = "<th>#</th><th>کالا</th><th>تعداد</th>" + ("<th>فی</th><th>جمع</th>" if SHOW_MONEY else "")
    rows = ""
    for k, i in enumerate(its, 1):
        rows += (f"<tr><td class='c'>{fa(k)}</td><td>{esc(i['name'])}<div class='muted'>کد {fa(i['code'])}</div></td>"
                 f"<td class='nm'>{fa(format(i['qty'], 'g'))}</td>"
                 + (f"<td class='nm'>{money(i['price'])}</td><td class='nm'>{money(i['qty'] * i['price'])}</td>" if SHOW_MONEY else "")
                 + "</tr>")
    qty = sum(float(i["qty"] or 0) for i in its)
    foot = (f"<tfoot><tr><td></td><td>جمع {fa(len(its))} قلم</td><td class='nm'>{fa(f'{qty:g}')}</td>"
            + (f"<td></td><td class='nm'>{money(o['total'])}</td>" if SHOW_MONEY else "") + "</tr></tfoot>")
    return (f"<div class='itm-scroll'><table class='itm'><thead><tr>{head}</tr></thead><tbody>{rows}</tbody>{foot}</table></div>"
            + note)


def order_doc(o, s, items_by_order) -> dict:
    """دادهٔ برگهٔ چاپی یک سفارش"""
    return {"id": int(o["id"]), "date": jdate(o["d"]), "weekday": jweekday(o["d"]), "time": hhmm(o["t"]),
            "visitor": s["visitor"], "customer": s["customer"], "customer_code": s["customer_code"],
            "lines": items_by_order.get(int(o["id"]), []), "total": o["total"], "description": txt(o.get("descr"))}


def print_orders(docs, key):
    """پیش‌نمایش برگهٔ چاپی (دکمهٔ چاپ داخل همان برگه است)"""
    components.html(report.orders_html(docs, SHOW_MONEY, font_css(), APP_NAME), height=660, scrolling=True)


def pay_html(p) -> str:
    if p["ptype"] == "چک":
        rows = [("شماره چک", fa(p["check_number"])), ("شماره صیادی", fa(p["check_sayyadi"])),
                ("سررسید", jdate(p["check_due"]))]
    elif p["ptype"] == "حواله":
        rows = [("حساب / کارت مقصد", f"<span dir='ltr'>{fa(p['tr_account'])}</span>"),
                ("شماره پیگیری", fa(p["tr_tracking"] or p["tracking"]))]
    else:
        rows = [("نوع", "نقدی")]
    amount = f" — {money(p['amount'])}" if SHOW_MONEY else ""
    note = f"<div class='note' style='margin-top:8px'><b>توضیح دریافت:</b> {esc(p['descr'])}</div>" if txt(p.get("descr")) else ""
    return (f"<div style='font-weight:800;font-size:16px;color:{KIND_COLOR['pay']};margin-bottom:6px'>{p['ptype']}{amount}</div>"
            + kv(rows) + note)


KIND_LABEL = {"visit": "ویزیت", "order": "سفارش", "pay": "دریافت"}


def detail_dialog(stop_by_n, items_by_order):
    @st.dialog("جزئیات", width="large", on_dismiss=_closed)
    def show_stop(n: int, focus: str, ref: int | None):
        s = stop_by_n[n]
        focus_order = next((o for o in s["orders"] if int(o["id"]) == ref), None) if focus == "order" else None
        focus_pay = next((p for p in s["pays"] if int(p["id"]) == ref), None) if focus == "pay" else None
        color, soft = KIND_COLOR[focus], KIND_SOFT[focus]
        title = s["customer"]
        if focus_order:
            title = f"سفارش شمارهٔ {fa(focus_order['id'])} — {s['customer']}"
        elif focus_pay:
            title = f"دریافت {focus_pay['ptype']} — {s['customer']}"
        amount = ""
        if SHOW_MONEY and focus_order:
            amount = f"<div class='amount' style='color:{color}'>{money(focus_order['total'])}</div>"
        elif SHOW_MONEY and focus_pay:
            amount = f"<div class='amount' style='color:{color}'>{money(focus_pay['amount'])}</div>"
        device = txt(s.get("device")) or txt((focus_order or focus_pay or {}).get("device"))
        chips = [f"👤 {esc(s['visitor'])}", f"🏷️ کد مشتری {fa(s['customer_code'])}"]
        if acc_txt(s):
            chips.append(f"📍 {acc_txt(s)}")
        if device:
            chips.append(f"📱 <span dir='ltr'>{esc(device)}</span>")
        st.markdown(
            f"<div class='dh' style='background:{soft};border:1px solid {color}33'>"
            f"<div class='time' style='color:{color}'><b>{hhmm(s['t'])}</b><small>{jweekday(s['d'])} {jdate(s['d'])}</small></div>"
            f"<div class='who'><span class='kind' style='background:{color}'>{fa(n)} · {KIND_LABEL[focus]}</span>"
            f"<div class='name'>{esc(title)}</div>{amount}"
            f"<div class='chips'>{''.join(f'<span>{c}</span>' for c in chips)}</div></div></div>",
            unsafe_allow_html=True)

        if s["visit"] is not None and txt(s["visit"]["descr"]):
            st.markdown(f"<div class='note'><b>📝 توضیح ویزیت:</b> {esc(s['visit']['descr'])}</div>", unsafe_allow_html=True)

        imgs = stop_images(s)
        if focus_pay:
            own = focus_pay["check_img"] if focus_pay["ptype"] == "چک" else focus_pay["tr_img"]
            imgs.sort(key=lambda x: x[0] != own)
        if imgs:
            st.markdown(gallery(imgs, f"{n}_{focus}"), unsafe_allow_html=True)

        if focus_order:
            st.markdown(f"<div class='box'><div class='sec'><i style='background:{KIND_COLOR['order']}'></i>اقلام سفارش</div>"
                        f"{order_html(focus_order, items_by_order)}</div>", unsafe_allow_html=True)
            if st.toggle("🖨️ برگهٔ چاپی سفارش", key=f"prt_{n}_{ref}"):
                print_orders([order_doc(focus_order, s, items_by_order)], f"po_{n}_{ref}")
        elif focus_pay:
            st.markdown(f"<div class='box'><div class='sec'><i style='background:{KIND_COLOR['pay']}'></i>جزئیات دریافت</div>"
                        f"{pay_html(focus_pay)}</div>", unsafe_allow_html=True)

        others_o = [o for o in s["orders"] if o is not focus_order]
        others_p = [p for p in s["pays"] if p is not focus_pay]
        if focus == "visit" or others_o or others_p:
            if focus != "visit":
                st.markdown("<div class='sec' style='margin-top:4px'>🔗 در همین ویزیت</div>", unsafe_allow_html=True)
            # سفارش‌ها تمام‌عرض (جدول اقلام زیاد هم کامل دیده می‌شود)، دریافت‌ها زیر آن
            body = "".join(f"<div class='muted' style='margin-top:6px'>سفارش شمارهٔ {fa(o['id'])}</div>{order_html(o, items_by_order)}"
                           for o in others_o) or "<div class='muted'>سفارشی ثبت نشده است.</div>"
            st.markdown(f"<div class='box'><div class='sec'><i style='background:{KIND_COLOR['order']}'></i>سفارش</div>{body}</div>",
                        unsafe_allow_html=True)
            if others_o and st.toggle("🖨️ برگهٔ چاپی سفارش" + ("‌ها" if len(others_o) > 1 else ""), key=f"prt_{n}_all"):
                print_orders([order_doc(o, s, items_by_order) for o in others_o], f"po_{n}_all")
            body = "".join(pay_html(p) for p in others_p) or "<div class='muted'>دریافتی ثبت نشده است.</div>"
            st.markdown(f"<div class='box'><div class='sec'><i style='background:{KIND_COLOR['pay']}'></i>دریافت</div>{body}</div>",
                        unsafe_allow_html=True)

        lat, lng = s.get("lat"), s.get("lng")
        if lat and lng:
            b1, b2, _ = st.columns([1, 1, 2])
            b1.link_button("🗺️ گوگل‌مپ", f"https://www.google.com/maps?q={lat},{lng}", width="stretch")
            b2.link_button("🧭 نشان", f"https://neshan.org/maps/@{lat},{lng},17z", width="stretch")
    return show_stop


# ══════════════════════════════════════════════
# صفحهٔ ۱: نقشه و لیست
# ══════════════════════════════════════════════
def page_map():
    ss = st.session_state
    fbox = st.container(key="filters")
    f_vis, f_per, f_date, f_cust, f_prod, f_exp, f_ref = fbox.columns([1.5, 1.25, 1.45, 2, 2, 0.8, 0.7])
    sel_vname = f_vis.selectbox("ویزیتور", list(vis_opts), key="f_vis", label_visibility="collapsed")
    sel_vid = vis_opts.get(sel_vname)
    period = f_per.selectbox("بازه", PERIODS, index=4, key="f_period", label_visibility="collapsed")
    if period == "بازه دلخواه":
        with f_date.popover(ss.get("range_lbl", "📅 انتخاب بازه"), width="stretch"):
            st.caption("از تاریخ")
            j0 = jalali_picker("from", jdatetime.date(today_j.year, today_j.month, 1))
            st.caption("تا تاریخ")
            j1 = jalali_picker("to", today_j)
        if j1 < j0:
            j0, j1 = j1, j0
        g0, g1 = j0.togregorian(), j1.togregorian()
        lbl = f"📅 {fa(j0.strftime('%m/%d'))} تا {fa(j1.strftime('%m/%d'))}"
        if ss.get("range_lbl") != lbl:
            ss["range_lbl"] = lbl
            st.rerun()
    else:
        g0, g1 = period_range(period)
        j0, j1 = jdatetime.date.fromgregorian(date=g0), jdatetime.date.fromgregorian(date=g1)
        f_date.markdown(f"<div class='hint' style='text-align:center'>{fa(j0.strftime('%Y/%m/%d'))}"
                        f"{'' if g0 == g1 else ' تا ' + fa(j1.strftime('%m/%d'))}</div>", unsafe_allow_html=True)
    if f_ref.button("🔄", width="stretch", help="بروزرسانی"):
        load_data.clear()
        st.rerun()

    vids = (sel_vid,) if sel_vid else ALLOWED
    try:
        visits, orders, pays, items = load_data(g0.isoformat(), g1.isoformat(), vids)
    except Exception as e:
        st.error(f"❌ خطای دیتابیس: {e}")
        st.stop()
    all_stops = build_stops(visits, orders, pays)

    cust_names = {}
    for s in all_stops:
        cust_names.setdefault(str(s["customer_code"]), s["customer"])
    prod_names = dict(zip(items["code"].astype(str), items["name"])) if len(items) else {}
    for k, opts in (("f_cust", cust_names), ("f_prod", prod_names)):      # گزینهٔ ناموجود در این بازه حذف شود
        if k in ss:
            ss[k] = [c for c in ss[k] if c in opts]
    sel_cust = f_cust.multiselect("مشتری", sorted(cust_names, key=lambda c: cust_names[c]), key="f_cust",
                                  label_visibility="collapsed", format_func=lambda c: f"{cust_names[c]} ({fa(c)})",
                                  placeholder="🔍 همهٔ مشتریان")
    sel_prod = f_prod.multiselect("کالا", sorted(prod_names, key=lambda c: prod_names[c]), key="f_prod",
                                  label_visibility="collapsed", format_func=lambda c: f"{prod_names[c]} ({fa(c)})",
                                  placeholder="🔍 همهٔ کالاها")

    items_by_order = {}
    for it in items.to_dict("records"):
        items_by_order.setdefault(int(it["order_id"]), []).append(it)

    stops = []
    for s in all_stops:
        if sel_cust and str(s["customer_code"]) not in sel_cust:
            continue
        if sel_prod:
            ords = [o for o in s["orders"]
                    if any(str(i["code"]) in sel_prod for i in items_by_order.get(int(o["id"]), []))]
            if not ords:
                continue
            s = {**s, "orders": ords}
        stops.append(s)
    for i, s in enumerate(stops, 1):
        s["n"] = i
        s["ck"] = stop_kind(s)
    stop_by_n = {s["n"]: s for s in stops}

    f_visits = [s for s in stops if s["visit"] is not None]
    f_orders = [(s, o) for s in stops for o in s["orders"]]
    f_pays = [(s, p) for s in stops for p in s["pays"]]
    order_sum = sum(float(o["total"] or 0) for _, o in f_orders)
    pay_sum = sum(float(p["amount"] or 0) for _, p in f_pays)
    prod_sum = {}
    for _, o in f_orders:
        for it in items_by_order.get(int(o["id"]), []):
            if sel_prod and str(it["code"]) not in sel_prod:
                continue
            r = prod_sum.setdefault(str(it["code"]), {"name": it["name"], "qty": 0.0, "amount": 0.0, "orders": set()})
            r["qty"] += float(it["qty"] or 0)
            r["amount"] += float(it["qty"] or 0) * float(it["price"] or 0)
            r["orders"].add(int(o["id"]))

    rtxt = range_text(j0, j1, g0, g1)
    amt = lambda v: f" · {money(v)}" if SHOW_MONEY else ""
    bar.markdown(app_bar("📍 داشبورد پیچا ویزیت", f"{rtxt} · {esc(sel_vname)}", [
        f"<b>{fa(len(f_visits))}</b> ویزیت",
        f"<b>{fa(len({s['customer_code'] for s in stops}))}</b> مشتری",
        f"<b>{fa(len(f_orders))}</b> سفارش{amt(order_sum)}",
        f"<b>{fa(len(f_pays))}</b> دریافت{amt(pay_sum)}",
        f"👤 {esc(USER['name'])}",
    ]), unsafe_allow_html=True)

    # ── خروجی همین نتیجه ──
    if CAN_EXPORT:
        meta = [("بازه", rtxt), ("ویزیتور", sel_vname)]
        if sel_cust:
            meta.append(("مشتری", "، ".join(cust_names[c] for c in sel_cust)))
        if sel_prod:
            meta.append(("کالا", "، ".join(prod_names[c] for c in sel_prod)))
        rows_v = [{"#": s["n"], "تاریخ": jdate(s["d"]), "ساعت": str(s["t"])[:5], "مشتری": s["customer"],
                   "ویزیتور": s["visitor"], "توضیحات": s["visit"]["descr"]} for s in f_visits]
        with f_exp.popover("📥", width="stretch", help="خروجی همین نتیجه"):
            st.caption("خروجی کامل‌تر با فیلترهای بیشتر: صفحهٔ «📊 گزارش‌ساز»")
            sec = [("ویزیت‌ها", ["#", "تاریخ", "ساعت", "مشتری", "ویزیتور", "توضیحات"], rows_v)]
            st.download_button("📥 Excel ویزیت‌ها", data=cached_excel(tuple(meta), freeze(sec)),
                               file_name=f"Visits_{j0.strftime('%Y%m%d')}.xlsx", width="stretch", on_click="ignore")

    # ── باز کردن ثبتی که از اعلان آمده ──
    to_open, focus_n = None, None
    pend = ss.pop("pending_open", None)
    if pend:
        table, rid = pend
        field = {"visits": "visit", "orders": "orders", "payments": "pays"}[table]
        for s in stops:
            if field == "visit" and s["visit"] is not None and int(s["visit"]["id"]) == rid:
                to_open, focus_n = (s["n"], "visit", None), s["n"]
            elif field != "visit" and any(int(x["id"]) == rid for x in s[field]):
                to_open, focus_n = (s["n"], "order" if field == "orders" else "pay", rid), s["n"]
        ss["note_focus"] = focus_n
    focus_n = focus_n or ss.pop("note_focus", None)

    ver = ss.setdefault("ui_ver", 0)
    col_list, col_map = st.columns([1, 1.55], gap="medium")

    def table(rows, cols, key, height=560, selectable=True):
        """کلیک روی 👁 = جزئیات؛ کلیک روی بقیهٔ ستون‌ها = نمایش روی نقشه"""
        if not rows:
            st.caption("موردی نیست.")
            return None, None
        df = pd.DataFrame(rows)[cols[::-1]]
        if not selectable:
            st.dataframe(df, hide_index=True, width="stretch", height=height)
            return None, None
        ev = st.dataframe(df, hide_index=True, width="stretch", height=height, key=key,
                          on_select="rerun", selection_mode="single-cell",
                          column_config={"👁": st.column_config.TextColumn("👁", width=36, help="نمایش جزئیات"),
                                         "#": st.column_config.TextColumn("#", width=36),
                                         "ساعت": st.column_config.TextColumn("ساعت", width=52),
                                         "تاریخ": st.column_config.TextColumn("تاریخ", width=86),
                                         # نام‌های بلند کوتاه نمایش داده می‌شوند تا ستون 👁 بیرون نزند
                                         "مشتری": st.column_config.TextColumn("مشتری", width=130),
                                         "ویزیتور": st.column_config.TextColumn("ویزیتور", width=78),
                                         "مبلغ": st.column_config.TextColumn("مبلغ", width=98),
                                         "شماره": st.column_config.TextColumn("شماره", width=50),
                                         "نوع": st.column_config.TextColumn("نوع", width=52)})
        cells = ev.selection.cells if ev and ev.selection else []
        if not cells:
            return None, None
        r, c = cells[0]
        target = rows[r]["_open"]
        return (target, None) if c == "👁" else (None, target[0])

    with col_list:
        st.markdown("<div class='hint'>👁 = جزئیات کامل · کلیک روی ردیف = نمایش همان شماره روی نقشه</div>",
                    unsafe_allow_html=True)
        tabs = st.tabs([f"ویزیت‌ها ({fa(len(f_visits))})", f"سفارش‌ها ({fa(len(f_orders))})",
                        f"دریافت‌ها ({fa(len(f_pays))})", f"کالاها ({fa(len(prod_sum))})"])
        m_col = ["مبلغ"] if SHOW_MONEY else []
        with tabs[0]:
            rows = [{"_open": (s["n"], "visit", None), "👁": "👁", "#": fa(s["n"]), "مشتری": s["customer"],
                     "ویزیتور": s["visitor"], "تاریخ": jdate(s["d"]), "ساعت": hhmm(s["t"]),
                     "توضیحات": txt(s["visit"]["descr"]),
                     "ثبت‌ها": " + ".join(x for x in ["سفارش" if s["orders"] else "", "دریافت" if s["pays"] else ""] if x)}
                    for s in f_visits]
            o, f = table(rows, ["👁", "#", "مشتری", "ویزیتور", "تاریخ", "ساعت", "ثبت‌ها"], f"tv_{ver}")
            to_open, focus_n = o or to_open, f or focus_n
        with tabs[1]:
            if f_orders and st.button(f"🖨️ چاپ برگهٔ {fa(len(f_orders))} سفارش این لیست", key="print_all_orders",
                                      width="stretch"):
                ss["dlg_open"] = True
                docs = [order_doc(o_, s, items_by_order) for s, o_ in f_orders]

                @st.dialog("برگهٔ چاپی سفارش‌ها", width="large", on_dismiss=_closed)
                def _print_all():
                    print_orders(docs, "po_all")
                _print_all()
            rows = [{"_open": (s["n"], "order", int(o_["id"])), "👁": "👁", "#": fa(s["n"]), "شماره": fa(o_["id"]),
                     "مشتری": s["customer"], "ویزیتور": s["visitor"], "تاریخ": jdate(o_["d"]), "مبلغ": money(o_["total"]),
                     "توضیحات": txt(o_["descr"])} for s, o_ in f_orders]
            o, f = table(rows, ["👁", "#", "شماره", "مشتری", "ویزیتور", "تاریخ"] + m_col, f"to_{ver}")
            to_open, focus_n = o or to_open, f or focus_n
        with tabs[2]:
            rows = [{"_open": (s["n"], "pay", int(p["id"])), "👁": "👁", "#": fa(s["n"]), "مشتری": s["customer"],
                     "ویزیتور": s["visitor"], "تاریخ": jdate(p["d"]), "نوع": p["ptype"], "مبلغ": money(p["amount"]),
                     "توضیحات": txt(p["descr"])} for s, p in f_pays]
            o, f = table(rows, ["👁", "#", "مشتری", "ویزیتور", "تاریخ", "نوع"] + m_col, f"tp_{ver}")
            to_open, focus_n = o or to_open, f or focus_n
        with tabs[3]:
            rows = [{"کالا": r["name"], "کد": fa(c), "تعداد": fa(f"{r['qty']:g}"), "سفارش": fa(len(r["orders"])),
                     "مبلغ": money(r["amount"])} for c, r in sorted(prod_sum.items(), key=lambda x: -x[1]["amount"])]
            table(rows, ["کالا", "کد", "تعداد", "سفارش"] + m_col, "tk", selectable=False)

    with col_map:
        map_click = draw_map(stops, stop_by_n, focus_n, ver)
        if map_click:
            to_open = map_click

    if to_open and to_open[0] in stop_by_n:
        ss["dlg_open"] = True
        detail_dialog(stop_by_n, items_by_order)(*to_open)


# ══════════════════════════════════════════════
# نقشه (رنگ‌های نرم، سایه و هالهٔ ملایم)
# ══════════════════════════════════════════════
MAP_CSS = """
<style>
.leaflet-container { background:#eef1f6; }
/* رنگ ملایم‌تر نقشه (بدون نیاز به سرویس یا کلید جدا) */
.leaflet-tile-pane { filter:saturate(.62) brightness(1.05) contrast(.92); }
.leaflet-tooltip.pv-tip { direction:rtl; text-align:right; padding:10px 12px; border-radius:14px; border:0;
  box-shadow:0 10px 30px rgba(16,24,40,.18); font-family:Vazirmatn,Tahoma,sans-serif; animation:tipIn .18s ease; }
.leaflet-tooltip.pv-tip:before { display:none; }
.pv-tip .h { font-weight:800; font-size:13px; color:#17202e; display:flex; align-items:center; gap:6px; }
.pv-tip .h i { width:9px; height:9px; border-radius:50%; display:inline-block; }
.pv-tip .m { font-size:11px; color:#6b7686; margin:2px 0 4px; }
.pv-tip img { display:block; width:200px; max-height:140px; object-fit:cover; border-radius:10px; margin:6px 0; }
.pv-tip .b { display:inline-block; font-size:11px; font-weight:700; border-radius:12px; padding:2px 8px; margin:2px 0 0 4px; }
.pv-tip .f { font-size:10px; color:#adb5bd; margin-top:4px; }
.pv-cl { width:38px; height:38px; border-radius:50%; background:rgba(2,0,37,.88); color:#fff; border:2px solid #fff;
  font:800 13px Vazirmatn,Tahoma,sans-serif; display:flex; align-items:center; justify-content:center;
  box-shadow:0 0 0 6px rgba(76,110,245,.18), 0 4px 12px rgba(16,24,40,.25); transition:transform .15s ease; }
.pv-cl:hover { transform:scale(1.08); }
.pv-pin { width:28px; height:28px; border-radius:50%; color:#fff; font:700 12px Vazirmatn,Tahoma,sans-serif;
  display:flex; align-items:center; justify-content:center; border:2px solid #fff;
  box-shadow:0 0 0 5px var(--halo), 0 3px 10px rgba(16,24,40,.25); transition:transform .15s ease, box-shadow .15s ease;
  animation:pinIn .35s ease both; }
.pv-pin:hover { transform:scale(1.15); box-shadow:0 0 0 7px var(--halo), 0 6px 16px rgba(16,24,40,.3); }
.pv-focus { width:40px; height:40px; font-size:15px; border-width:3px; animation:pinIn .35s ease both, pulse 1.8s ease-out infinite; }
.leaflet-tooltip.pv-flabel { font:800 13px Vazirmatn,Tahoma,sans-serif; direction:rtl; border-radius:10px; border:0;
  box-shadow:0 6px 16px rgba(16,24,40,.18); }
@keyframes pinIn { from { opacity:0; transform:scale(.6); } to { opacity:1; transform:none; } }
@keyframes tipIn { from { opacity:0; } to { opacity:1; } }
@keyframes pulse { 0% { box-shadow:0 0 0 0 var(--halo2), 0 3px 10px rgba(16,24,40,.25); }
                   70% { box-shadow:0 0 0 18px rgba(0,0,0,0), 0 3px 10px rgba(16,24,40,.25); }
                   100% { box-shadow:0 0 0 0 rgba(0,0,0,0), 0 3px 10px rgba(16,24,40,.25); } }
</style>"""


def _hex_rgba(h, a):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


FOCUS_ZOOM = 15          # زوم نمایش یک نقطه: سطح خیابان با اطراف آن (۱۸ = حداکثر)


def overview_zoom(lats, lngs, w=620, h=540) -> int:
    """بزرگ‌ترین زومی که همهٔ نقاط در کادر (با حاشیه) جا شوند — Web Mercator"""
    import math
    def y(lat):
        s = math.sin(math.radians(max(min(lat, 85), -85)))
        return math.log((1 + s) / (1 - s)) / 2
    dx = max(max(lngs) - min(lngs), 1e-6) / 360
    dy = max(y(max(lats)) - y(min(lats)), 1e-6) / (2 * math.pi)
    z = min(math.log2(w / 256 / dx), math.log2(h / 256 / dy))
    return int(max(3, min(16, math.floor(z))))


def draw_map(stops, stop_by_n, focus_n, ver):
    pts = [s for s in stops if s.get("lat") and s.get("lng")]
    visitor_ids = sorted({int(s["visitor_id"]) for s in stops})
    rcolor = {vid: ROUTE_COLORS[i % len(ROUTE_COLORS)] for i, vid in enumerate(visitor_ids)}
    names = {int(s["visitor_id"]): s["visitor"] for s in stops}
    counts = {k: sum(1 for s in pts if s["ck"] == k) for k in STOP_COLORS}
    legend = "".join(f"<span><i style='background:{c}'></i>{lbl} ({fa(counts[k])})</span>"
                     for k, (c, lbl) in STOP_COLORS.items() if counts[k])
    if len(visitor_ids) > 1:
        legend += "".join(f"<span><i class='r' style='background:{rcolor[v]}'></i>مسیر {esc(names[v])}</span>"
                          for v in visitor_ids)
    st.markdown(f"<div class='legend'>{legend}</div>", unsafe_allow_html=True)

    m = folium.Map(location=[35.6997, 51.3380], zoom_start=11, control_scale=True, tiles="OpenStreetMap", max_zoom=19)
    m.get_root().header.add_child(folium.Element(font_css().replace(".stApp *", "body *") + "\n" + MAP_CSS))

    routes = {}
    for s in pts:
        routes.setdefault((int(s["visitor_id"]), str(s["d"])), []).append([float(s["lat"]), float(s["lng"])])
    for (vid, _), line in routes.items():
        if len(line) > 1:
            folium.PolyLine(line, color=rcolor[vid], weight=4, opacity=.35, dash_array="2 8",
                            line_cap="round", line_join="round").add_to(m)

    cluster = MarkerCluster(
        options={"maxClusterRadius": 45, "spiderfyOnMaxZoom": True, "showCoverageOnHover": False,
                 "spiderfyDistanceMultiplier": 2},
        icon_create_function="""function(c){return L.divIcon({className:'',iconSize:[38,38],
            html:'<div class="pv-cl">'+c.getChildCount().toLocaleString('fa-IR')+'</div>'});}""",
    ).add_to(m)

    def tip_html(s):
        c = STOP_COLORS[s["ck"]][0]
        badges = ""
        if s["orders"]:
            a = f" {money(sum(o['total'] or 0 for o in s['orders']))}" if SHOW_MONEY else ""
            badges += f"<span class='b' style='background:{KIND_SOFT['order']};color:{KIND_COLOR['order']}'>سفارش{a}</span>"
        for p in s["pays"]:
            a = f" {money(p['amount'])}" if SHOW_MONEY else ""
            badges += f"<span class='b' style='background:{KIND_SOFT['pay']};color:{KIND_COLOR['pay']}'>{p['ptype']}{a}</span>"
        th = img_src(s["visit"]["selfie"]) if s["visit"] is not None else None
        img = f"<img src='{th}'>" if th else ""
        acc = acc_txt(s)
        return (f"<div class='h'><i style='background:{c}'></i>{fa(s['n'])}. {esc(s['customer'])}</div>"
                f"<div class='m'>{jdate(s['d'])} · {hhmm(s['t'])} · {esc(s['visitor'])}{' · ' + acc if acc else ''}</div>"
                f"{img}{badges}<div class='f'>برای جزئیات کلیک کنید</div>")

    focus = stop_by_n.get(focus_n) if focus_n else None
    for s in pts:
        c = STOP_COLORS[s["ck"]][0]
        folium.Marker(
            [float(s["lat"]), float(s["lng"])],
            icon=folium.DivIcon(html=f"<div class='pv-pin' style='background:{c};--halo:{_hex_rgba(c, .18)}'>{fa(s['n'])}</div>",
                                icon_size=(28, 28), icon_anchor=(14, 14)),
            tooltip=folium.Tooltip(tip_html(s), class_name="pv-tip", sticky=False),
        ).add_to(cluster)

    if pts:
        lats = [float(s["lat"]) for s in pts]
        lngs = [float(s["lng"]) for s in pts]
        m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]], padding=(30, 30), max_zoom=16)

    # نقطهٔ انتخاب‌شده: لایهٔ جدا که بدون ساختن دوبارهٔ نقشه اضافه می‌شود؛
    # نقشه با زوم معقول (سطح خیابان، نه حداکثر) به سمت همان نقطه می‌رود
    fg = folium.FeatureGroup(name="focus")
    center, zoom = None, None
    if focus is not None and focus.get("lat") and focus.get("lng"):
        flat, flng = float(focus["lat"]), float(focus["lng"])
        try:
            acc_m = float(focus.get("acc")) if focus.get("acc") is not None and not pd.isna(focus.get("acc")) else None
        except (TypeError, ValueError):
            acc_m = None
        c = STOP_COLORS[focus["ck"]][0]
        if acc_m:
            folium.Circle([flat, flng], radius=acc_m, color=c, weight=1, opacity=.5, fill=True, fill_opacity=.08).add_to(fg)
        folium.Marker(
            [flat, flng], z_index_offset=10000,
            icon=folium.DivIcon(html=f"<div class='pv-pin pv-focus' style='background:{c};--halo:{_hex_rgba(c, .22)};"
                                     f"--halo2:{_hex_rgba(c, .45)}'>{fa(focus['n'])}</div>",
                                icon_size=(40, 40), icon_anchor=(20, 20)),
            tooltip=folium.Tooltip(f"{fa(focus['n'])}. {esc(focus['customer'])}", permanent=True,
                                   direction="top", offset=(0, -18), class_name="pv-flabel"),
        ).add_to(fg)
        center, zoom = [flat, flng], FOCUS_ZOOM
    elif pts:
        # نمای کلی: مرکز و زوم از روی محدودهٔ نقاط (صریح، تا نقشه همیشه همهٔ نقاط را نشان دهد)
        center, zoom = [(min(lats) + max(lats)) / 2, (min(lngs) + max(lngs)) / 2], overview_zoom(lats, lngs)

    stabilize(m)
    # کلید نقشه: فقط با تغییر داده‌ها (فیلتر/بازه/ثبت جدید) عوض می‌شود → نقشه از نو و اندازه‌شده روی نقاط؛
    # کلیک ردیف و باز/بسته شدن جزئیات کلید را عوض نمی‌کند → همان نقشه، فقط حرکت نرم به نقطه
    sig = zlib.crc32(repr([(s["n"], s.get("lat"), s.get("lng"), s["ck"]) for s in stops]).encode())
    mkey = f'{st.session_state.setdefault("map_key", 0)}_{sig}'
    out = st_folium(m, key=f"map_{mkey}", height=600, width="stretch", center=center, zoom=zoom,
                    feature_group_to_add=fg, returned_objects=["last_object_clicked_tooltip"])
    tip_txt = (out or {}).get("last_object_clicked_tooltip") or ""
    mt = re.match(r"\s*([0-9]+)\.", tip_txt.translate(_EN))
    if not stops:
        st.info("با این فیلترها موردی وجود ندارد. بازه، ویزیتور، مشتری یا کالا را تغییر دهید.")
    if mt and int(mt.group(1)) in stop_by_n:
        if st.session_state.get("map_click_seen") == (mkey, tip_txt):
            return None                         # همان کلیک قبلی (بعد از بستن پنجره)
        st.session_state["map_click_seen"] = (mkey, tip_txt)
        st.session_state["map_click_used"] = True
        n_ = int(mt.group(1))
        return (n_, stop_by_n[n_]["kind"], None)
    return None


# ══════════════════════════════════════════════
# خروجی‌ها (کش)
# ══════════════════════════════════════════════
def freeze(sections):
    return tuple((n, tuple(c), tuple(tuple(sorted(r.items())) for r in rows)) for n, c, rows in sections)


def thaw(fsections):
    return [(n, list(c), [dict(r) for r in rows]) for n, c, rows in fsections]


@st.cache_data(show_spinner=False, max_entries=20)
def cached_excel(meta, fsections):
    return report.to_excel(list(meta), thaw(fsections))


@st.cache_data(show_spinner=False, max_entries=20)
def cached_pdf(meta, fsections):
    return report.to_pdf(list(meta), thaw(fsections))


# ══════════════════════════════════════════════
# صفحهٔ ۲: گزارش‌ساز (فیلترهای ترکیبی)
# ══════════════════════════════════════════════
GROUPS = ["بدون گروه‌بندی", "ویزیتور", "مشتری", "روز", "کالا"]
TYPES = ["ویزیت", "سفارش", "دریافت"]
PTYPES = ["نقدی", "چک", "حواله"]


def page_report():
    ss = st.session_state
    bar.markdown(app_bar("📊 گزارش‌ساز", "فیلترها را ترکیب کنید؛ نتیجه همان لحظه به‌روز می‌شود",
                         [f"👤 {esc(USER['name'])}"]), unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.caption("از تاریخ")
            j0 = jalali_picker("rfrom", jdatetime.date(today_j.year, today_j.month, 1))
        with c2:
            st.caption("تا تاریخ")
            j1 = jalali_picker("rto", today_j)
        if j1 < j0:
            j0, j1 = j1, j0
        g0, g1 = j0.togregorian(), j1.togregorian()
        try:
            visits, orders, pays, items = load_data(g0.isoformat(), g1.isoformat(), ALLOWED)
        except Exception as e:
            st.error(f"❌ خطای دیتابیس: {e}")
            return
        vnames = {int(r["id"]): r["full_name"] for _, r in vis_df.iterrows()}
        cnames = {}
        for df in (visits, orders, pays):
            for r in df.itertuples():
                cnames.setdefault(str(r.customer_code), r.customer)
        pnames = dict(zip(items["code"].astype(str), items["name"])) if len(items) else {}

        r1 = st.columns(3)
        f_v = r1[0].multiselect("ویزیتورها", list(vnames), format_func=lambda v: vnames[v], placeholder="همه", key="r_v")
        f_c = r1[1].multiselect("مشتری‌ها", sorted(cnames, key=lambda c: cnames[c]),
                                format_func=lambda c: f"{cnames[c]} ({fa(c)})", placeholder="همه", key="r_c")
        f_p = r1[2].multiselect("کالاها", sorted(pnames, key=lambda c: pnames[c]),
                                format_func=lambda c: f"{pnames[c]} ({fa(c)})", placeholder="همه", key="r_p",
                                help="با انتخاب کالا فقط سفارش‌هایی که آن کالا را دارند می‌آیند.")
        r2 = st.columns([1.3, 1.3, 1, 1, 1.2])
        f_t = r2[0].multiselect("نوع ثبت", TYPES, default=TYPES, key="r_t")
        f_pt = r2[1].multiselect("نوع دریافت", PTYPES, default=PTYPES, key="r_pt")
        f_min = r2[2].number_input("حداقل مبلغ (ریال)", min_value=0, value=0, step=100000, key="r_min",
                                   disabled=not SHOW_MONEY)
        f_max = r2[3].number_input("حداکثر مبلغ (ریال)", min_value=0, value=0, step=100000, key="r_max",
                                   help="صفر = بدون سقف", disabled=not SHOW_MONEY)
        f_g = r2[4].selectbox("گروه‌بندی", GROUPS, key="r_g")

    items_by_order = {}
    for it in items.to_dict("records"):
        items_by_order.setdefault(int(it["order_id"]), []).append(it)

    def keep(r, kind, amount=None):
        if f_v and int(r["visitor_id"]) not in f_v:
            return False
        if f_c and str(r["customer_code"]) not in f_c:
            return False
        if amount is not None and SHOW_MONEY:
            if f_min and amount < f_min:
                return False
            if f_max and amount > f_max:
                return False
        return True

    recs = []
    if "ویزیت" in f_t and not f_p:
        for r in visits.to_dict("records"):
            if keep(r, "visit"):
                recs.append({"نوع": "ویزیت", "تاریخ": jdate(r["d"]), "ساعت": str(r["t"])[:5], "ویزیتور": r["visitor"],
                             "مشتری": r["customer"], "جزئیات": "", "مبلغ (ریال)": None, "توضیحات": txt(r["descr"]),
                             "_d": str(r["d"]), "_v": r["visitor"], "_c": r["customer"]})
    if "سفارش" in f_t:
        for r in orders.to_dict("records"):
            its = items_by_order.get(int(r["id"]), [])
            if f_p and not any(str(i["code"]) in f_p for i in its):
                continue
            if keep(r, "order", float(r["total"] or 0)):
                recs.append({"نوع": "سفارش", "تاریخ": jdate(r["d"]), "ساعت": str(r["t"])[:5], "ویزیتور": r["visitor"],
                             "مشتری": r["customer"], "جزئیات": "، ".join(f"{i['name']} × {i['qty']:g}" for i in its),
                             "مبلغ (ریال)": float(r["total"] or 0), "توضیحات": txt(r["descr"]),
                             "_d": str(r["d"]), "_v": r["visitor"], "_c": r["customer"], "_items": its})
    if "دریافت" in f_t and not f_p:
        for r in pays.to_dict("records"):
            if r["ptype"] not in f_pt:
                continue
            if keep(r, "pay", float(r["amount"] or 0)):
                det = (f"چک {r['check_number']} · سررسید {jdate(r['check_due'])}" if r["ptype"] == "چک"
                       else f"پیگیری {r['tr_tracking'] or r['tracking']}" if r["ptype"] == "حواله" else "نقدی")
                recs.append({"نوع": f"دریافت {r['ptype']}", "تاریخ": jdate(r["d"]), "ساعت": str(r["t"])[:5],
                             "ویزیتور": r["visitor"], "مشتری": r["customer"], "جزئیات": det,
                             "مبلغ (ریال)": float(r["amount"] or 0), "توضیحات": txt(r["descr"]),
                             "_d": str(r["d"]), "_v": r["visitor"], "_c": r["customer"]})
    recs.sort(key=lambda x: (x["_d"], x["ساعت"]))

    n_v = sum(1 for r in recs if r["نوع"] == "ویزیت")
    n_o = [r for r in recs if r["نوع"] == "سفارش"]
    n_p = [r for r in recs if r["نوع"].startswith("دریافت")]
    s_o, s_p = sum(r["مبلغ (ریال)"] for r in n_o), sum(r["مبلغ (ریال)"] for r in n_p)
    amt = lambda v: f" · {money(v)}" if SHOW_MONEY else ""
    st.markdown("<div class='legend' style='margin-top:6px'>"
                f"<span><i style='background:{KIND_COLOR['visit']}'></i>{fa(n_v)} ویزیت</span>"
                f"<span><i style='background:{KIND_COLOR['order']}'></i>{fa(len(n_o))} سفارش{amt(s_o)}</span>"
                f"<span><i style='background:{KIND_COLOR['pay']}'></i>{fa(len(n_p))} دریافت{amt(s_p)}</span>"
                f"<span>{fa(len(recs))} ردیف · {range_text(j0, j1, g0, g1)}</span></div>", unsafe_allow_html=True)

    # ── گروه‌بندی ──
    grp_rows, grp_cols = [], []
    if f_g == "کالا":
        agg = {}
        for r in n_o:
            for i in r["_items"]:
                if f_p and str(i["code"]) not in f_p:
                    continue
                a = agg.setdefault(str(i["code"]), {"کالا": i["name"], "کد": str(i["code"]), "تعداد": 0.0,
                                                   "سفارش‌ها": 0, "مبلغ (ریال)": 0.0})
                a["تعداد"] += float(i["qty"] or 0)
                a["سفارش‌ها"] += 1
                a["مبلغ (ریال)"] += float(i["qty"] or 0) * float(i["price"] or 0)
        grp_rows = sorted(agg.values(), key=lambda x: -x["مبلغ (ریال)"])
        grp_cols = ["کالا", "کد", "تعداد", "سفارش‌ها"] + (["مبلغ (ریال)"] if SHOW_MONEY else [])
    elif f_g != "بدون گروه‌بندی":
        kf = {"ویزیتور": "_v", "مشتری": "_c", "روز": "تاریخ"}[f_g]
        agg = {}
        for r in recs:
            a = agg.setdefault(r[kf], {f_g: r[kf], "ویزیت": 0, "سفارش": 0, "مبلغ سفارش (ریال)": 0.0,
                                       "دریافت": 0, "مبلغ دریافت (ریال)": 0.0})
            if r["نوع"] == "ویزیت":
                a["ویزیت"] += 1
            elif r["نوع"] == "سفارش":
                a["سفارش"] += 1; a["مبلغ سفارش (ریال)"] += r["مبلغ (ریال)"]
            else:
                a["دریافت"] += 1; a["مبلغ دریافت (ریال)"] += r["مبلغ (ریال)"]
        grp_rows = sorted(agg.values(), key=lambda x: str(x[f_g]))
        grp_cols = [f_g, "ویزیت", "سفارش"] + (["مبلغ سفارش (ریال)"] if SHOW_MONEY else []) + ["دریافت"] + \
                   (["مبلغ دریافت (ریال)"] if SHOW_MONEY else [])

    detail_cols = ["تاریخ", "ساعت", "نوع", "مشتری", "ویزیتور", "جزئیات"] + (["مبلغ (ریال)"] if SHOW_MONEY else []) + ["توضیحات"]

    def show_df(rows, cols, height):
        df = pd.DataFrame([{c: report.fmt(r.get(c), c) if r.get(c) not in ("",) else "—" for c in cols}
                           for r in rows], columns=cols)
        st.dataframe(df[cols[::-1]], hide_index=True, width="stretch", height=height)

    if grp_rows:
        st.markdown(f"<div class='sec'>خلاصه بر اساس {f_g}</div>", unsafe_allow_html=True)
        show_df(grp_rows, grp_cols, min(420, 38 + 35 * len(grp_rows)))
    st.markdown("<div class='sec'>ریز ثبت‌ها</div>", unsafe_allow_html=True)
    if recs:
        show_df(recs, detail_cols, 460)
    else:
        st.info("با این فیلترها ثبتی پیدا نشد.")

    if CAN_EXPORT and recs:
        meta = [("بازه", range_text(j0, j1, g0, g1))]
        for lbl, vals, names in (("ویزیتور", f_v, vnames), ("مشتری", f_c, cnames), ("کالا", f_p, pnames)):
            if vals:
                meta.append((lbl, "، ".join(str(names[v]) for v in vals)))
        meta.append(("نوع ثبت", "، ".join(f_t)))
        meta.append(("جمع", f"{fa(n_v)} ویزیت · {fa(len(n_o))} سفارش{amt(s_o)} · {fa(len(n_p))} دریافت{amt(s_p)}"))
        clean = lambda rows, cols: [{c: r.get(c) for c in cols} for r in rows]
        sections = ([(f"خلاصه بر اساس {f_g}", grp_cols, clean(grp_rows, grp_cols))] if grp_rows else []) + \
                   [("ریز ثبت‌ها", detail_cols, clean(recs, detail_cols))]
        fz, mt = freeze(sections), tuple(meta)
        fname = f"PeechaVisit_Report_{j0.strftime('%Y%m%d')}_{j1.strftime('%Y%m%d')}"
        e1, e2, e3, _ = st.columns([1, 1, 1, 3])
        e1.download_button("📥 Excel", data=cached_excel(mt, fz), file_name=f"{fname}.xlsx",
                           width="stretch", on_click="ignore")
        try:
            e2.download_button("📄 PDF", data=cached_pdf(mt, fz), file_name=f"{fname}.pdf", mime="application/pdf",
                               width="stretch", on_click="ignore")
        except Exception as e:
            e2.caption(f"PDF ساخته نشد: {e}")
        if e3.button("🖨️ چاپ", width="stretch"):
            ss["dlg_open"] = True

            @st.dialog("پیش‌نمایش چاپ", width="large", on_dismiss=_closed)
            def _print():
                components.html(report.to_html(meta, sections, font_css()), height=640, scrolling=True)
            _print()


# ══════════════════════════════════════════════
# صفحهٔ ۳: گزارش کالا — هر ویزیتور چه کالاهایی و چه مقدار سفارش گرفته
# ══════════════════════════════════════════════
PROD_VIEWS = ["ویزیتور × کالا", "جمع هر کالا", "ویزیتور", "ریز اقلام"]


def page_products():
    bar.markdown(app_bar("📦 گزارش کالا", "کالاهای سفارش‌گرفته‌شده به تفکیک ویزیتور، کالا و ریز اقلام",
                         [f"👤 {esc(USER['name'])}"]), unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.caption("از تاریخ")
            j0 = jalali_picker("pfrom", jdatetime.date(today_j.year, today_j.month, 1))
        with c2:
            st.caption("تا تاریخ")
            j1 = jalali_picker("pto", today_j)
        if j1 < j0:
            j0, j1 = j1, j0
        g0, g1 = j0.togregorian(), j1.togregorian()
        try:
            _, orders, _, items = load_data(g0.isoformat(), g1.isoformat(), ALLOWED)
        except Exception as e:
            st.error(f"❌ خطای دیتابیس: {e}")
            return
        vnames = {int(r["id"]): r["full_name"] for _, r in vis_df.iterrows()}
        pnames = dict(zip(items["code"].astype(str), items["name"])) if len(items) else {}
        cnames = {str(r.customer_code): r.customer for r in orders.itertuples()}
        r1 = st.columns([1.2, 1.4, 1.2, 1])
        f_v = r1[0].multiselect("ویزیتورها", list(vnames), format_func=lambda v: vnames[v], placeholder="همه", key="p_v")
        f_p = r1[1].multiselect("کالاها", sorted(pnames, key=lambda c: pnames[c]),
                                format_func=lambda c: f"{pnames[c]} ({fa(c)})", placeholder="همه", key="p_p")
        f_c = r1[2].multiselect("مشتری‌ها", sorted(cnames, key=lambda c: cnames[c]),
                                format_func=lambda c: f"{cnames[c]} ({fa(c)})", placeholder="همه", key="p_c")
        view = r1[3].selectbox("نمایش", PROD_VIEWS, key="p_view")

    om = {int(r["id"]): r for r in orders.to_dict("records")}
    lines = []
    for it in items.to_dict("records"):
        o = om.get(int(it["order_id"]))
        if o is None or (f_v and int(o["visitor_id"]) not in f_v) or (f_c and str(o["customer_code"]) not in f_c) \
                or (f_p and str(it["code"]) not in f_p):
            continue
        q, pr = float(it["qty"] or 0), float(it["price"] or 0)
        lines.append({"تاریخ": jdate(o["d"]), "ساعت": hhmm(o["t"]), "سفارش": fa(o["id"]), "ویزیتور": o["visitor"],
                      "مشتری": o["customer"], "کد کالا": str(it["code"]), "کالا": it["name"], "تعداد": q,
                      "فی (ریال)": pr, "مبلغ (ریال)": q * pr, "_d": str(o["d"]), "_vid": int(o["visitor_id"])})
    lines.sort(key=lambda x: (x["_d"], x["ساعت"], x["سفارش"]))

    tot_q = sum(l["تعداد"] for l in lines)
    tot_a = sum(l["مبلغ (ریال)"] for l in lines)
    n_ord = len({l["سفارش"] for l in lines})
    n_prod = len({l["کد کالا"] for l in lines})
    amt = f" · {money(tot_a)}" if SHOW_MONEY else ""
    st.markdown("<div class='legend' style='margin-top:6px'>"
                f"<span><i style='background:{KIND_COLOR['order']}'></i>{fa(n_ord)} سفارش{amt}</span>"
                f"<span>{fa(n_prod)} کالای مختلف</span><span>جمع تعداد: <b>{fa(format(tot_q, 'g'))}</b></span>"
                f"<span>{fa(len(lines))} ردیف قلم · {range_text(j0, j1, g0, g1)}</span></div>", unsafe_allow_html=True)
    if not lines:
        st.info("در این بازه و با این فیلترها سفارشی ثبت نشده است.")
        return

    m_cols = ["مبلغ (ریال)"] if SHOW_MONEY else []

    def agg(keyf, first):
        out = {}
        for l in lines:
            k = keyf(l)
            a = out.setdefault(k, {**first(l), "تعداد": 0.0, "سفارش‌ها": set(), "مبلغ (ریال)": 0.0})
            a["تعداد"] += l["تعداد"]; a["سفارش‌ها"].add(l["سفارش"]); a["مبلغ (ریال)"] += l["مبلغ (ریال)"]
        for a in out.values():
            a["سفارش‌ها"] = len(a["سفارش‌ها"])
        return list(out.values())

    by_vp = agg(lambda l: (l["_vid"], l["کد کالا"]),
                lambda l: {"ویزیتور": l["ویزیتور"], "کالا": l["کالا"], "کد کالا": l["کد کالا"]})
    by_vp.sort(key=lambda a: (a["ویزیتور"], -a["تعداد"]))
    by_p = agg(lambda l: l["کد کالا"], lambda l: {"کالا": l["کالا"], "کد کالا": l["کد کالا"]})
    by_p.sort(key=lambda a: -a["تعداد"])
    by_v = agg(lambda l: l["_vid"], lambda l: {"ویزیتور": l["ویزیتور"]})
    for a in by_v:
        a["کالای مختلف"] = len({l["کد کالا"] for l in lines if l["ویزیتور"] == a["ویزیتور"]})
    by_v.sort(key=lambda a: -a["مبلغ (ریال)"])

    # ردیف جمع کل برای هر جدول خلاصه
    def with_total(rows, label_col):
        total = {label_col: "جمع کل", "تعداد": sum(r["تعداد"] for r in rows),
                 "مبلغ (ریال)": sum(r["مبلغ (ریال)"] for r in rows), "سفارش‌ها": n_ord}
        return rows + [total]

    sections = {
        "ویزیتور × کالا": (["ویزیتور", "کالا", "کد کالا", "تعداد", "سفارش‌ها"] + m_cols, with_total(by_vp, "ویزیتور")),
        "جمع هر کالا": (["کالا", "کد کالا", "تعداد", "سفارش‌ها"] + m_cols, with_total(by_p, "کالا")),
        "ویزیتور": (["ویزیتور", "کالای مختلف", "تعداد", "سفارش‌ها"] + m_cols, with_total(by_v, "ویزیتور")),
        "ریز اقلام": (["تاریخ", "ساعت", "سفارش", "ویزیتور", "مشتری", "کالا", "کد کالا", "تعداد"]
                      + (["فی (ریال)", "مبلغ (ریال)"] if SHOW_MONEY else []), lines),
    }
    cols, rows = sections[view]

    def show(rows, cols, height):
        df = pd.DataFrame([{c: (report.fmt(r.get(c), c) if r.get(c) not in ("", None) else "—") for c in cols}
                           for r in rows], columns=cols)
        st.dataframe(df[cols[::-1]], hide_index=True, width="stretch", height=height)

    st.markdown(f"<div class='sec'>{view}</div>", unsafe_allow_html=True)
    show(rows, cols, min(520, 38 + 35 * len(rows)))
    if view != "ریز اقلام":
        with st.expander(f"ریز اقلام ({fa(len(lines))} ردیف)"):
            show(lines, sections["ریز اقلام"][0], min(460, 38 + 35 * len(lines)))

    if CAN_EXPORT:
        meta = [("گزارش", "کالاهای سفارش‌گرفته‌شده"), ("بازه", range_text(j0, j1, g0, g1))]
        for lbl, vals, names in (("ویزیتور", f_v, vnames), ("کالا", f_p, pnames), ("مشتری", f_c, cnames)):
            if vals:
                meta.append((lbl, "، ".join(str(names[v]) for v in vals)))
        meta.append(("جمع", f"{fa(n_ord)} سفارش · {fa(n_prod)} کالا · تعداد {fa(format(tot_q, 'g'))}{amt}"))
        clean = lambda rs, cs: [{c: r.get(c) for c in cs} for r in rs]
        secs = [(name, sections[name][0], clean(sections[name][1], sections[name][0])) for name in PROD_VIEWS]
        fz, mt = freeze(secs), tuple(meta)
        fname = f"PeechaVisit_Products_{j0.strftime('%Y%m%d')}_{j1.strftime('%Y%m%d')}"
        e1, e2, e3, _ = st.columns([1, 1, 1, 3])
        e1.download_button("📥 Excel", data=cached_excel(mt, fz), file_name=f"{fname}.xlsx", width="stretch",
                           on_click="ignore", key="p_xl")
        try:
            e2.download_button("📄 PDF", data=cached_pdf(mt, fz), file_name=f"{fname}.pdf", mime="application/pdf",
                               width="stretch", on_click="ignore", key="p_pdf")
        except Exception as e:
            e2.caption(f"PDF ساخته نشد: {e}")
        if e3.button("🖨️ چاپ", width="stretch", key="p_print"):
            st.session_state["dlg_open"] = True

            @st.dialog("پیش‌نمایش چاپ", width="large", on_dismiss=_closed)
            def _print():
                components.html(report.to_html(meta, secs, font_css()), height=640, scrolling=True)
            _print()



# ══════════════════════════════════════════════
# صفحهٔ ۴: پیام‌ها
# ══════════════════════════════════════════════
def page_messages():
    ss = st.session_state
    me = int(USER["id"])
    users = read_sql("SELECT id, full_name, ISNULL(role,'visitor') AS role FROM visitors WHERE is_active=1 AND id<>? "
                     "ORDER BY CASE WHEN role='admin' THEN 0 ELSE 1 END, full_name", (me,))
    unread = read_sql("SELECT sender_id, COUNT(*) AS n FROM messages WHERE recipient_id=? AND read_at IS NULL "
                      "GROUP BY sender_id", (me,))
    un = dict(zip(unread["sender_id"].astype(int), unread["n"].astype(int))) if len(unread) else {}
    bar.markdown(app_bar("💬 پیام‌ها", "گفتگو با ویزیتورها و همکاران",
                         [f"<b>{fa(sum(un.values()))}</b> پیام خوانده‌نشده", f"👤 {esc(USER['name'])}"]),
                 unsafe_allow_html=True)
    names = {int(r["id"]): r["full_name"] + (" (مدیر)" if r["role"] == "admin" else "") for _, r in users.iterrows()}
    opts = (["all"] if IS_ADMIN else []) + list(names)
    if not opts:
        st.info("کاربر دیگری برای گفتگو وجود ندارد.")
        return
    c_list, c_chat = st.columns([1, 2.4], gap="medium")
    with c_list:
        who = st.radio("گفتگو با", opts, key="chat_with", label_visibility="collapsed",
                       format_func=lambda u: "📣 پیام به همه" if u == "all"
                       else f"{names[u]}{'  🔵 ' + fa(un[u]) if un.get(u) else ''}")
    with c_chat:
        if who == "all":
            st.markdown("<div class='chat'><div class='muted' style='margin:auto'>این پیام برای همهٔ کاربران فعال فرستاده می‌شود.</div></div>",
                        unsafe_allow_html=True)
        else:
            if un.get(who):
                run_sql("UPDATE messages SET read_at=GETDATE() WHERE recipient_id=? AND sender_id=? AND read_at IS NULL",
                        (me, who))
            conv = read_sql("""SELECT TOP 200 id, sender_id, body, CONVERT(VARCHAR(16), created_at, 120) AS at
                               FROM messages WHERE (sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?)
                               ORDER BY id DESC""", (me, who, who, me)).iloc[::-1]
            bubbles = "".join(
                f"<div class='bub {'me' if int(r.sender_id) == me else 'them'}'>"
                f"<b class='who'>{'شما' if int(r.sender_id) == me else esc(names.get(int(r.sender_id), ''))}</b>{esc(r.body)}"
                f"<small>{jdate(r.at[:10])} {fa(r.at[11:16])}</small></div>" for r in conv.itertuples()) \
                or "<div class='muted' style='margin:auto'>هنوز پیامی رد و بدل نشده است.</div>"
            st.markdown(f"<div class='chat' id='chatbox'>{bubbles}</div>", unsafe_allow_html=True)
            components.html("<script>const c=window.parent.document.getElementById('chatbox');if(c)c.scrollTop=c.scrollHeight;</script>",
                            height=0)
        with st.form("send_msg", clear_on_submit=True, border=False):
            fc1, fc2 = st.columns([5, 1])
            body = fc1.text_input("پیام", placeholder="پیام خود را بنویسید...", label_visibility="collapsed")
            sent = fc2.form_submit_button("ارسال", type="primary", width="stretch")
        if sent and body.strip():
            targets = list(names) if who == "all" else [who]
            for t in targets:
                run_sql("INSERT INTO messages (sender_id, recipient_id, body) VALUES (?,?,?)", (me, t, body.strip()[:2000]))
            audit.log_event("dashboard", "message", me, USER["username"], detail=f"به {'همه' if who == 'all' else who}")
            if who == "all":
                st.toast(f"پیام برای {fa(len(targets))} نفر ارسال شد.")
            st.rerun()


# ══════════════════════════════════════════════
# صفحهٔ ۵: لاگ ورود و فعالیت (فقط مدیر)
# ══════════════════════════════════════════════
def page_logs():
    bar.markdown(app_bar("📜 لاگ ورود و فعالیت", "ورود به اپ، داشبورد و پنل مدیریت؛ ثبت‌ها و پیام‌ها با دستگاه",
                         [f"👤 {esc(USER['name'])}"]), unsafe_allow_html=True)
    c = st.columns([1.2, 1.2, 1.5, 1.5, 1.5])
    with c[0]:
        days = st.selectbox("بازه", [1, 7, 30, 90], index=1, format_func=lambda d: f"{fa(d)} روز اخیر", key="lg_days")
    src = c[1].multiselect("منبع", list(audit.SOURCE_LABELS), format_func=lambda s: audit.SOURCE_LABELS[s],
                           placeholder="همه", key="lg_src")
    evt = c[2].multiselect("رویداد", list(audit.EVENT_LABELS), format_func=lambda e: audit.EVENT_LABELS[e],
                           placeholder="همه", key="lg_evt")
    usr = c[3].text_input("نام کاربری", placeholder="همه", key="lg_user")
    dev = c[4].text_input("دستگاه (برند/مدل)", placeholder="همه", key="lg_dev")
    sql = """SELECT TOP 2000 CONVERT(VARCHAR(19), created_at, 120) AS at, ISNULL(username,'') AS username, source, event,
                    ISNULL(device,'') AS device, ISNULL(ip,'') AS ip, ISNULL(detail,'') AS detail
             FROM access_log WHERE created_at >= DATEADD(day, ?, GETDATE())"""
    prm = [-int(days)]
    if src:
        sql += f" AND source IN ({','.join('?' * len(src))})"; prm += src
    if evt:
        sql += f" AND event IN ({','.join('?' * len(evt))})"; prm += evt
    if usr.strip():
        sql += " AND username LIKE ?"; prm.append(f"%{usr.strip()}%")
    if dev.strip():
        sql += " AND device LIKE ?"; prm.append(f"%{dev.strip()}%")
    df = read_sql(sql + " ORDER BY id DESC", prm)
    if df.empty:
        st.info("رویدادی پیدا نشد.")
        return
    ok_n = int((df["event"] == "login").sum()); bad_n = int((df["event"] == "login_failed").sum())
    st.markdown(f"<div class='legend'><span>{fa(len(df))} رویداد</span><span>✅ {fa(ok_n)} ورود</span>"
                f"<span>⛔ {fa(bad_n)} ورود ناموفق</span><span>📱 {fa(df['device'].replace('', pd.NA).nunique())} دستگاه</span></div>",
                unsafe_allow_html=True)
    out = pd.DataFrame({
        "زمان": [f"{jdate(a[:10])} {fa(a[11:16])}" for a in df["at"]],
        "کاربر": df["username"],
        "منبع": [audit.SOURCE_LABELS.get(s, s) for s in df["source"]],
        "رویداد": [audit.EVENT_LABELS.get(e, e) for e in df["event"]],
        "دستگاه": df["device"], "IP": df["ip"], "جزئیات": df["detail"],
    })
    st.dataframe(out[out.columns[::-1]], hide_index=True, width="stretch", height=560)


# ══════════════════════════════════════════════
# اعلان ثبت‌ها و پیام‌های جدید + بروزرسانی فقط هنگام تغییر داده
# ══════════════════════════════════════════════
NOTE_KIND = {"visits": ("📍", "ویزیت جدید", "visit"), "orders": ("📦", "سفارش جدید", "order"),
             "payments": ("💰", "دریافت جدید", "pay"), "messages": ("💬", "پیام جدید", "visit")}


def _new_rows(table, last_id):
    f, p = _vis_filter("x", ALLOWED)
    if table == "messages":
        return read_sql("""SELECT TOP 6 x.id, ISNULL(u.full_name,N'') AS visitor, x.body AS customer,
                                  CONVERT(VARCHAR(5), x.created_at, 108) AS t, '' AS img, NULL AS amount, '' AS ptype,
                                  CONVERT(VARCHAR(10), x.created_at, 120) AS d
                           FROM messages x LEFT JOIN visitors u ON u.id = x.sender_id
                           WHERE x.id > ? AND x.recipient_id = ? ORDER BY x.id DESC""", (last_id, int(USER["id"])))
    col = {"visits": ("visit_time", "visit_date", "ISNULL(x.selfie_path,'')", "NULL", "''"),
           "orders": ("order_time", "order_date", "''", "x.total_amount", "''"),
           "payments": ("payment_time", "payment_date",
                        "ISNULL(x.check_image_path, ISNULL(x.transfer_image_path,''))", "x.amount", "x.payment_type")}[table]
    return read_sql(f"""SELECT TOP 6 x.id, ISNULL(u.full_name,N'') AS visitor,
                               COALESCE(CAST(c.C_Name AS NVARCHAR(200)), nc.name + N' (جدید)', x.customer_code) AS customer,
                               CONVERT(VARCHAR(5), x.{col[0]}, 108) AS t, {col[2]} AS img, {col[3]} AS amount,
                               {col[4]} AS ptype, CONVERT(VARCHAR(10), x.{col[1]}, 120) AS d
                        FROM {table} x
                        LEFT JOIN visitors u ON u.id = x.visitor_id
                        LEFT JOIN {SALES}.customer c ON c.C_Code = x.customer_code
                        LEFT JOIN new_customers nc ON nc.code = x.customer_code
                        WHERE x.id > ? {f} ORDER BY x.id DESC""", (last_id,) + p)


def _max_ids():
    f, p = _vis_filter("x", ALLOWED)
    out = {}
    for t in ("visits", "orders", "payments"):
        out[t] = int(read_sql(f"SELECT ISNULL(MAX(x.id),0) AS m FROM {t} x WHERE 1=1 {f}", p)["m"].iloc[0])
    out["messages"] = int(read_sql("SELECT ISNULL(MAX(id),0) AS m FROM messages WHERE recipient_id=?",
                                   (int(USER["id"]),))["m"].iloc[0])
    return out


def _go_messages(sender_name):
    st.session_state["page"] = P_MSGS
    st.session_state["_go_rerun"] = True
    st.session_state.notes = [n for n in st.session_state.get("notes", []) if n["t"] != "messages"]


@st.fragment(run_every=15)
def live():
    ss = st.session_state
    try:
        cur = _max_ids()
    except Exception:
        return
    if "last_ids" not in ss:
        ss.last_ids, ss.notes = cur, []
    data_changed = False
    for t, mx in cur.items():
        if mx > ss.last_ids.get(t, 0):
            if ss.get("notify_on", True):
                for r in _new_rows(t, ss.last_ids[t]).itertuples():
                    ss.notes.append({"t": t, "id": int(r.id), "at": time.time(), "visitor": r.visitor,
                                     "customer": r.customer, "time": r.t, "img": r.img, "amount": r.amount,
                                     "ptype": r.ptype, "d": r.d})
            ss.last_ids[t] = mx
            data_changed = data_changed or t != "messages"
    ss.notes = [n for n in ss.notes if time.time() - n["at"] < 25][-4:]

    box = st.container(key="pvnotes")
    for n in ss.notes:
        icon, title, kind = NOTE_KIND[n["t"]]
        color, soft = KIND_COLOR[kind], KIND_SOFT[kind]
        if n["t"] == "payments" and n["ptype"]:
            title = f"دریافت {n['ptype']}"
        src = img_src(n["img"], (160, 160)) if n["img"] else None
        pic = f"<img src='{src}'>" if src else f"<div class='i' style='background:{soft}'>{icon}</div>"
        amount = f" · {money(n['amount'])}" if n["amount"] is not None and not pd.isna(n["amount"]) and SHOW_MONEY else ""
        with box.container(key=f"note_{n['t']}_{n['id']}"):
            st.markdown(
                f"<div class='pv-note' style='border-right:4px solid {color};padding-right:8px'>{pic}<div>"
                f"<div class='t' style='color:{color}'>{title}</div>"
                f"<div class='n'>{esc(n['customer'] if n['t'] != 'messages' else n['visitor'])}</div>"
                f"<div class='m'>{esc(n['visitor'] if n['t'] != 'messages' else n['customer'][:60])}"
                f" · ساعت {hhmm(n['time'])}{amount}</div></div></div>", unsafe_allow_html=True)
            if n["t"] == "messages":
                st.button("پاسخ ←", key=f"nb_{n['t']}_{n['id']}", on_click=_go_messages, args=(n["visitor"],))
            else:
                st.button("نمایش روی نقشه و جزئیات ←", key=f"nb_{n['t']}_{n['id']}",
                          on_click=open_note, args=(n["t"], n["id"], n["d"]))

    if ss.get("pending_open") or ss.get("_go_rerun"):
        ss.pop("_go_rerun", None)
        st.rerun(scope="app")
    if data_changed and REFRESH.get(ss.get("auto_refresh"), True) and not ss.get("dlg_open"):
        load_data.clear()
        st.rerun(scope="app")


# ══════════════════════════════════════════════
# اجرا
# ══════════════════════════════════════════════
if page == P_MAP:
    page_map()
elif page == P_REPORT:
    page_report()
elif page == P_PRODUCTS:
    page_products()
elif page == P_MSGS:
    page_messages()
elif page == P_LOGS and IS_ADMIN:
    page_logs()

live()
