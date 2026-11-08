# admin.py - پیچا ویزیت | پنل مدیریت v4.0
# ════════════════════════════════════════════════
# مدیریت کاربران، تنظیمات سامانه و وضعیت سرویس‌ها
# اجرا:  streamlit run admin.py --server.port 8502
# ════════════════════════════════════════════════
import ipaddress
import re
import secrets
import urllib.request
from datetime import datetime

import jdatetime
import pandas as pd
import pyodbc
import streamlit as st

import config
from config import APP, SECURITY, DEFAULTS, SETTINGS_FILE
from db import get_conn, TRACKING_DB, SALES_DB
from auth import hash_password, is_locked
from panel_auth import require_admin, logout
from ui_font import font_css

C1, C2 = APP["PRIMARY_COLOR"], APP["ACCENT_COLOR"]
PW_MIN = int(SECURITY["PASSWORD_MIN_LEN"])
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,50}$")
INSECURE_SECRET = DEFAULTS["SECURITY"]["SESSION_SECRET"]

st.set_page_config(page_title=f"مدیریت | {APP['NAME']}", page_icon="🛠️", layout="wide")

# ══════════════════════════════════════════════
# ظاهر
# ══════════════════════════════════════════════
st.markdown(f"""
<style>
.stApp {{ background:#f3f5fb; direction:rtl; }}
.block-container {{ padding:3.4rem 28px 40px !important; max-width:1280px; }}
p, label, .stMarkdown, .stCaption, .stAlert {{ direction:rtl; text-align:right; }}
input, textarea {{ direction:rtl; }}
input[type=number] {{ direction:ltr; text-align:left; }}

/* هدر */
.pv-head {{
    background:{C1};
    border-radius:18px; padding:20px 24px; color:#fff; margin-bottom:14px;
    display:flex; justify-content:space-between; align-items:center;
}}
.pv-head .t {{ font-size:20px; font-weight:900; }}
.pv-head .s {{ font-size:12px; opacity:.75; margin-top:4px; }}
.pv-head .chip {{ background:rgba(255,255,255,.14); border-radius:30px; padding:6px 14px; font-size:12px; font-weight:700; }}

/* تب‌ها */
.stTabs [data-baseweb="tab-list"] {{
    background:#fff; border-radius:12px; padding:5px; gap:4px;
    box-shadow:0 2px 10px rgba(0,0,0,.05);
}}
.stTabs [data-baseweb="tab"] {{ border-radius:9px; font-weight:700; padding:8px 18px; }}
.stTabs [aria-selected="true"] {{ background:{C1}; color:#fff !important; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none; }}

/* کارت آمار */
.kpi {{ background:#fff; border-radius:14px; padding:14px 16px; border:1px solid #e6e9f5;
        display:flex; align-items:center; gap:12px; }}
.kpi .ic {{ width:42px; height:42px; border-radius:12px; display:flex; align-items:center;
           justify-content:center; font-size:20px; }}
.kpi .v {{ font-size:24px; font-weight:900; color:#0f172a; line-height:1.1; }}
.kpi .l {{ font-size:12px; color:#64748b; font-weight:600; }}

/* کارت کاربر */
.u-card {{ background:#fff; border:1px solid #e6e9f5; border-radius:14px; padding:14px 16px;
          display:flex; align-items:center; gap:14px; margin-top:10px; }}
.u-av {{ width:46px; height:46px; border-radius:50%; flex-shrink:0; color:#fff; font-weight:900;
        display:flex; align-items:center; justify-content:center; font-size:18px; }}
.u-main {{ flex:1; min-width:0; }}
.u-name {{ font-size:15px; font-weight:800; color:#0f172a; }}
.u-meta {{ font-size:12px; color:#64748b; margin-top:2px; direction:rtl; }}
.u-meta b {{ color:#334155; }}
.u-stats {{ display:flex; gap:8px; flex-wrap:wrap; }}
.u-stat {{ background:#f1f5f9; border-radius:10px; padding:6px 10px; text-align:center; min-width:62px; }}
.u-stat .n {{ font-size:15px; font-weight:900; color:#1e293b; }}
.u-stat .k {{ font-size:10px; color:#64748b; }}
.badge {{ display:inline-block; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:700; margin-left:4px; }}
.b-admin {{ background:#f3e8ff; color:#7e22ce; }}
.b-visitor {{ background:#e0e7ff; color:#3730a3; }}
.b-on {{ background:#dcfce7; color:#166534; }}
.b-off {{ background:#f1f5f9; color:#64748b; }}
.b-lock {{ background:#ffedd5; color:#c2410c; }}
.b-me {{ background:#fef9c3; color:#854d0e; }}

/* بخش‌ها */
.sec-t {{ font-size:15px; font-weight:900; color:{C1}; margin:4px 0 2px; }}
.sec-s {{ font-size:12px; color:#94a3b8; margin-bottom:8px; }}
.cfg-tbl {{ width:100%; border-collapse:collapse; font-size:13px; direction:rtl; }}
.cfg-tbl td {{ padding:7px 10px; border-bottom:1px solid #eef1f6; }}
.cfg-tbl td:first-child {{ color:#64748b; width:45%; }}
.cfg-tbl td:last-child {{ direction:ltr; text-align:left; font-weight:700; color:#1e293b; }}
.svc {{ background:#fff; border:1px solid #e6e9f5; border-radius:12px; padding:12px 14px; margin-bottom:8px; }}
.svc .n {{ font-weight:800; font-size:14px; }}
.svc .a {{ font-size:12px; direction:ltr; text-align:left; color:#475569; }}
</style>
""", unsafe_allow_html=True)

