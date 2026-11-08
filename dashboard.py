# dashboard.py - پیچا ویزیت | داشبورد v7
# ════════════════════════════════════════════════
# اجرا:  streamlit run dashboard.py --server.port 8501
# هر «توقف» روی نقشه = یک ویزیت (+ سفارش و دریافتی که همان لحظه ثبت شده)
# ════════════════════════════════════════════════
import base64
import io
import os
import re
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

from config import APP
from db import get_conn, SALES_DB
from panel_auth import require_admin, logout
from ui_font import font_css
import report

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.realpath(os.path.join(BASE_DIR, "static"))
C1         = APP["PRIMARY_COLOR"]
KIND_COLOR = {"visit": "#3b5bdb", "order": "#7c3aed", "pay": "#12805c"}
VISITOR_COLORS = ["#3b5bdb", "#e8590c", "#2b8a3e", "#c2255c", "#1098ad", "#7048e8", "#f08c00", "#495057"]
MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
          "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
SALES = f"[{SALES_DB}].dbo" if re.fullmatch(r"[A-Za-z0-9_]+", SALES_DB) else "dbo"

st.markdown(font_css(), unsafe_allow_html=True)
st.markdown(f"""
<style>
.stApp {{ background:#f3f5fb; direction:rtl; }}
.block-container {{ padding:3.2rem 22px 30px !important; max-width:100% !important; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {{ display:none !important; }}
p, label, .stMarkdown, .stCaption, .stAlert {{ direction:rtl; text-align:right; }}
.pv-title {{ font-size:19px; font-weight:800; color:{C1}; line-height:1.3; padding-top:4px; }}
.kpis {{ display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 12px; }}
.kpi {{ background:#fff; border:1px solid #e3e7ef; border-radius:10px; padding:6px 12px;
        font-size:13px; color:#495057; white-space:nowrap; }}
.kpi b {{ font-size:15px; color:#17202e; margin-left:4px; }}
.kpi i {{ font-style:normal; color:#6b7686; }}
.kpi.f {{ background:#fff6e0; border-color:#ffe3a3; }}
.legend {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:6px; font-size:12px; }}
.legend span {{ display:inline-flex; align-items:center; gap:5px; background:#fff; border:1px solid #e3e7ef;
                border-radius:20px; padding:2px 10px; }}
.legend i {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
/* روز/ماه/سال در موبایل هم کنار هم بمانند */
[class*="st-key-jp_"] [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; gap:6px !important; }}
[class*="st-key-jp_"] [data-testid="stColumn"] {{ min-width:0 !important; width:auto !important; flex:1 1 0 !important; }}
/* وقتی پنجره‌ای باز است، منوی بالا رویش نماند */
body:has([data-testid="stDialog"]) [data-testid="stPopoverBody"] {{ display:none !important; }}
/* پنجرهٔ جزئیات */
.dlg-kind {{ display:inline-block; border-radius:20px; padding:2px 12px; font-size:12px; font-weight:700; }}
.dlg-head {{ font-size:20px; font-weight:800; color:#17202e; margin-top:6px; }}
.dlg-amount {{ font-size:22px; font-weight:800; margin:2px 0; }}
.dlg-meta {{ font-size:13px; color:#6b7686; margin:2px 0 10px; }}
.sec {{ font-size:15px; font-weight:800; margin:6px 0 8px; }}
.box {{ background:#fff; border:1px solid #e3e7ef; border-radius:12px; padding:12px 14px; margin-bottom:10px; }}
.muted {{ color:#868e96; font-size:13px; }}
.kv {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:8px; }}
.kv div {{ background:#f6f7fa; border-radius:8px; padding:6px 10px; }}
.kv small {{ display:block; font-size:11px; color:#6b7686; }}
.kv b {{ font-size:14px; color:#17202e; font-weight:600; }}
.itm {{ width:100%; border-collapse:collapse; font-size:13px; }}
.itm th {{ text-align:right; color:#6b7686; font-weight:600; border-bottom:1px solid #e3e7ef; padding:5px 4px; }}
.itm td {{ border-bottom:1px solid #f1f3f5; padding:6px 4px; }}
.itm tfoot td {{ font-weight:800; border-bottom:0; }}
/* گالری بند انگشتی + بزرگ‌نمایی با کلیک */
.gal {{ display:flex; flex-wrap:wrap; gap:10px; margin:4px 0 12px; }}
.gal figure {{ margin:0; width:132px; }}
.gal .th img {{ width:132px; height:96px; object-fit:cover; border-radius:10px; border:1px solid #dfe3ea;
               cursor:zoom-in; display:block; }}
.gal figcaption {{ font-size:12px; color:#6b7686; text-align:center; margin-top:3px; }}
.gal .lbt {{ display:none; }}
.gal .lb {{ display:none; position:fixed; inset:0; z-index:100000; background:rgba(10,12,20,.88);
           align-items:center; justify-content:center; flex-direction:column; }}
.gal .lbt:checked ~ .lb {{ display:flex; }}
.gal .lb img {{ max-width:92vw; max-height:84vh; border-radius:8px; cursor:zoom-out; }}
.gal .lb span {{ color:#fff; margin-top:8px; font-size:14px; }}
.gal .nophoto {{ width:132px; height:96px; border-radius:10px; border:1px dashed #ced4da; color:#adb5bd;
                display:flex; align-items:center; justify-content:center; font-size:12px; text-align:center; padding:4px; }}
</style>
""", unsafe_allow_html=True)

