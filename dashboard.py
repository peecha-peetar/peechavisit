# dashboard.py - پیچا ویزیت | داشبورد v6
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
from PIL import Image
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

st.set_page_config(page_title="داشبورد | پیچا ویزیت", page_icon="📍",
                   layout="wide", initial_sidebar_state="collapsed")

from config import APP
from db import get_conn, SALES_DB
from panel_auth import require_admin, logout
from ui_font import font_css

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
.pv-range {{ font-size:12px; color:#6b7686; }}
.kpis {{ display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 12px; }}
.kpi {{ background:#fff; border:1px solid #e3e7ef; border-radius:10px; padding:6px 12px;
        font-size:13px; color:#495057; white-space:nowrap; }}
.kpi b {{ font-size:15px; color:#17202e; margin-left:4px; }}
.kpi i {{ font-style:normal; color:#6b7686; }}
.legend {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:6px; font-size:12px; }}
.legend span {{ display:inline-flex; align-items:center; gap:5px; background:#fff; border:1px solid #e3e7ef;
                border-radius:20px; padding:2px 10px; }}
.legend i {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
/* روز/ماه/سال در موبایل هم کنار هم بمانند */
[class*="st-key-jp_"] [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; gap:6px !important; }}
[class*="st-key-jp_"] [data-testid="stColumn"] {{ min-width:0 !important; width:auto !important; flex:1 1 0 !important; }}
.dlg-head {{ font-size:18px; font-weight:800; color:#17202e; }}
.dlg-meta {{ font-size:13px; color:#6b7686; margin:2px 0 8px; }}
.chip {{ display:inline-block; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600; margin-left:4px; }}
.sec {{ font-size:15px; font-weight:800; margin:14px 0 6px; padding-top:10px; border-top:1px solid #eef0f4; }}
.kv {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:8px; }}
.kv div {{ background:#f6f7fa; border-radius:8px; padding:6px 10px; }}
.kv small {{ display:block; font-size:11px; color:#6b7686; }}
.kv b {{ font-size:14px; color:#17202e; font-weight:600; }}
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


def img_file(rel) -> str | None:
    """مسیر ذخیره‌شده در دیتابیس (/static/...) → فایل روی دیسک (فقط داخل پوشهٔ static)"""
    if not rel or str(rel).strip() in ("", "None", "nan"):
        return None
    p = os.path.realpath(os.path.join(BASE_DIR, str(rel).strip().lstrip("/\\")))
    return p if p.startswith(STATIC_DIR + os.sep) and os.path.isfile(p) else None


@st.cache_data(show_spinner=False, max_entries=2000)
def thumb_b64(path: str, mtime: float) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((220, 150))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def thumb_tag(rel) -> str:
    p = img_file(rel)
    if not p:
        return ""
    try:
        return f"<img src='data:image/jpeg;base64,{thumb_b64(p, os.path.getmtime(p))}'>"
    except Exception:
        return ""


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
    return visits, orders, pays


@st.cache_data(ttl=60, show_spinner=False)
def load_items(order_id: int):
    return read_sql(f"""
        SELECT ISNULL(CAST(a.A_Name AS NVARCHAR(200)), oi.article_code) AS name, oi.article_code AS code,
               CAST(oi.quantity AS FLOAT) AS qty, CAST(oi.price AS FLOAT) AS price
        FROM order_items oi
        LEFT JOIN {SALES}.article a ON a.A_Code = oi.article_code
        WHERE oi.order_id=? ORDER BY oi.id""", (order_id,))


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
    for i, s in enumerate(stops, 1):
        s["n"] = i
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
    visits, orders, pays = load_data(g0.isoformat(), g1.isoformat(), sel_vid)
except Exception as e:
    st.error(f"❌ خطای دیتابیس: {e}")
    st.stop()
stops = build_stops(visits, orders, pays)
stop_by_n = {s["n"]: s for s in stops}

range_txt = (f"{fa(j0.strftime('%Y/%m/%d'))}" if g0 == g1
             else f"از {fa(j0.strftime('%Y/%m/%d'))} تا {fa(j1.strftime('%Y/%m/%d'))}")
st.markdown(
    f"<div class='kpis'>"
    f"<span class='kpi'><i>{range_txt} · {sel_vname}</i></span>"
    f"<span class='kpi'><b>{fa(len(visits))}</b>ویزیت</span>"
    f"<span class='kpi'><b>{fa(visits['customer_code'].nunique() if len(visits) else 0)}</b>مشتری</span>"
    f"<span class='kpi'><b>{fa(len(orders))}</b>سفارش · {money(orders['total'].sum() if len(orders) else 0)}</span>"
    f"<span class='kpi'><b>{fa(len(pays))}</b>دریافت · {money(pays['amount'].sum() if len(pays) else 0)}</span>"
    f"</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# خروجی اکسل و خروج
# ══════════════════════════════════════════════
def excel_bytes() -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        sheets = {
            "ویزیت‌ها": pd.DataFrame([{
                "تاریخ": jdate(r.d), "ساعت": str(r.t)[:5], "ویزیتور": r.visitor, "مشتری": r.customer,
                "کد مشتری": r.customer_code, "توضیحات": r.descr, "عرض": r.lat, "طول": r.lng}
                for r in visits.itertuples()]),
            "سفارش‌ها": pd.DataFrame([{
                "شماره": r.id, "تاریخ": jdate(r.d), "ساعت": str(r.t)[:5], "ویزیتور": r.visitor,
                "مشتری": r.customer, "کد مشتری": r.customer_code, "جمع (ریال)": float(r.total or 0)}
                for r in orders.itertuples()]),
            "دریافت‌ها": pd.DataFrame([{
                "تاریخ": jdate(r.d), "ساعت": str(r.t)[:5], "ویزیتور": r.visitor, "مشتری": r.customer,
                "کد مشتری": r.customer_code, "نوع": r.ptype, "مبلغ (ریال)": float(r.amount or 0),
                "شماره چک": r.check_number, "صیادی": r.check_sayyadi, "سررسید": jdate(r.check_due) if r.check_due else "",
                "حساب مقصد": r.tr_account, "پیگیری": r.tr_tracking or r.tracking}
                for r in pays.itertuples()]),
        }
        items = []
        for r in orders.itertuples():
            for it in load_items(int(r.id)).itertuples():
                items.append({"شماره سفارش": r.id, "مشتری": r.customer, "کالا": it.name, "کد کالا": it.code,
                              "تعداد": it.qty, "قیمت واحد": it.price, "جمع": it.qty * it.price})
        sheets["اقلام سفارش"] = pd.DataFrame(items)
        head = w.book.add_format({"bold": True, "bg_color": C1, "font_color": "white", "border": 1})
        for name, df in sheets.items():
            if df.empty:
                df = pd.DataFrame({"": ["در این بازه موردی نیست"]})
            df.to_excel(w, sheet_name=name, index=False)
            ws = w.sheets[name]
            ws.right_to_left()
            for i, col in enumerate(df.columns):
                ws.write(0, i, col, head)
                ws.set_column(i, i, 18, w.book.add_format({"num_format": "#,##0"}) if "ریال" in str(col) or col in ("قیمت واحد", "جمع") else None)
    return out.getvalue()


with h_menu.popover("☰ منو", use_container_width=True):
    st.download_button("📥 خروجی Excel", data=excel_bytes(), use_container_width=True,
                       file_name=f"PeechaVisit_{j0.strftime('%Y%m%d')}_{j1.strftime('%Y%m%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption(f"👤 {ADMIN['name']} (@{ADMIN['username']})")
    if st.button("🚪 خروج", use_container_width=True):
        logout()


# ══════════════════════════════════════════════
# جزئیات یک توقف (پنجره)
# ══════════════════════════════════════════════
def _closed():
    # پاک شدن انتخاب نقشه و جدول تا کلیک دوباره روی همان مورد هم کار کند
    st.session_state["ui_ver"] = st.session_state.get("ui_ver", 0) + 1


def kv(items) -> str:
    return "<div class='kv'>" + "".join(
        f"<div><small>{k}</small><b>{v if v not in (None, '') else '—'}</b></div>" for k, v in items) + "</div>"


def show_image(rel, caption):
    p = img_file(rel)
    if p:
        st.image(p, caption=caption, width=320)
    elif rel:
        st.caption(f"🖼️ {caption}: فایل عکس روی سرور پیدا نشد ({rel})")


@st.dialog("جزئیات", width="large", on_dismiss=_closed)
def show_stop(s):
    chips = []
    if s["visit"] is not None:
        chips.append(f"<span class='chip' style='background:#edf1ff;color:{KIND_COLOR['visit']}'>ویزیت</span>")
    if s["orders"]:
        chips.append(f"<span class='chip' style='background:#f3edff;color:{KIND_COLOR['order']}'>سفارش</span>")
    if s["pays"]:
        chips.append(f"<span class='chip' style='background:#e6f6ef;color:{KIND_COLOR['pay']}'>دریافت</span>")
    st.markdown(f"<div class='dlg-head'>{fa(s['n'])}. {s['customer']} {''.join(chips)}</div>"
                f"<div class='dlg-meta'>{jdate(s['d'])} · ساعت {hhmm(s['t'])} · {s['visitor']} · کد مشتری {fa(s['customer_code'])}</div>",
                unsafe_allow_html=True)

    lat, lng = s.get("lat"), s.get("lng")
    if lat and lng:
        b1, b2, _ = st.columns([1, 1, 2])
        b1.link_button("🗺️ گوگل‌مپ", f"https://www.google.com/maps?q={lat},{lng}", use_container_width=True)
        b2.link_button("🧭 نشان", f"https://neshan.org/maps/@{lat},{lng},17z", use_container_width=True)

    if s["visit"] is not None:
        v = s["visit"]
        st.markdown("<div class='sec'>📍 ویزیت</div>", unsafe_allow_html=True)
        st.markdown(kv([("توضیحات", v["descr"] or "—"), ("مختصات", f"<span dir='ltr'>{fa(f'{lat:.5f}, {lng:.5f}')}</span>" if lat else "—")]),
                    unsafe_allow_html=True)
        if v["selfie"]:
            show_image(v["selfie"], "سلفی ویزیتور")
        else:
            st.caption("سلفی ثبت نشده است.")

    for o in s["orders"]:
        st.markdown(f"<div class='sec'>📦 سفارش شمارهٔ {fa(o['id'])} — {money(o['total'])}</div>",
                    unsafe_allow_html=True)
        items = load_items(int(o["id"]))
        if items.empty:
            st.caption("اقلامی ثبت نشده است.")
        else:
            st.dataframe(pd.DataFrame({
                "جمع": [money(q * p) for q, p in zip(items.qty, items.price)],
                "قیمت واحد": [money(p) for p in items.price],
                "تعداد": [fa(f"{q:g}") for q in items.qty],
                "کالا": items.name,
            }), hide_index=True, use_container_width=True)

    for p in s["pays"]:
        st.markdown(f"<div class='sec'>💰 دریافت {p['ptype']} — {money(p['amount'])}</div>", unsafe_allow_html=True)
        if p["ptype"] == "چک":
            st.markdown(kv([("شماره چک", fa(p["check_number"])), ("شماره صیادی", fa(p["check_sayyadi"])),
                            ("سررسید", jdate(p["check_due"]) if p["check_due"] else "—")]), unsafe_allow_html=True)
            show_image(p["check_img"], "عکس چک")
        elif p["ptype"] == "حواله":
            st.markdown(kv([("حساب / کارت مقصد", fa(p["tr_account"])),
                            ("شماره پیگیری", fa(p["tr_tracking"] or p["tracking"]))]), unsafe_allow_html=True)
            show_image(p["tr_img"], "عکس رسید حواله")


# ══════════════════════════════════════════════
# نقشه + لیست
# ══════════════════════════════════════════════
ver = st.session_state.setdefault("ui_ver", 0)
to_open = None
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
    m.get_root().header.add_child(folium.Element(font_css().replace("<style>", "<style>\n").replace(
        ".stApp *", "body *") + """
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
        tip = (f"<div class='h'>{fa(s['n'])}. {s['customer']}</div>"
               f"<div class='m'>{jdate(s['d'])} · {hhmm(s['t'])} · {s['visitor']}</div>"
               f"{thumb_tag(s['visit']['selfie']) if s['visit'] is not None else ''}{badges}"
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
    mt = re.match(r"\s*([0-9۰-۹]+)\.", tip_txt.translate(_EN) if tip_txt else "")
    if mt:
        to_open = int(mt.group(1).translate(_EN))
    if not stops:
        st.info("در این بازه ثبتی وجود ندارد. بازه یا ویزیتور را تغییر دهید.")


def table(rows, cols, key, height=540):
    if not rows:
        st.caption("موردی در این بازه نیست.")
        return None
    df = pd.DataFrame(rows)[cols[::-1]]          # ستون اول در سمت راست دیده شود
    ev = st.dataframe(df.drop(columns=["_n"]) if "_n" in df else df, hide_index=True,
                      use_container_width=True, height=height, key=key,
                      on_select="rerun", selection_mode="single-row")
    sel = ev.selection.rows if ev and ev.selection else []
    return rows[sel[0]]["_n"] if sel else None


with col_list:
    t_v, t_o, t_p = st.tabs([f"ویزیت‌ها ({fa(len(visits))})", f"سفارش‌ها ({fa(len(orders))})",
                             f"دریافت‌ها ({fa(len(pays))})"])
    with t_v:
        rows = [{"_n": s["n"], "#": fa(s["n"]), "مشتری": s["customer"], "ویزیتور": s["visitor"],
                 "تاریخ": jdate(s["d"]), "ساعت": hhmm(s["t"]),
                 "ثبت‌ها": " + ".join(x for x in ["سفارش" if s["orders"] else "", "دریافت" if s["pays"] else ""] if x)}
                for s in stops if s["visit"] is not None]
        n = table(rows, ["#", "مشتری", "ویزیتور", "تاریخ", "ساعت", "ثبت‌ها", "_n"], f"tv_{ver}")
        to_open = n or to_open
    with t_o:
        rows = [{"_n": s["n"], "#": fa(s["n"]), "مشتری": s["customer"], "ویزیتور": s["visitor"],
                 "تاریخ": jdate(o["d"]), "ساعت": hhmm(o["t"]), "مبلغ": money(o["total"])}
                for s in stops for o in s["orders"]]
        n = table(rows, ["#", "مشتری", "ویزیتور", "تاریخ", "ساعت", "مبلغ", "_n"], f"to_{ver}")
        to_open = n or to_open
    with t_p:
        rows = [{"_n": s["n"], "#": fa(s["n"]), "مشتری": s["customer"], "ویزیتور": s["visitor"],
                 "تاریخ": jdate(p["d"]), "نوع": p["ptype"], "مبلغ": money(p["amount"])}
                for s in stops for p in s["pays"]]
        n = table(rows, ["#", "مشتری", "ویزیتور", "تاریخ", "نوع", "مبلغ", "_n"], f"tp_{ver}")
        to_open = n or to_open

if to_open and to_open in stop_by_n:
    show_stop(stop_by_n[to_open])