st.markdown(font_css(), unsafe_allow_html=True)
ADMIN = require_admin("پنل مدیریت پیچا", "🛠️")


# ══════════════════════════════════════════════
# توابع کمکی
# ══════════════════════════════════════════════
def flash(msg: str, kind: str = "success"):
    """پیامی که بعد از rerun نمایش داده می‌شود"""
    st.session_state["_flash"] = (kind, msg)


def show_flash():
    if "_flash" in st.session_state:
        kind, msg = st.session_state.pop("_flash")
        getattr(st, kind)(msg)


def run_sql(sql: str, params=()) -> int:
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(sql, params)
        n = cur.rowcount
        conn.commit()
        return n
    finally:
        cur.close(); conn.close()


def scalar(sql: str, params=(), db=TRACKING_DB):
    conn = get_conn(db); cur = conn.cursor()
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close(); conn.close()


def to_jalali(dt, with_time=True) -> str:
    if dt is None or (not isinstance(dt, str) and pd.isna(dt)):
        return "—"
    try:
        dt = pd.Timestamp(dt).to_pydatetime()
        j = jdatetime.datetime.fromgregorian(datetime=dt)
        return j.strftime("%Y/%m/%d  %H:%M" if with_time else "%Y/%m/%d")
    except Exception:
        return str(dt)[:16]


def ensure_cols():
    cols = [
        ("role", "VARCHAR(20) NOT NULL DEFAULT 'visitor'"),
        ("phone", "VARCHAR(20) NULL"), ("last_login", "DATETIME NULL"),
        ("failed_attempts", "INT NOT NULL DEFAULT 0"),
        ("locked_until", "DATETIME NULL"), ("notes", "NVARCHAR(500) NULL"),
        ("created_at", "DATETIME NOT NULL DEFAULT GETDATE()"),
    ]
    try:
        conn = get_conn(autocommit=True); cur = conn.cursor()
        for c, d in cols:
            cur.execute(f"""IF NOT EXISTS(SELECT 1 FROM sys.columns
                WHERE object_id=OBJECT_ID('visitors') AND name='{c}')
                ALTER TABLE visitors ADD {c} {d}""")
        cur.close(); conn.close()
    except Exception:
        pass


@st.cache_resource
def _ensure_once():
    ensure_cols()
    return True


_ensure_once()


def load_users() -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql("""
            SELECT v.id, v.username, v.full_name,
                   ISNULL(v.role,'visitor')       AS role,
                   ISNULL(v.phone,'')             AS phone,
                   CAST(v.is_active AS INT)       AS is_active,
                   v.last_login,
                   ISNULL(v.failed_attempts,0)    AS failed_attempts,
                   v.locked_until,
                   ISNULL(v.notes,'')             AS notes,
                   v.created_at,
                   (SELECT COUNT(*) FROM visits   WHERE visitor_id=v.id) AS n_visits,
                   (SELECT COUNT(*) FROM orders   WHERE visitor_id=v.id) AS n_orders,
                   (SELECT COUNT(*) FROM payments WHERE visitor_id=v.id) AS n_pays,
                   (SELECT MAX(visit_date) FROM visits WHERE visitor_id=v.id) AS last_visit
            FROM visitors v ORDER BY v.id
        """, conn)
    finally:
        conn.close()
    df["locked"] = df["locked_until"].apply(
        lambda x: is_locked(pd.Timestamp(x).to_pydatetime()) if pd.notna(x) else False)
    return df


def username_taken(username: str, exclude_id: int | None = None) -> bool:
    n = scalar("SELECT COUNT(*) FROM visitors WHERE LOWER(username)=LOWER(?) AND id<>?",
               (username, exclude_id or -1))
    return bool(n)