ADMIN = require_admin("داشبورد پیچا ویزیت", "📍")


# ══════════════════════════════════════════════
# توابع کمکی
# ══════════════════════════════════════════════
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa(v) -> str:
    return str(v).translate(_FA)


def money(n) -> str:
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


def hhmm(t) -> str:
    return fa(str(t or "")[:5]) or "—"


def esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def img_file(rel) -> str | None:
    """مسیر ذخیره‌شده در دیتابیس (/static/...) → فایل روی دیسک (فقط داخل پوشهٔ static)"""
    if not rel or str(rel).strip() in ("", "None", "nan"):
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


# ══════════════════════════════════════════════
# داده‌ها
# ══════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner="در حال دریافت اطلاعات...")
def load_visitors():
    return read_sql("SELECT id, full_name, ISNULL(is_active,1) AS active FROM visitors ORDER BY full_name")


@st.cache_data(ttl=60, show_spinner="در حال دریافت اطلاعات...")
def load_data(g0: str, g1: str, vid: int | None):
    vf = "AND {a}.visitor_id=?" if vid else ""
    prm = (g0, g1) + ((vid,) if vid else ())
    visits = read_sql(f"""
        SELECT v.id, v.visitor_id, ISNULL(u.full_name, N'نامشخص') AS visitor,
               v.customer_code, ISNULL(CAST(c.C_Name AS NVARCHAR(200)), v.customer_code) AS customer,
               v.visit_date AS d, CONVERT(VARCHAR(8), v.visit_time, 108) AS t,
               v.latitude AS lat, v.longitude AS lng,
               ISNULL(v.selfie_path,'') AS selfie, ISNULL(v.description,'') AS descr
        FROM visits v
        LEFT JOIN visitors u ON u.id = v.visitor_id
        LEFT JOIN {SALES}.customer c ON c.C_Code = v.customer_code
        WHERE v.visit_date BETWEEN ? AND ? {vf.format(a='v')}
        ORDER BY v.visit_date, v.visit_time""", prm)
    orders = read_sql(f"""
        SELECT o.id, o.visitor_id, ISNULL(u.full_name, N'نامشخص') AS visitor,
               o.customer_code, ISNULL(CAST(c.C_Name AS NVARCHAR(200)), o.customer_code) AS customer,
               o.order_date AS d, CONVERT(VARCHAR(8), o.order_time, 108) AS t,
               o.latitude AS lat, o.longitude AS lng, o.total_amount AS total
        FROM orders o
        LEFT JOIN visitors u ON u.id = o.visitor_id
        LEFT JOIN {SALES}.customer c ON c.C_Code = o.customer_code
        WHERE o.order_date BETWEEN ? AND ? {vf.format(a='o')}
        ORDER BY o.order_date, o.order_time""", prm)
    pays = read_sql(f"""
        SELECT p.id, p.visitor_id, ISNULL(u.full_name, N'نامشخص') AS visitor,
               p.customer_code, ISNULL(CAST(c.C_Name AS NVARCHAR(200)), p.customer_code) AS customer,
               p.payment_date AS d, CONVERT(VARCHAR(8), p.payment_time, 108) AS t,
               p.latitude AS lat, p.longitude AS lng, p.payment_type AS ptype, p.amount,
               ISNULL(p.check_number,'') AS check_number, ISNULL(p.check_sayyadi,'') AS check_sayyadi,
               p.check_due_date AS check_due, ISNULL(p.check_image_path,'') AS check_img,
               ISNULL(p.transfer_account,'') AS tr_account, ISNULL(p.transfer_tracking,'') AS tr_tracking,
               ISNULL(p.transfer_image_path,'') AS tr_img, ISNULL(p.tracking_number,'') AS tracking
        FROM payments p
        LEFT JOIN visitors u ON u.id = p.visitor_id
        LEFT JOIN {SALES}.customer c ON c.C_Code = p.customer_code
        WHERE p.payment_date BETWEEN ? AND ? {vf.format(a='p')}
        ORDER BY p.payment_date, p.payment_time""", prm)
    items = read_sql(f"""
        SELECT oi.order_id, oi.article_code AS code,
               ISNULL(CAST(a.A_Name AS NVARCHAR(200)), oi.article_code) AS name,
               CAST(oi.quantity AS FLOAT) AS qty, CAST(oi.price AS FLOAT) AS price
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        LEFT JOIN {SALES}.article a ON a.A_Code = oi.article_code
        WHERE o.order_date BETWEEN ? AND ? {vf.format(a='o')}
        ORDER BY oi.order_id, oi.id""", prm)
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
                s = {**r.to_dict(), "kind": kind, "visit": None, "orders": [], "pays": []}
                by_key[key(r)] = s
                stops.append(s)
            s[field].append(r.to_dict())
    stops.sort(key=lambda s: (str(s["d"]), str(s["t"])))
    return stops


# ══════════════════════════════════════════════
# نوار بالا: فیلترها
# ══════════════════════════════════════════════
today_j = jdatetime.date.today()
today_g = today_j.togregorian()


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


vis_df = load_visitors()
vis_opts = {"همهٔ ویزیتورها": None}
vis_opts.update({(r["full_name"] + ("" if r["active"] else " (غیرفعال)")): int(r["id"]) for _, r in vis_df.iterrows()})

h_title, h_vis, h_per, h_ref, h_menu = st.columns([2.2, 2, 2, 0.9, 0.9], vertical_alignment="bottom")
with h_title:
    st.markdown("<div class='pv-title'>📍 داشبورد پیچا ویزیت</div>", unsafe_allow_html=True)
sel_vname = h_vis.selectbox("ویزیتور", list(vis_opts))
sel_vid = vis_opts[sel_vname]
period = h_per.selectbox("بازه", ["امروز", "دیروز", "۷ روز اخیر", "۳۰ روز اخیر", "این ماه", "ماه قبل", "بازه دلخواه"],
                         index=4)
if h_ref.button("🔄 بروزرسانی", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

if period == "بازه دلخواه":
    f_col, t_col = st.columns(2)
    with f_col:
        st.caption("از تاریخ")
        j0 = jalali_picker("from", jdatetime.date(today_j.year, today_j.month, 1))
    with t_col:
        st.caption("تا تاریخ")
        j1 = jalali_picker("to", today_j)
    if j1 < j0:
        st.warning("«تا تاریخ» قبل از «از تاریخ» است؛ جابه‌جا شد.")
        j0, j1 = j1, j0
    g0, g1 = j0.togregorian(), j1.togregorian()
else:
    g0, g1 = period_range(period)
    j0, j1 = jdatetime.date.fromgregorian(date=g0), jdatetime.date.fromgregorian(date=g1)

try:
    visits, orders, pays, items = load_data(g0.isoformat(), g1.isoformat(), sel_vid)
except Exception as e:
    st.error(f"❌ خطای دیتابیس: {e}")
    st.stop()
all_stops = build_stops(visits, orders, pays)

# ── فیلتر مشتری و کالا (گزینه‌ها از داده‌های همین بازه) ──
cust_names = {}
for s in all_stops:
    cust_names.setdefault(str(s["customer_code"]), s["customer"])
prod_names = dict(zip(items["code"].astype(str), items["name"])) if len(items) else {}

fc, fp = st.columns(2)
sel_cust = fc.multiselect("مشتری", sorted(cust_names, key=lambda c: cust_names[c]),
                          format_func=lambda c: f"{cust_names[c]} ({fa(c)})", placeholder="همهٔ مشتریان")
sel_prod = fp.multiselect("کالا", sorted(prod_names, key=lambda c: prod_names[c]),
                          format_func=lambda c: f"{prod_names[c]} ({fa(c)})", placeholder="همهٔ کالاها",
                          help="فقط سفارش‌هایی که این کالاها را دارند (و ویزیت/دریافتِ همان توقف) نمایش داده می‌شوند.")

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
stop_by_n = {s["n"]: s for s in stops}

f_visits = [s for s in stops if s["visit"] is not None]
f_orders = [(s, o) for s in stops for o in s["orders"]]
f_pays = [(s, p) for s in stops for p in s["pays"]]
order_sum = sum(float(o["total"] or 0) for _, o in f_orders)
pay_sum = sum(float(p["amount"] or 0) for _, p in f_pays)

# خلاصهٔ کالاها (فقط کالاهای فیلترشده، اگر فیلتر کالا فعال است)
prod_sum = {}
for _, o in f_orders:
    for it in items_by_order.get(int(o["id"]), []):
        if sel_prod and str(it["code"]) not in sel_prod:
            continue
        r = prod_sum.setdefault(str(it["code"]), {"name": it["name"], "qty": 0.0, "amount": 0.0, "orders": set()})
        r["qty"] += float(it["qty"] or 0)
        r["amount"] += float(it["qty"] or 0) * float(it["price"] or 0)
        r["orders"].add(int(o["id"]))

range_txt = (f"{fa(j0.strftime('%Y/%m/%d'))}" if g0 == g1
             else f"از {fa(j0.strftime('%Y/%m/%d'))} تا {fa(j1.strftime('%Y/%m/%d'))}")
filt_txt = []
if sel_cust:
    filt_txt.append("مشتری: " + "، ".join(cust_names[c] for c in sel_cust))
if sel_prod:
    filt_txt.append("کالا: " + "، ".join(prod_names[c] for c in sel_prod))
st.markdown(
    f"<div class='kpis'>"
    f"<span class='kpi'><i>{range_txt} · {sel_vname}</i></span>"
    + "".join(f"<span class='kpi f'><i>{esc(t)}</i></span>" for t in filt_txt)
    + f"<span class='kpi'><b>{fa(len(f_visits))}</b>ویزیت</span>"
    f"<span class='kpi'><b>{fa(len({s['customer_code'] for s in stops}))}</b>مشتری</span>"
    f"<span class='kpi'><b>{fa(len(f_orders))}</b>سفارش · {money(order_sum)}</span>"
    f"<span class='kpi'><b>{fa(len(f_pays))}</b>دریافت · {money(pay_sum)}</span>"
    f"</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# گزارش: Excel / PDF / چاپ  (همه از نتیجهٔ فیلترشده)
# ══════════════════════════════════════════════
def report_data():
    meta = [("بازه", range_txt), ("ویزیتور", sel_vname)]
    if sel_cust:
        meta.append(("مشتری", "، ".join(cust_names[c] for c in sel_cust)))
    if sel_prod:
        meta.append(("کالا", "، ".join(prod_names[c] for c in sel_prod)))
    meta.append(("جمع", f"{fa(len(f_visits))} ویزیت · {fa(len(f_orders))} سفارش ({money(order_sum)}) · "
                       f"{fa(len(f_pays))} دریافت ({money(pay_sum)})"))
    sec_v = [{"#": s["n"], "تاریخ": jdate(s["d"]), "ساعت": str(s["t"])[:5], "مشتری": s["customer"],
              "ویزیتور": s["visitor"],
              "ثبت‌ها": " + ".join(x for x in ["سفارش" if s["orders"] else "", "دریافت" if s["pays"] else ""] if x),
              "توضیحات": s["visit"]["descr"]} for s in f_visits]
    sec_o = [{"شماره": int(o["id"]), "تاریخ": jdate(o["d"]), "ساعت": str(o["t"])[:5], "مشتری": s["customer"],
              "ویزیتور": s["visitor"],
              "اقلام": "، ".join(f"{i['name']} × {i['qty']:g}" for i in items_by_order.get(int(o["id"]), [])),
              "مبلغ (ریال)": float(o["total"] or 0)} for s, o in f_orders]
    sec_p = [{"تاریخ": jdate(p["d"]), "ساعت": str(p["t"])[:5], "مشتری": s["customer"], "ویزیتور": s["visitor"],
              "نوع": p["ptype"], "مبلغ (ریال)": float(p["amount"] or 0),
              "جزئیات": (f"چک {p['check_number']} · صیادی {p['check_sayyadi']} · سررسید {jdate(p['check_due'])}"
                         if p["ptype"] == "چک" else
                         f"حساب {p['tr_account']} · پیگیری {p['tr_tracking'] or p['tracking']}"
                         if p["ptype"] == "حواله" else "")} for s, p in f_pays]
    sec_k = [{"کالا": r["name"], "کد": c, "تعداد": r["qty"], "سفارش‌ها": len(r["orders"]), "مبلغ (ریال)": r["amount"]}
             for c, r in sorted(prod_sum.items(), key=lambda x: -x[1]["amount"])]
    sections = [
        ("ویزیت‌ها", ["#", "تاریخ", "ساعت", "مشتری", "ویزیتور", "ثبت‌ها", "توضیحات"], sec_v),
        ("سفارش‌ها", ["شماره", "تاریخ", "ساعت", "مشتری", "ویزیتور", "اقلام", "مبلغ (ریال)"], sec_o),
        ("دریافت‌ها", ["تاریخ", "ساعت", "مشتری", "ویزیتور", "نوع", "مبلغ (ریال)", "جزئیات"], sec_p),
        ("خلاصهٔ کالاها", ["کالا", "کد", "تعداد", "سفارش‌ها", "مبلغ (ریال)"], sec_k),
    ]
    return meta, sections


@st.cache_data(show_spinner=False, max_entries=20)
def cached_excel(meta, sections):
    return report.to_excel(meta, sections)


@st.cache_data(show_spinner=False, max_entries=20)
def cached_pdf(meta, sections):
    return report.to_pdf(meta, sections)


meta, sections = report_data()
fname = f"PeechaVisit_{j0.strftime('%Y%m%d')}_{j1.strftime('%Y%m%d')}"

with h_menu.popover("☰ منو", use_container_width=True):
    st.download_button("📥 Excel", data=cached_excel(meta, sections), file_name=f"{fname}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True, on_click="ignore")
    try:
        st.download_button("📄 PDF", data=cached_pdf(meta, sections), file_name=f"{fname}.pdf",
                           mime="application/pdf", use_container_width=True, on_click="ignore")
    except Exception as e:
        st.caption(f"PDF ساخته نشد: {e}")
    if st.button("🖨️ چاپ", use_container_width=True):
        st.session_state["want_print"] = True
    st.caption("خروجی‌ها همان نتیجهٔ فیلترشدهٔ فعلی هستند.")
    st.divider()
    st.caption(f"👤 {ADMIN['name']} (@{ADMIN['username']})")
    if st.button("🚪 خروج", use_container_width=True):
        logout()


# ══════════════════════════════════════════════
# پنجره‌ها: جزئیات و چاپ
# ══════════════════════════════════════════════
def _closed():
    # پاک شدن انتخاب نقشه و جدول تا کلیک دوباره روی همان مورد هم کار کند
    st.session_state["ui_ver"] = st.session_state.get("ui_ver", 0) + 1
    st.session_state.pop("want_print", None)


def kv(rows) -> str:
    return "<div class='kv'>" + "".join(
        f"<div><small>{k}</small><b>{v if v not in (None, '') else '—'}</b></div>" for k, v in rows) + "</div>"


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


def order_html(o) -> str:
    its = items_by_order.get(int(o["id"]), [])
    if not its:
        return "<div class='muted'>اقلامی ثبت نشده است.</div>"
    rows = ""
    for i in its:
        qty = fa(f"{i['qty']:g}")
        rows += (f"<tr><td>{esc(i['name'])}<div class='muted'>کد {fa(i['code'])}</div></td><td>{qty}</td>"
                 f"<td>{money(i['price'])}</td><td>{money(i['qty'] * i['price'])}</td></tr>")
    return (f"<table class='itm'><thead><tr><th>کالا</th><th>تعداد</th><th>قیمت واحد</th><th>جمع</th></tr></thead>"
            f"<tbody>{rows}</tbody><tfoot><tr><td colspan='3'>جمع سفارش</td><td>{money(o['total'])}</td></tr></tfoot></table>")


def pay_html(p) -> str:
    if p["ptype"] == "چک":
        rows = [("شماره چک", fa(p["check_number"])), ("شماره صیادی", fa(p["check_sayyadi"])),
                ("سررسید", jdate(p["check_due"]))]
    elif p["ptype"] == "حواله":
        rows = [("حساب / کارت مقصد", f"<span dir='ltr'>{fa(p['tr_account'])}</span>"),
                ("شماره پیگیری", fa(p["tr_tracking"] or p["tracking"]))]
    else:
        rows = [("نوع", "نقدی")]
    return (f"<div class='dlg-amount' style='color:{KIND_COLOR['pay']};font-size:17px'>{p['ptype']} — {money(p['amount'])}</div>"
            + kv(rows))


KIND_LABEL = {"visit": ("ویزیت", "#edf1ff"), "order": ("سفارش", "#f3edff"), "pay": ("دریافت", "#e6f6ef")}


@st.dialog("جزئیات", width="large", on_dismiss=_closed)
def show_stop(n: int, focus: str, ref: int | None):
    s = stop_by_n[n]
    lbl, bg = KIND_LABEL[focus]
    focus_order = next((o for o in s["orders"] if int(o["id"]) == ref), None) if focus == "order" else None
    focus_pay = next((p for p in s["pays"] if int(p["id"]) == ref), None) if focus == "pay" else None

    # ── سرتیتر: همان چیزی که رویش کلیک شده ──
    head = s["customer"]
    if focus_order:
        head = f"سفارش شمارهٔ {fa(focus_order['id'])} — {s['customer']}"
    elif focus_pay:
        head = f"دریافت {focus_pay['ptype']} — {s['customer']}"
    st.markdown(
        f"<span class='dlg-kind' style='background:{bg};color:{KIND_COLOR[focus]}'>{lbl}</span>"
        f"<div class='dlg-head'>{esc(head)}</div>"
        + (f"<div class='dlg-amount' style='color:{KIND_COLOR['order']}'>{money(focus_order['total'])}</div>" if focus_order else "")
        + (f"<div class='dlg-amount' style='color:{KIND_COLOR['pay']}'>{money(focus_pay['amount'])}</div>" if focus_pay else "")
        + f"<div class='dlg-meta'>{jdate(s['d'])} · ساعت {hhmm(s['t'])} · {esc(s['visitor'])} · کد مشتری {fa(s['customer_code'])}</div>",
        unsafe_allow_html=True)

    # ── عکس‌ها (بند انگشتی؛ کلیک = بزرگ‌نمایی) ──
    imgs = stop_images(s)
    if focus_pay:      # عکسِ همین دریافت اول بیاید
        own = focus_pay["check_img"] if focus_pay["ptype"] == "چک" else focus_pay["tr_img"]
        imgs.sort(key=lambda x: x[0] != own)
    if imgs:
        st.markdown(gallery(imgs, f"{n}_{focus}"), unsafe_allow_html=True)

    # ── بدنه بر اساس نوع ردیف ──
    if focus_order:
        st.markdown(f"<div class='box'><div class='sec'>📦 اقلام سفارش</div>{order_html(focus_order)}</div>",
                    unsafe_allow_html=True)
    elif focus_pay:
        st.markdown(f"<div class='box'><div class='sec'>💰 جزئیات دریافت</div>{pay_html(focus_pay)}</div>",
                    unsafe_allow_html=True)

    others_o = [o for o in s["orders"] if o is not focus_order]
    others_p = [p for p in s["pays"] if p is not focus_pay]
    if focus == "visit" or others_o or others_p:
        if focus != "visit":
            st.markdown("<div class='sec' style='margin-top:4px'>🔗 در همین ویزیت</div>", unsafe_allow_html=True)
        c_o, c_p = st.columns(2)
        with c_o:
            body = "".join(f"<div class='muted'>سفارش شمارهٔ {fa(o['id'])}</div>{order_html(o)}" for o in others_o) \
                or "<div class='muted'>سفارشی ثبت نشده است.</div>"
            st.markdown(f"<div class='box'><div class='sec'>📦 سفارش</div>{body}</div>", unsafe_allow_html=True)
        with c_p:
            body = "".join(pay_html(p) for p in others_p) or "<div class='muted'>دریافتی ثبت نشده است.</div>"
            st.markdown(f"<div class='box'><div class='sec'>💰 دریافت</div>{body}</div>", unsafe_allow_html=True)

    if s["visit"] is not None and s["visit"]["descr"]:
        st.markdown(f"<div class='box'><div class='sec'>📝 توضیحات ویزیت</div>{esc(s['visit']['descr'])}</div>",
                    unsafe_allow_html=True)

    lat, lng = s.get("lat"), s.get("lng")
    if lat and lng:
        b1, b2, _ = st.columns([1, 1, 2])
        b1.link_button("🗺️ گوگل‌مپ", f"https://www.google.com/maps?q={lat},{lng}", use_container_width=True)
        b2.link_button("🧭 نشان", f"https://neshan.org/maps/@{lat},{lng},17z", use_container_width=True)


@st.dialog("پیش‌نمایش چاپ", width="large", on_dismiss=_closed)
def show_print():
    components.html(report.to_html(meta, sections, font_css()), height=640, scrolling=True)


# ══════════════════════════════════════════════
# نقشه + لیست
# ══════════════════════════════════════════════
ver = st.session_state.setdefault("ui_ver", 0)
to_open = None          # (شمارهٔ توقف, نوع, شناسهٔ سفارش/دریافت)
col_map, col_list = st.columns([1.55, 1], gap="medium")

with col_map:
    pts = [s for s in stops if s.get("lat") and s.get("lng")]
    visitor_ids = sorted({int(s["visitor_id"]) for s in stops})
    vcolor = {vid: VISITOR_COLORS[i % len(VISITOR_COLORS)] for i, vid in enumerate(visitor_ids)}
    names = {int(s["visitor_id"]): s["visitor"] for s in stops}
    if len(visitor_ids) > 1:
        st.markdown("<div class='legend'>" + "".join(
            f"<span><i style='background:{vcolor[v]}'></i>{names[v]}</span>" for v in visitor_ids) + "</div>",
            unsafe_allow_html=True)

    m = folium.Map(location=[35.6997, 51.3380], zoom_start=11, control_scale=True, tiles="OpenStreetMap")
    m.get_root().header.add_child(folium.Element(font_css().replace(".stApp *", "body *") + """
<style>
.leaflet-tooltip.pv-tip { direction:rtl; text-align:right; padding:8px 10px; border-radius:10px;
  border:1px solid #dfe3ea; box-shadow:0 6px 18px rgba(16,24,40,.16); font-family:Vazirmatn,Tahoma,sans-serif; }
.pv-tip .h { font-weight:800; font-size:13px; color:#17202e; }
.pv-tip .m { font-size:11px; color:#6b7686; margin:1px 0 4px; }
.pv-tip img { display:block; width:200px; max-height:140px; object-fit:cover; border-radius:8px; margin:4px 0; }
.pv-tip .b { display:inline-block; font-size:11px; font-weight:700; border-radius:12px; padding:1px 8px; margin:2px 0 0 4px; }
.pv-tip .f { font-size:10px; color:#868e96; margin-top:4px; }
.pv-cl { width:36px; height:36px; border-radius:50%; background:#020025; color:#fff; border:3px solid #fff;
  font:800 13px Vazirmatn,Tahoma,sans-serif; display:flex; align-items:center; justify-content:center;
  box-shadow:0 1px 5px rgba(0,0,0,.4); }
.pv-pin { width:28px; height:28px; border-radius:50%; color:#fff; font:700 12px Vazirmatn,Tahoma,sans-serif;
  display:flex; align-items:center; justify-content:center; border:2px solid #fff; box-shadow:0 1px 4px rgba(0,0,0,.35); }
</style>"""))

    # مسیر هر ویزیتور در هر روز
    routes = {}
    for s in pts:
        routes.setdefault((int(s["visitor_id"]), str(s["d"])), []).append([float(s["lat"]), float(s["lng"])])
    for (vid, _), line in routes.items():
        if len(line) > 1:
            folium.PolyLine(line, color=vcolor[vid], weight=3, opacity=.55, dash_array="6 6").add_to(m)

    # نشانگرهای نزدیک به هم گروه می‌شوند (عدد = تعداد)؛ کلیک = بزرگ‌نمایی،
    # و در بیشترین بزرگ‌نمایی نشانگرهای هم‌مکان باز می‌شوند تا همه قابل کلیک باشند
    cluster = MarkerCluster(
        options={"maxClusterRadius": 34, "spiderfyOnMaxZoom": True, "showCoverageOnHover": False,
                 "spiderfyDistanceMultiplier": 1.7},
        icon_create_function="""function(c){return L.divIcon({className:'',iconSize:[36,36],
            html:'<div class="pv-cl">'+c.getChildCount().toLocaleString('fa-IR')+'</div>'});}""",
    ).add_to(m)

    for s in pts:
        badges = ""
        if s["orders"]:
            badges += f"<span class='b' style='background:#f3edff;color:{KIND_COLOR['order']}'>سفارش {money(sum(o['total'] or 0 for o in s['orders']))}</span>"
        for p in s["pays"]:
            badges += f"<span class='b' style='background:#e6f6ef;color:{KIND_COLOR['pay']}'>{p['ptype']} {money(p['amount'])}</span>"
        th = img_src(s["visit"]["selfie"]) if s["visit"] is not None else None
        img_tag = f"<img src='{th}'>" if th else ""
        tip = (f"<div class='h'>{fa(s['n'])}. {esc(s['customer'])}</div>"
               f"<div class='m'>{jdate(s['d'])} · {hhmm(s['t'])} · {esc(s['visitor'])}</div>"
               f"{img_tag}{badges}"
               f"<div class='f'>برای جزئیات کلیک کنید</div>")
        color = vcolor[int(s["visitor_id"])] if len(visitor_ids) > 1 else KIND_COLOR[s["kind"]]
        folium.Marker(
            [float(s["lat"]), float(s["lng"])],
            icon=folium.DivIcon(html=f"<div class='pv-pin' style='background:{color}'>{fa(s['n'])}</div>",
                                icon_size=(28, 28), icon_anchor=(14, 14)),
            tooltip=folium.Tooltip(tip, class_name="pv-tip", sticky=False),
        ).add_to(cluster)
    if pts:
        lats = [float(s["lat"]) for s in pts]
        lngs = [float(s["lng"]) for s in pts]
        m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]], padding=(30, 30), max_zoom=16)

    out = st_folium(m, key=f"map_{ver}", height=620, use_container_width=True,
                    returned_objects=["last_object_clicked_tooltip"])
    tip_txt = (out or {}).get("last_object_clicked_tooltip") or ""
    mt = re.match(r"\s*([0-9]+)\.", tip_txt.translate(_EN))
    if mt and int(mt.group(1)) in stop_by_n:
        n_ = int(mt.group(1))
        to_open = (n_, stop_by_n[n_]["kind"], None)
    if not stops:
        st.info("با این فیلترها موردی وجود ندارد. بازه، ویزیتور، مشتری یا کالا را تغییر دهید.")