def guard_admin_change(users: pd.DataFrame, uid: int, new_role: str, new_active: bool) -> str | None:
    """جلوگیری از قفل شدن پنل: حداقل یک مدیر فعال باید بماند"""
    row = users[users["id"] == uid].iloc[0]
    was_active_admin = row["role"] == "admin" and bool(row["is_active"])
    stays_active_admin = new_role == "admin" and new_active
    if was_active_admin and not stays_active_admin:
        if uid == ADMIN["id"]:
            return "نمی‌توانید دسترسی مدیر یا فعال بودن حساب خودتان را بردارید."
        active_admins = int(((users["role"] == "admin") & (users["is_active"] == 1)).sum())
        if active_admins <= 1:
            return "حداقل یک مدیر فعال باید در سامانه باقی بماند."
    return None


def avatar_color(name: str) -> str:
    palette = ["#4f46e5", "#0891b2", "#059669", "#d97706", "#db2777", "#7c3aed", "#2563eb", "#dc2626"]
    return palette[sum(map(ord, name)) % len(palette)]


# ══════════════════════════════════════════════
# هدر
# ══════════════════════════════════════════════
now_j = jdatetime.datetime.now()
hc1, hc2 = st.columns([6, 1])
with hc1:
    st.markdown(f"""
    <div class='pv-head'>
        <div>
            <div class='t'>🛠️ پنل مدیریت {APP['NAME']}</div>
            <div class='s'>نسخهٔ {APP['VERSION']} &nbsp;•&nbsp; {now_j.strftime('%Y/%m/%d  %H:%M')}</div>
        </div>
        <div class='chip'>👑 {ADMIN['name']} (@{ADMIN['username']})</div>
    </div>""", unsafe_allow_html=True)
with hc2:
    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    if st.button("🚪 خروج", use_container_width=True):
        logout()

show_flash()

try:
    users_df = load_users()
except Exception as e:
    st.error(f"❌ خطا در اتصال به دیتابیس: {e}")
    st.info("از تب «وضعیت سیستم» یا فایل config.py تنظیمات اتصال را بررسی کنید.")
    users_df = pd.DataFrame()

tab_users, tab_new, tab_cfg, tab_sys = st.tabs([
    f"👥 کاربران ({len(users_df)})", "➕ کاربر جدید", "⚙️ تنظیمات", "🩺 وضعیت سیستم",
])


# ══════════════════════════════════════════════
# تب ۱ — کاربران
# ══════════════════════════════════════════════
with tab_users:
    if users_df.empty:
        st.info("هیچ کاربری یافت نشد.")
    else:
        k = st.columns(5)
        for col, ic, bg, v, lb in [
            (k[0], "👥", "#e0e7ff", len(users_df), "کل کاربران"),
            (k[1], "✅", "#dcfce7", int(users_df["is_active"].sum()), "فعال"),
            (k[2], "🧭", "#e0f2fe", int((users_df["role"] == "visitor").sum()), "ویزیتور"),
            (k[3], "🛡️", "#f3e8ff", int((users_df["role"] == "admin").sum()), "مدیر"),
            (k[4], "🔒", "#ffedd5", int(users_df["locked"].sum()), "قفل‌شده"),
        ]:
            col.markdown(f"""<div class='kpi'><div class='ic' style='background:{bg}'>{ic}</div>
                <div><div class='v'>{v}</div><div class='l'>{lb}</div></div></div>""",
                         unsafe_allow_html=True)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        f1, f2, f3 = st.columns([3, 1.3, 1.3])
        q = f1.text_input("جستجو", placeholder="🔍 نام، نام کاربری یا تلفن...",
                          label_visibility="collapsed")
        f_role = f2.selectbox("نقش", ["همه نقش‌ها", "ویزیتور", "مدیر"], label_visibility="collapsed")
        f_state = f3.selectbox("وضعیت", ["همه وضعیت‌ها", "فعال", "غیرفعال", "قفل‌شده"],
                               label_visibility="collapsed")

        view = users_df
        if q.strip():
            ql = q.strip().lower()
            view = view[view.apply(lambda r: ql in str(r["full_name"]).lower()
                                   or ql in str(r["username"]).lower()
                                   or ql in str(r["phone"]), axis=1)]
        if f_role != "همه نقش‌ها":
            view = view[view["role"] == ("admin" if f_role == "مدیر" else "visitor")]
        if f_state == "فعال":
            view = view[view["is_active"] == 1]
        elif f_state == "غیرفعال":
            view = view[view["is_active"] == 0]
        elif f_state == "قفل‌شده":
            view = view[view["locked"]]

        if view.empty:
            st.info("کاربری با این فیلتر پیدا نشد.")

        for _, u in view.iterrows():
            uid = int(u["id"])
            fname, uname = str(u["full_name"]), str(u["username"])
            role, act, locked = str(u["role"]), bool(u["is_active"]), bool(u["locked"])
            is_me = uid == ADMIN["id"]
            badges = (
                ("<span class='badge b-admin'>🛡️ مدیر</span>" if role == "admin"
                 else "<span class='badge b-visitor'>🧭 ویزیتور</span>")
                + ("<span class='badge b-on'>فعال</span>" if act else "<span class='badge b-off'>غیرفعال</span>")
                + (f"<span class='badge b-lock'>🔒 قفل تا {to_jalali(u['locked_until']).split()[-1]}</span>" if locked else "")
                + ("<span class='badge b-me'>شما</span>" if is_me else "")
            )
            last_visit = to_jalali(u["last_visit"], with_time=False)
            st.markdown(f"""
            <div class='u-card' style='{"opacity:.6" if not act else ""}'>
                <div class='u-av' style='background:{avatar_color(uname)}'>{fname[:1]}</div>
                <div class='u-main'>
                    <div class='u-name'>{fname} {badges}</div>
                    <div class='u-meta'>
                        <span style='direction:ltr;display:inline-block'>@{uname}</span>
                        &nbsp;•&nbsp; 📱 <b>{u['phone'] or '—'}</b>
                        &nbsp;•&nbsp; آخرین ورود: <b>{to_jalali(u['last_login'])}</b>
                        &nbsp;•&nbsp; آخرین ویزیت: <b>{last_visit}</b>
                    </div>
                </div>
                <div class='u-stats'>
                    <div class='u-stat'><div class='n'>{int(u['n_visits'])}</div><div class='k'>ویزیت</div></div>
                    <div class='u-stat'><div class='n'>{int(u['n_orders'])}</div><div class='k'>سفارش</div></div>
                    <div class='u-stat'><div class='n'>{int(u['n_pays'])}</div><div class='k'>دریافت</div></div>
                </div>
            </div>""", unsafe_allow_html=True)

            with st.expander(f"✏️ ویرایش و عملیات — {fname}"):
                with st.form(f"edit_{uid}"):
                    c1, c2, c3 = st.columns(3)
                    new_name = c1.text_input("👤 نام کامل", value=fname)
                    new_phone = c2.text_input("📱 تلفن", value=str(u["phone"]))
                    new_role = c3.selectbox("🛡️ نقش", ["visitor", "admin"],
                                            index=1 if role == "admin" else 0,
                                            format_func=lambda x: "🛡️ مدیر" if x == "admin" else "🧭 ویزیتور")
                    c4, c5, c6 = st.columns(3)
                    new_pass = c4.text_input("🔒 رمز جدید", type="password",
                                             placeholder="خالی = بدون تغییر",
                                             help=f"حداقل {PW_MIN} کاراکتر")
                    new_notes = c5.text_input("📝 یادداشت", value=str(u["notes"]))
                    c6.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                    new_act = c6.toggle("حساب فعال", value=act)
                    saved = st.form_submit_button("💾 ذخیرهٔ تغییرات", type="primary")

                if saved:
                    err = None
                    if not new_name.strip():
                        err = "نام کامل نمی‌تواند خالی باشد."
                    elif new_pass and len(new_pass) < PW_MIN:
                        err = f"رمز جدید باید حداقل {PW_MIN} کاراکتر باشد."
                    else:
                        err = guard_admin_change(users_df, uid, new_role, new_act)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        try:
                            fields = "full_name=?, phone=?, role=?, is_active=?, notes=?"
                            params = [new_name.strip(), new_phone.strip() or None, new_role,
                                      int(new_act), new_notes.strip() or None]
                            if new_pass:
                                fields += ", password_hash=?, failed_attempts=0, locked_until=NULL"
                                params.append(hash_password(new_pass))
                            run_sql(f"UPDATE visitors SET {fields} WHERE id=?", (*params, uid))
                            flash(f"✅ اطلاعات «{new_name.strip()}» ذخیره شد"
                                  + (" و رمز تغییر کرد." if new_pass else "."))
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

                a1, a2, a3 = st.columns(3)
                if locked or int(u["failed_attempts"]) > 0:
                    if a1.button("🔓 رفع قفل / صفر کردن تلاش‌ها", key=f"ul_{uid}", use_container_width=True):
                        run_sql("UPDATE visitors SET failed_attempts=0, locked_until=NULL WHERE id=?", (uid,))
                        flash(f"✅ قفل حساب @{uname} برداشته شد.")
                        st.rerun()
                if a2.button("⏸️ غیرفعال کردن" if act else "▶️ فعال کردن", key=f"tg_{uid}",
                             use_container_width=True):
                    err = guard_admin_change(users_df, uid, role, not act)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        run_sql("UPDATE visitors SET is_active=? WHERE id=?", (int(not act), uid))
                        flash(f"✅ حساب @{uname} {'غیرفعال' if act else 'فعال'} شد.")
                        st.rerun()
                has_records = int(u["n_visits"]) + int(u["n_orders"]) + int(u["n_pays"]) > 0
                with a3.popover("🗑️ حذف کاربر", use_container_width=True, disabled=is_me):
                    if has_records:
                        st.warning("این کاربر سابقهٔ ویزیت/سفارش/دریافت دارد و حذف آن سوابق را "
                                   "بی‌صاحب می‌کند. به‌جای حذف، حساب را غیرفعال کنید.")
                    else:
                        st.write(f"حذف دائمی @{uname}؟ این کار برگشت‌پذیر نیست.")
                        if st.button("بله، حذف شود", key=f"del_{uid}", type="primary"):
                            err = guard_admin_change(users_df, uid, "visitor", False)
                            if err:
                                st.error(f"❌ {err}")
                            else:
                                run_sql("DELETE FROM visitors WHERE id=?", (uid,))
                                flash(f"🗑️ کاربر @{uname} حذف شد.")
                                st.rerun()