def table(rows, cols, key, height=540, selectable=True):
    if not rows:
        st.caption("موردی نیست.")
        return None
    df = pd.DataFrame(rows)[cols[::-1]]          # ستون اول در سمت راست دیده شود
    if not selectable:
        st.dataframe(df, hide_index=True, use_container_width=True, height=height)
        return None
    ev = st.dataframe(df, hide_index=True, use_container_width=True, height=height, key=key,
                      on_select="rerun", selection_mode="single-row")
    sel = ev.selection.rows if ev and ev.selection else []
    return rows[sel[0]]["_open"] if sel else None


with col_list:
    t_v, t_o, t_p, t_k = st.tabs([f"ویزیت‌ها ({fa(len(f_visits))})", f"سفارش‌ها ({fa(len(f_orders))})",
                                  f"دریافت‌ها ({fa(len(f_pays))})", f"کالاها ({fa(len(prod_sum))})"])
    with t_v:
        rows = [{"_open": (s["n"], "visit", None), "#": fa(s["n"]), "مشتری": s["customer"], "ویزیتور": s["visitor"],
                 "تاریخ": jdate(s["d"]), "ساعت": hhmm(s["t"]),
                 "ثبت‌ها": " + ".join(x for x in ["سفارش" if s["orders"] else "", "دریافت" if s["pays"] else ""] if x)}
                for s in f_visits]
        to_open = table(rows, ["#", "مشتری", "ویزیتور", "تاریخ", "ساعت", "ثبت‌ها"], f"tv_{ver}") or to_open
    with t_o:
        rows = [{"_open": (s["n"], "order", int(o["id"])), "شماره": fa(o["id"]), "مشتری": s["customer"],
                 "ویزیتور": s["visitor"], "تاریخ": jdate(o["d"]), "مبلغ": money(o["total"])} for s, o in f_orders]
        to_open = table(rows, ["شماره", "مشتری", "ویزیتور", "تاریخ", "مبلغ"], f"to_{ver}") or to_open
    with t_p:
        rows = [{"_open": (s["n"], "pay", int(p["id"])), "مشتری": s["customer"], "ویزیتور": s["visitor"],
                 "تاریخ": jdate(p["d"]), "نوع": p["ptype"], "مبلغ": money(p["amount"])} for s, p in f_pays]
        to_open = table(rows, ["مشتری", "ویزیتور", "تاریخ", "نوع", "مبلغ"], f"tp_{ver}") or to_open
    with t_k:
        rows = [{"کالا": r["name"], "کد": fa(c), "تعداد": fa(f"{r['qty']:g}"), "سفارش": fa(len(r["orders"])),
                 "مبلغ": money(r["amount"])} for c, r in sorted(prod_sum.items(), key=lambda x: -x[1]["amount"])]
        table(rows, ["کالا", "کد", "تعداد", "سفارش", "مبلغ"], "tk", selectable=False)

# فقط یک پنجره در هر اجرا
if st.session_state.get("want_print"):
    show_print()
elif to_open and to_open[0] in stop_by_n:
    show_stop(*to_open)