# ══════════════════════════════════════════════
# تب ۲ — کاربر جدید
# ══════════════════════════════════════════════
with tab_new:
    st.markdown("<div class='sec-t'>➕ ثبت کاربر / ویزیتور جدید</div>"
                "<div class='sec-s'>پس از ثبت، کاربر با همین نام کاربری و رمز وارد اپ موبایل می‌شود.</div>",
                unsafe_allow_html=True)
    ver = st.session_state.setdefault("new_user_ver", 0)
    with st.form(f"new_user_{ver}"):
        n1, n2 = st.columns(2)
        n_full = n1.text_input("👤 نام و نام خانوادگی *", placeholder="مثال: علی محمدی")
        n_user = n1.text_input("🔑 نام کاربری *", placeholder="ali.m",
                               help="فقط حروف انگلیسی، عدد و . _ - (۳ تا ۵۰ کاراکتر)")
        n_phone = n1.text_input("📱 شماره موبایل", placeholder="09121234567")
        n_pass = n2.text_input("🔒 رمز عبور *", type="password", placeholder=f"حداقل {PW_MIN} کاراکتر")
        n_pass2 = n2.text_input("🔒 تکرار رمز عبور *", type="password")
        n_role = n2.selectbox("🛡️ نقش", ["visitor", "admin"],
                              format_func=lambda x: "🧭 ویزیتور" if x == "visitor" else "🛡️ مدیر سیستم")
        n_notes = st.text_area("📝 یادداشت (اختیاری)", height=80)
        create = st.form_submit_button("✅ ثبت کاربر", type="primary")

    if create:
        errs = []
        uname = n_user.strip()
        if not n_full.strip():
            errs.append("نام کامل الزامی است.")
        if not USERNAME_RE.match(uname):
            errs.append("نام کاربری فقط حروف انگلیسی، عدد و . _ - و بین ۳ تا ۵۰ کاراکتر باشد.")
        if len(n_pass) < PW_MIN:
            errs.append(f"رمز باید حداقل {PW_MIN} کاراکتر باشد.")
        if n_pass != n_pass2:
            errs.append("رمز و تکرار آن یکسان نیست.")
        if n_phone.strip() and not re.fullmatch(r"0?9\d{9}", n_phone.strip()):
            errs.append("شماره موبایل معتبر نیست (مثال: 09121234567).")
        if not errs:
            try:
                if username_taken(uname):
                    errs.append("این نام کاربری قبلاً ثبت شده است.")
            except Exception as e:
                errs.append(f"خطای دیتابیس: {e}")
        if errs:
            for e in errs:
                st.error(f"❌ {e}")
        else:
            try:
                run_sql("""INSERT INTO visitors
                           (username,password_hash,full_name,role,phone,notes,is_active)
                           VALUES (?,?,?,?,?,?,1)""",
                        (uname, hash_password(n_pass), n_full.strip(), n_role,
                         n_phone.strip() or None, n_notes.strip() or None))
                st.session_state["new_user_ver"] = ver + 1
                flash(f"✅ کاربر «{n_full.strip()}» با نام کاربری @{uname} ثبت شد.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطا: {e}")


# ══════════════════════════════════════════════
# تب ۳ — تنظیمات
# ══════════════════════════════════════════════
def _valid_host(h: str) -> bool:
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        return bool(re.fullmatch(r"[A-Za-z0-9.-]{1,253}", h))


with tab_cfg:
    cur_cfg = config.current_settings()
    # تنظیمات اپ موبایل بدون ری‌استارت اعمال می‌شود، پس در مقایسه نیست
    loaded = {s: getattr(config, s) for s in DEFAULTS if s != "MOBILE"}
    if {s: v for s, v in cur_cfg.items() if s != "MOBILE"} != loaded:
        st.warning("⚠️ تنظیمات ذخیره‌شده با تنظیمات در حال اجرا فرق دارد. "
                   "برای اعمال، سرویس‌ها (app.py، داشبورد و این پنل) را ری‌استارت کنید.")
    if SECURITY["SESSION_SECRET"] == INSECURE_SECRET:
        st.error("🔑 کلید امنیتی توکن‌ها هنوز مقدار پیش‌فرض است و هر کسی کد را دارد می‌تواند توکن جعل کند. "
                 "پایین همین صفحه «ساخت کلید جدید» را بزنید.")

    # ── اپ موبایل (بدون ری‌استارت) ──
    M = cur_cfg["MOBILE"]
    with st.form("mobile_form"):
        st.markdown("<div class='sec-t'>📱 اپ موبایل ویزیتورها</div>"
                    "<div class='sec-s'>بلافاصله اعمال می‌شود؛ روی گوشی با دکمهٔ «همگام‌سازی» یا باز کردن دوبارهٔ اپ.</div>",
                    unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1:
            m_selfie = st.toggle("📸 سلفی برای ثبت ویزیت اجباری باشد", value=M["REQUIRE_SELFIE"])
            m_price = st.toggle("💰 قیمت کالا نمایش داده شود", value=M["SHOW_PRICE"])
            m_stock = st.toggle("📦 موجودی کالا نمایش داده شود", value=M["SHOW_STOCK"])
        with m2:
            m_instock = st.toggle("✅ فقط کالاهای دارای موجودی در لیست بیایند", value=M["ONLY_IN_STOCK"])
            m_oversell = st.toggle("⚠️ سفارش بیشتر از موجودی (یا بدون موجودی) مجاز باشد",
                                   value=M["ALLOW_OVERSELL"],
                                   help="خاموش: تعداد سفارش از موجودی بیشتر نمی‌شود")
        save_mobile = st.form_submit_button("💾 ذخیرهٔ تنظیمات اپ موبایل", type="primary")
    if save_mobile:
        config.save_settings({"MOBILE": {"REQUIRE_SELFIE": m_selfie, "SHOW_PRICE": m_price,
                                         "SHOW_STOCK": m_stock, "ONLY_IN_STOCK": m_instock,
                                         "ALLOW_OVERSELL": m_oversell}})
        flash("✅ تنظیمات اپ موبایل ذخیره شد و از همین حالا اعمال می‌شود.")
        st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    N, D, S, A = cur_cfg["NETWORK"], cur_cfg["DATABASES"], cur_cfg["SECURITY"], cur_cfg["APP"]
    with st.form("settings_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            with st.container(border=True):
                st.markdown("<div class='sec-t'>🌐 شبکه و سرور</div>"
                            "<div class='sec-s'>آی‌پی کامپیوتر سرور در شبکه و پورت سرویس‌ها</div>",
                            unsafe_allow_html=True)
                s_ip = st.text_input("آی‌پی سرور (برای موبایل‌ها)", value=N["SERVER_IP"])
                p1, p2 = st.columns(2)
                s_api = p1.number_input("پورت API موبایل", 1, 65535, int(N["FLASK_PORT"]))
                s_pwa = p2.number_input("پورت وب‌اپ", 1, 65535, int(N["PWA_PORT"]))
                p3, p4 = st.columns(2)
                s_dash = p3.number_input("پورت داشبورد", 1, 65535, int(N["DASHBOARD_PORT"]))
                s_adm = p4.number_input("پورت پنل مدیریت", 1, 65535, int(N["ADMIN_PORT"]))
                s_debug = st.toggle("حالت دیباگ API (فقط برای تست)", value=bool(N["DEBUG"]))

            with st.container(border=True):
                st.markdown("<div class='sec-t'>🏷️ برنامه</div>", unsafe_allow_html=True)
                a1, a2 = st.columns(2)
                s_name = a1.text_input("نام فارسی", value=A["NAME"])
                s_name_en = a2.text_input("نام انگلیسی", value=A["NAME_EN"])
                s_web = st.text_input("وب‌سایت", value=A["WEBSITE"])
                a3, a4 = st.columns(2)
                s_c1 = a3.color_picker("رنگ اصلی", value=A["PRIMARY_COLOR"])
                s_c2 = a4.color_picker("رنگ تأکیدی", value=A["ACCENT_COLOR"])

        with col_b:
            with st.container(border=True):
                st.markdown("<div class='sec-t'>🗄️ دیتابیس SQL Server</div>"
                            "<div class='sec-s'>نام کاربری خالی = ورود ویندوزی (Trusted Connection)</div>",
                            unsafe_allow_html=True)
                s_srv = st.text_input("نام SQL Server", value=N["SERVER_NAME"],
                                      help="مثال: SERWIN\\RAD یا localhost\\SQLEXPRESS")
                d1, d2 = st.columns(2)
                s_tdb = d1.text_input("دیتابیس ردیابی", value=D["TRACKING_DB"])
                s_sdb = d2.text_input("دیتابیس فروش", value=D["SALES_DB"])
                drivers = sorted(set(pyodbc.drivers()) | {D["DRIVER"]})
                s_drv = st.selectbox("درایور ODBC", drivers, index=drivers.index(D["DRIVER"]))
                d3, d4 = st.columns(2)
                s_user = d3.text_input("نام کاربری SQL", value=D["USER"])
                s_pwd = d4.text_input("رمز SQL", type="password", value="",
                                      placeholder="•••• (بدون تغییر)" if D["PASSWORD"] else "")
                s_extra = st.text_input("پارامترهای اضافهٔ اتصال", value=D["EXTRA"],
                                        placeholder="TrustServerCertificate=yes")
                s_timeout = st.number_input("مهلت اتصال (ثانیه)", 1, 300, int(D["TIMEOUT"]))

            with st.container(border=True):
                st.markdown("<div class='sec-t'>🔒 امنیت و ورود</div>", unsafe_allow_html=True)
                e1, e2 = st.columns(2)
                s_hours = e1.number_input("اعتبار ورود (ساعت)", 1, 720, int(S["SESSION_HOURS"]))
                s_pwmin = e2.number_input("حداقل طول رمز", 4, 64, int(S["PASSWORD_MIN_LEN"]))
                e3, e4 = st.columns(2)
                s_tries = e3.number_input("تلاش ناموفق تا قفل", 1, 50, int(S["MAX_LOGIN_ATTEMPTS"]))
                s_lock = e4.number_input("مدت قفل (دقیقه)", 1, 1440, int(S["LOCKOUT_MINUTES"]))

        save = st.form_submit_button("💾 ذخیرهٔ تنظیمات", type="primary", use_container_width=True)

    if save:
        errs = []
        if not _valid_host(s_ip.strip()):
            errs.append("آی‌پی سرور معتبر نیست.")
        ports = [s_api, s_pwa, s_dash, s_adm]
        if len(set(ports)) != len(ports):
            errs.append("پورت سرویس‌ها نباید تکراری باشد.")
        if not s_srv.strip() or not s_tdb.strip() or not s_sdb.strip():
            errs.append("نام SQL Server و دیتابیس‌ها الزامی است.")
        if errs:
            for e in errs:
                st.error(f"❌ {e}")
        else:
            config.save_settings({
                "NETWORK": {"SERVER_IP": s_ip.strip(), "SERVER_NAME": s_srv.strip(),
                            "FLASK_PORT": s_api, "PWA_PORT": s_pwa,
                            "DASHBOARD_PORT": s_dash, "ADMIN_PORT": s_adm, "DEBUG": s_debug},
                "DATABASES": {"TRACKING_DB": s_tdb.strip(), "SALES_DB": s_sdb.strip(),
                              "DRIVER": s_drv, "USER": s_user.strip(), "EXTRA": s_extra.strip(),
                              "TIMEOUT": s_timeout,
                              # رمز خالی = بدون تغییر؛ با حذف نام کاربری، رمز هم پاک می‌شود
                              "PASSWORD": (s_pwd if s_pwd else D["PASSWORD"]) if s_user.strip() else ""},
                "SECURITY": {"SESSION_HOURS": s_hours, "PASSWORD_MIN_LEN": s_pwmin,
                             "MAX_LOGIN_ATTEMPTS": s_tries, "LOCKOUT_MINUTES": s_lock},
                "APP": {"NAME": s_name.strip(), "NAME_EN": s_name_en.strip(), "WEBSITE": s_web.strip(),
                        "PRIMARY_COLOR": s_c1, "ACCENT_COLOR": s_c2},
            })
            flash("✅ تنظیمات ذخیره شد. برای اعمال، سرویس‌ها را ری‌استارت کنید.")
            st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    k1, k2 = st.columns(2)
    with k1:
        with st.container(border=True):
            st.markdown("<div class='sec-t'>🔑 کلید امنیتی توکن‌ها</div>"
                        "<div class='sec-s'>با ساخت کلید جدید، همهٔ ویزیتورها باید دوباره وارد اپ شوند.</div>",
                        unsafe_allow_html=True)
            if st.button("🔑 ساخت کلید جدید", use_container_width=True):
                config.save_settings({"SECURITY": {"SESSION_SECRET": secrets.token_hex(32)}})
                flash("✅ کلید جدید ساخته شد. app.py را ری‌استارت کنید.")
                st.rerun()
    with k2:
        with st.container(border=True):
            overrides = config.read_settings_file()
            st.markdown("<div class='sec-t'>↩️ بازگشت به پیش‌فرض</div>"
                        f"<div class='sec-s'>{sum(len(v) for v in overrides.values())} مقدار سفارشی در "
                        f"<code>settings.json</code></div>", unsafe_allow_html=True)
            with st.popover("حذف همهٔ تنظیمات سفارشی", use_container_width=True, disabled=not overrides):
                st.write("همهٔ مقادیر به config.py برمی‌گردند (کلید امنیتی هم).")
                if st.button("بله، بازگردانی شود", type="primary"):
                    config.reset_settings()
                    flash("✅ تنظیمات به پیش‌فرض برگشت. سرویس‌ها را ری‌استارت کنید.")
                    st.rerun()


# ══════════════════════════════════════════════
# تب ۴ — وضعیت سیستم
# ══════════════════════════════════════════════
def api_alive() -> bool:
    try:
        port = config.NETWORK["FLASK_PORT"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


with tab_sys:
    ip = config.NETWORK["SERVER_IP"]
    s1, s2 = st.columns([1.1, 1])
    with s1:
        st.markdown("<div class='sec-t'>🔗 سرویس‌ها</div>"
                    "<div class='sec-s'>آدرس‌هایی که موبایل‌ها و کامپیوترهای شبکه باز می‌کنند</div>",
                    unsafe_allow_html=True)
        alive = api_alive()
        for name, port, note in [
            ("📡 API موبایل (app.py)", config.NETWORK["FLASK_PORT"],
             "🟢 در حال اجرا" if alive else "🔴 پاسخ نمی‌دهد"),
            ("📱 وب‌اپ موبایل (run_client.py)", config.NETWORK["PWA_PORT"], ""),
            ("📊 داشبورد", config.NETWORK["DASHBOARD_PORT"], ""),
            ("🛠️ پنل مدیریت", config.NETWORK["ADMIN_PORT"], ""),
        ]:
            st.markdown(f"<div class='svc'><div class='n'>{name} <span style='float:left;font-size:12px'>{note}</span></div>"
                        f"<div class='a'>http://{ip}:{port}</div></div>", unsafe_allow_html=True)
        st.caption("در اپ اندروید، در صفحهٔ ورود بخش «⚙️ آدرس سرور» همین آی‌پی را وارد کنید.")

    with s2:
        st.markdown("<div class='sec-t'>🗄️ دیتابیس</div>", unsafe_allow_html=True)
        try:
            stats = {
                "اتصال tracking": "✅ برقرار",
                "ویزیت‌ها (کل / امروز)": f"{scalar('SELECT COUNT(*) FROM visits')} / "
                                         f"{scalar('SELECT COUNT(*) FROM visits WHERE visit_date=CAST(GETDATE() AS DATE)')}",
                "سفارش‌ها": scalar("SELECT COUNT(*) FROM orders"),
                "دریافت‌ها": scalar("SELECT COUNT(*) FROM payments"),
            }
        except Exception as e:
            stats = {"اتصال tracking": f"❌ {e}"}
        try:
            stats[f"اتصال {SALES_DB}"] = "✅ برقرار"
            stats["مشتریان فعال"] = scalar(
                "SELECT COUNT(*) FROM customer WHERE [Delete]=0 OR [Delete] IS NULL", db=SALES_DB)
            stats["کالاها"] = scalar(
                "SELECT COUNT(*) FROM article WHERE [Delete]=0 OR [Delete] IS NULL", db=SALES_DB)
        except Exception as e:
            stats[f"اتصال {SALES_DB}"] = f"❌ {str(e)[:120]}"
        rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in stats.items())
        st.markdown(f"<table class='cfg-tbl'>{rows}</table>", unsafe_allow_html=True)
        if st.button("🔄 تست دوباره", use_container_width=True):
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("ℹ️ تنظیمات در حال اجرا"):
        for title, sec in [("شبکه", "NETWORK"), ("دیتابیس", "DATABASES"), ("امنیت", "SECURITY"), ("برنامه", "APP")]:
            rows = "".join(
                f"<tr><td>{k}</td><td>{'••••••' if any(x in k for x in ('SECRET', 'PASSWORD')) and v else v}</td></tr>"
                for k, v in getattr(config, sec).items())
            st.markdown(f"<b>{title}</b><table class='cfg-tbl'>{rows}</table><br>", unsafe_allow_html=True)
        st.caption(f"فایل تنظیمات: {SETTINGS_FILE}")
