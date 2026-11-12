# admin.py - پیچا ویزیت | پنل مدیریت v4.0
# ════════════════════════════════════════════════
# مدیریت کاربران، تنظیمات سامانه و وضعیت سرویس‌ها
# اجرا:  streamlit run admin.py --server.port 8502
# ════════════════════════════════════════════════
import io
import os
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
from mobile_rules import LABELS as MOBILE_LABELS, global_rules, user_overrides, dump_overrides
from ui_font import font_css
from ui_theme import theme_css, app_bar
import perms as P
import vaseteh as V

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
input, textarea {{ direction:rtl; }}
input[type=number] {{ direction:ltr; text-align:left; }}

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
.b-app {{ background:#e0f2fe; color:#075985; }}
.b-dash {{ background:#fff4e6; color:#b35c00; }}
.b-vas {{ background:#ecfdf5; color:#047857; }}

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

st.markdown(font_css() + "\n" + theme_css(), unsafe_allow_html=True)
ADMIN = require_admin("پنل مدیریت پیچا", "🛠️")


# ══════════════════════════════════════════════
# توابع کمکی
# ══════════════════════════════════════════════
def RESTART_NOTE(msg: str) -> str:
    """زیر برنامهٔ اصلی (start.bat جدید / سرویس ویندوز) ری‌استارت خودکار است"""
    if os.environ.get("PEECHA_PARENT"):
        return msg.split(".")[0] + ". سرویس‌ها ظرف چند ثانیه خودکار دوباره شروع می‌شوند."
    return msg


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
        ("app_settings", "NVARCHAR(1000) NULL"),
        ("dash_perms", "NVARCHAR(2000) NULL"),
        ("sales_codes", "NVARCHAR(400) NULL"),
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
    try:
        import audit
        audit.ensure_schema()      # جدول‌های پیام، لاگ و مشتری جدید
    except Exception:
        pass
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
                   ISNULL(v.app_settings,'')      AS app_settings,
                   ISNULL(v.dash_perms,'')        AS dash_perms,
                   ISNULL(v.sales_codes,'')       AS sales_codes,
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


@st.cache_data(ttl=60, show_spinner=False)
def vaseteh_list():
    """واسطه‌ها (ویزیتورهای نرم‌افزار فروش): ([{code,name,customers}], خطا)"""
    try:
        return V.vasetehs(), None
    except Exception as e:
        return [], str(e)


def vaseteh_label(code: str) -> str:
    v = {x["code"]: x for x in vaseteh_list()[0]}.get(code)
    return f"{v['name']} ({code}) — {v['customers']} مشتری" if v else f"{code} (در نرم‌افزار فروش پیدا نشد)"


def vaseteh_names(codes) -> str:
    names = {x["code"]: x["name"] for x in vaseteh_list()[0]}
    return "، ".join(names.get(c, c) for c in codes)


def vaseteh_picker(container, current, key):
    """انتخاب یک یا چند واسطهٔ نرم‌افزار فروش برای کاربر"""
    rows, err = vaseteh_list()
    opts = [x["code"] for x in rows]
    opts += [c for c in current if c not in opts]
    if err:
        container.caption(f"⚠️ فهرست واسطه‌ها خوانده نشد: {err}")
    return container.multiselect(
        "🔗 واسطه / ویزیتور در نرم‌افزار فروش", opts, default=[c for c in current if c in opts],
        format_func=vaseteh_label, key=key, placeholder="بدون واسطه",
        help="اپ فقط مشتریانی را نشان می‌دهد که در نرم‌افزار فروش یکی از این واسطه‌ها را دارند "
             "(جدول CustomerVaseteh). خالی = طبق تنظیمات (همه یا هیچ). مدیر همیشه همه را می‌بیند.")


def avatar_color(name: str) -> str:
    palette = ["#4f46e5", "#0891b2", "#059669", "#d97706", "#db2777", "#7c3aed", "#2563eb", "#dc2626"]
    return palette[sum(map(ord, name)) % len(palette)]


# ══════════════════════════════════════════════
# هدر
# ══════════════════════════════════════════════
now_j = jdatetime.datetime.now()
st.markdown(app_bar(f"🛠️ پنل مدیریت {APP['NAME']}",
                    f"نسخهٔ {APP['VERSION']} · {now_j.strftime('%Y/%m/%d  %H:%M')}",
                    [f"👑 {ADMIN['name']} (@{ADMIN['username']})"]), unsafe_allow_html=True)
_, hc_out = st.columns([7, 1])
if hc_out.button("🚪 خروج", width="stretch"):
    logout()

show_flash()

try:
    users_df = load_users()
except Exception as e:
    st.error(f"❌ خطا در اتصال به دیتابیس: {e}")
    st.info("از تب «وضعیت سیستم» یا فایل config.py تنظیمات اتصال را بررسی کنید.")
    users_df = pd.DataFrame()

try:
    _nc_new = int(scalar("SELECT COUNT(*) FROM new_customers WHERE status='new'") or 0)
except Exception:
    _nc_new = 0
tab_users, tab_new, tab_nc, tab_cfg, tab_sys = st.tabs([
    f"👥 کاربران ({len(users_df)})", "➕ کاربر جدید",
    f"🆕 مشتریان جدید{f' ({_nc_new})' if _nc_new else ''}", "⚙️ تنظیمات", "🩺 وضعیت سیستم",
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
                + ("<span class='badge b-app'>📱 تنظیمات اختصاصی</span>" if user_overrides(u["app_settings"]) else "")
                + ("<span class='badge b-dash'>📊 داشبورد</span>" if role != "admin" and P.parse(u["dash_perms"])["access"] else "")
                + (f"<span class='badge b-vas'>🔗 {vaseteh_names(V.parse_codes(u['sales_codes']))}</span>" if u["sales_codes"] else "")
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
                    new_vas = vaseteh_picker(st, V.parse_codes(u["sales_codes"]), f"vas_{uid}")
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
                            fields = "full_name=?, phone=?, role=?, is_active=?, notes=?, sales_codes=?"
                            params = [new_name.strip(), new_phone.strip() or None, new_role,
                                      int(new_act), new_notes.strip() or None, V.dump_codes(new_vas)]
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
                    if a1.button("🔓 رفع قفل / صفر کردن تلاش‌ها", key=f"ul_{uid}", width="stretch"):
                        run_sql("UPDATE visitors SET failed_attempts=0, locked_until=NULL WHERE id=?", (uid,))
                        flash(f"✅ قفل حساب @{uname} برداشته شد.")
                        st.rerun()
                if a2.button("⏸️ غیرفعال کردن" if act else "▶️ فعال کردن", key=f"tg_{uid}",
                             width="stretch"):
                    err = guard_admin_change(users_df, uid, role, not act)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        run_sql("UPDATE visitors SET is_active=? WHERE id=?", (int(not act), uid))
                        flash(f"✅ حساب @{uname} {'غیرفعال' if act else 'فعال'} شد.")
                        st.rerun()
                has_records = int(u["n_visits"]) + int(u["n_orders"]) + int(u["n_pays"]) > 0
                with a3.popover("🗑️ حذف کاربر", width="stretch", disabled=is_me):
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

                # ── تنظیمات اپ موبایل فقط برای همین کاربر ──
                glob = global_rules()
                mine = user_overrides(u["app_settings"])
                choices = ["پیش‌فرض", "بله", "خیر"]
                with st.form(f"app_{uid}"):
                    st.markdown("<div class='sec-t'>📱 تنظیمات اپ برای این کاربر</div>"
                                "<div class='sec-s'>«پیش‌فرض» = همان تنظیم سراسری (تب تنظیمات). بدون ری‌استارت اعمال می‌شود.</div>",
                                unsafe_allow_html=True)
                    cols = st.columns(3)
                    picked = {}
                    for i, (k, label) in enumerate(MOBILE_LABELS.items()):
                        col = cols[i % 3]
                        cur = "پیش‌فرض" if k not in mine else ("بله" if mine[k] else "خیر")
                        picked[k] = col.selectbox(
                            label, choices, index=choices.index(cur), key=f"app_{uid}_{k}",
                            help=f"پیش‌فرض سراسری: {'بله' if glob.get(k) else 'خیر'}")
                    save_app = st.form_submit_button("💾 ذخیرهٔ تنظیمات اپ این کاربر")
                if save_app:
                    raw = dump_overrides({k: v == "بله" for k, v in picked.items() if v != "پیش‌فرض"})
                    run_sql("UPDATE visitors SET app_settings=? WHERE id=?", (raw, uid))
                    flash(f"✅ تنظیمات اپ @{uname} ذخیره شد"
                          + ("." if raw else " (همه روی پیش‌فرض)."))
                    st.rerun()

                # ── دسترسی داشبورد ──
                if role == "admin":
                    st.caption("📊 مدیر سیستم به داشبورد و همهٔ اطلاعات دسترسی کامل دارد.")
                else:
                    dp = P.parse(u["dash_perms"])
                    vis_all = {int(r["id"]): r["full_name"] for _, r in users_df.iterrows()}
                    with st.form(f"dash_{uid}"):
                        st.markdown("<div class='sec-t'>📊 دسترسی داشبورد</div>"
                                    "<div class='sec-s'>مثلاً برای سرپرست فروش: فقط ویزیتورهای تیم خودش، با یا بدون مبلغ‌ها.</div>",
                                    unsafe_allow_html=True)
                        d_access = st.toggle("اجازهٔ ورود به داشبورد", value=dp["access"])
                        d_vis = st.multiselect("ویزیتورهایی که می‌بیند (خالی = همه)", list(vis_all),
                                               default=[v for v in dp["visitors"] if v in vis_all],
                                               format_func=lambda v: vis_all[v], placeholder="همهٔ ویزیتورها")
                        dc = st.columns(3)
                        d_flags = {k: dc[i].toggle(lbl, value=dp[k]) for i, (k, lbl) in enumerate(P.LABELS.items())}
                        save_dash = st.form_submit_button("💾 ذخیرهٔ دسترسی داشبورد")
                    if save_dash:
                        run_sql("UPDATE visitors SET dash_perms=? WHERE id=?",
                                (P.dump({"access": d_access, "visitors": d_vis, **d_flags}), uid))
                        flash(f"✅ دسترسی داشبورد @{uname} ذخیره شد"
                              + ("." if d_access else " (بدون دسترسی)."))
                        st.rerun()


# ══════════════════════════════════════════════
# تب ۲ — کاربر جدید
# ══════════════════════════════════════════════
with tab_new:
    st.markdown("<div class='sec-t'>➕ ثبت کاربر / ویزیتور جدید</div>"
                "<div class='sec-s'>پس از ثبت، کاربر با همین نام کاربری و رمز وارد اپ موبایل می‌شود.</div>",
                unsafe_allow_html=True)
    ver = st.session_state.setdefault("new_user_ver", 0)
    _vrows, _verr = vaseteh_list()
    pick = st.selectbox("🔗 انتخاب ویزیتور از نرم‌افزار فروش (اختیاری)", [""] + [x["code"] for x in _vrows],
                        format_func=lambda c: "— بدون واسطه / ورود دستی —" if not c else vaseteh_label(c),
                        key=f"nu_pick_{ver}",
                        help="نام از نرم‌افزار فروش پر می‌شود و کاربر فقط مشتریان همین واسطه را در اپ می‌بیند.")
    if _verr:
        st.caption(f"⚠️ فهرست واسطه‌ها خوانده نشد: {_verr} — تب تنظیمات ← «واسطه / ویزیتور».")
    _pname = next((x["name"] for x in _vrows if x["code"] == pick), "")
    with st.form(f"new_user_{ver}_{pick}"):
        n1, n2 = st.columns(2)
        n_full = n1.text_input("👤 نام و نام خانوادگی *", value=_pname, placeholder="مثال: علی محمدی")
        n_user = n1.text_input("🔑 نام کاربری *", placeholder="ali.m",
                               help="فقط حروف انگلیسی، عدد و . _ - (۳ تا ۵۰ کاراکتر)")
        n_phone = n1.text_input("📱 شماره موبایل", placeholder="09121234567")
        n_pass = n2.text_input("🔒 رمز عبور *", type="password", placeholder=f"حداقل {PW_MIN} کاراکتر")
        n_pass2 = n2.text_input("🔒 تکرار رمز عبور *", type="password")
        n_role = n2.selectbox("🛡️ نقش", ["visitor", "admin"],
                              format_func=lambda x: "🧭 ویزیتور" if x == "visitor" else "🛡️ مدیر سیستم")
        n_vas = vaseteh_picker(st, [pick] if pick else [], f"nu_vas_{ver}_{pick}")
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
                           (username,password_hash,full_name,role,phone,notes,is_active,sales_codes)
                           VALUES (?,?,?,?,?,?,1,?)""",
                        (uname, hash_password(n_pass), n_full.strip(), n_role,
                         n_phone.strip() or None, n_notes.strip() or None, V.dump_codes(n_vas)))
                st.session_state["new_user_ver"] = ver + 1
                flash(f"✅ کاربر «{n_full.strip()}» با نام کاربری @{uname} ثبت شد.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطا: {e}")


def norm_fa(v) -> str:
    """یکسان‌سازی حروف و ارقام برای جستجو: ي/ى→ی، ك→ک، ارقام فارسی/عربی→انگلیسی"""
    s = str(v or "").replace("ي", "ی").replace("ى", "ی").replace("ك", "ک").replace("ة", "ه")
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    return " ".join(s.replace("\u200c", " ").lower().split())


@st.cache_data(ttl=120, show_spinner="در حال خواندن مشتریان دیتابیس فروش...")
def sales_customers():
    """[(کد، نام، متن جستجو)] همهٔ مشتریان دیتابیس فروش — جدیدترین کدها اول"""
    conn = get_conn(SALES_DB); cur = conn.cursor()
    cur.execute("SELECT CAST(C_Code AS NVARCHAR(50)), CAST(C_Name AS NVARCHAR(200)) FROM customer")
    rows = []
    for code, name in cur.fetchall():
        code = (code or "").strip()
        name = (name or "").strip().replace("ي", "ی").replace("ك", "ک")
        if code:
            rows.append((code, name, norm_fa(f"{name} {code}")))
    cur.close(); conn.close()
    rows.sort(key=lambda r: (len(r[0]), r[0]), reverse=True)
    return rows


# ══════════════════════════════════════════════
# تب — مشتریان جدیدِ ثبت‌شده در اپ (فقط در tracking)
# ══════════════════════════════════════════════
NC_STATUS = {"new": "🆕 جدید — بررسی نشده", "done": "✅ در نرم‌افزار فروش تعریف شد", "rejected": "⛔ رد شده (در اپ نمی‌آید)"}

with tab_nc:
    st.markdown("<div class='sec-s'>مشتریانی که ویزیتورها در اپ ثبت کرده‌اند. این مشتری‌ها فقط در دیتابیس پیچا ویزیت هستند "
                "و در نرم‌افزار فروش ثبت نشده‌اند؛ ویزیت و سفارش آن‌ها با کد موقت (شروع با N) ذخیره می‌شود. "
                "بعد از تعریف در نرم‌افزار فروش، کد آن‌جا را این‌جا وارد کنید.</div>", unsafe_allow_html=True)
    try:
        conn = get_conn()
        ncs = pd.read_sql("""
            SELECT n.id, n.code, n.name, ISNULL(n.contact,'') AS contact, ISNULL(n.mobile,'') AS mobile,
                   ISNULL(n.phone,'') AS phone, ISNULL(n.city,'') AS city, ISNULL(n.address,'') AS address,
                   ISNULL(n.national_id,'') AS national_id, ISNULL(n.description,'') AS description,
                   n.latitude, n.longitude, n.status, ISNULL(n.sales_code,'') AS sales_code, n.created_at,
                   ISNULL(u.full_name, N'نامشخص') AS visitor,
                   (SELECT COUNT(*) FROM orders o WHERE o.customer_code = n.code) AS n_orders,
                   (SELECT ISNULL(SUM(o.total_amount),0) FROM orders o WHERE o.customer_code = n.code) AS s_orders,
                   (SELECT COUNT(*) FROM visits v WHERE v.customer_code = n.code) AS n_visits
            FROM new_customers n LEFT JOIN visitors u ON u.id = n.visitor_id
            ORDER BY n.id DESC""", conn)
        conn.close()
    except Exception as e:
        ncs = None
        st.error(f"❌ خواندن مشتریان جدید ممکن نشد: {e}")
    if ncs is not None and ncs.empty:
        st.info("هنوز مشتری جدیدی از اپ ثبت نشده است. ویزیتور در اپ از دکمهٔ «➕ مشتری جدید» کنار انتخاب مشتری استفاده می‌کند.")
    elif ncs is not None:
        f1, f2 = st.columns([1, 2])
        f_st = f1.selectbox("وضعیت", ["همه"] + list(NC_STATUS), format_func=lambda s: s if s == "همه" else NC_STATUS[s],
                            key="nc_f_status")
        f_q = f2.text_input("جستجو", placeholder="نام، موبایل، کد یا ویزیتور", key="nc_f_q")
        view = ncs if f_st == "همه" else ncs[ncs["status"] == f_st]
        if f_q.strip():
            q = f_q.strip()
            view = view[view.apply(lambda r: any(q in str(r[c]) for c in ("name", "mobile", "phone", "code", "visitor", "contact")), axis=1)]
        table = pd.DataFrame({
            "کد موقت": view["code"], "نام مشتری": view["name"], "مسئول": view["contact"], "موبایل": view["mobile"],
            "تلفن": view["phone"], "شهر": view["city"], "آدرس": view["address"], "ثبت توسط": view["visitor"],
            "تاریخ ثبت": view["created_at"].apply(to_jalali),
            "ویزیت": view["n_visits"], "سفارش": view["n_orders"], "جمع سفارش (ریال)": view["s_orders"].map(lambda v: f"{v:,.0f}"),
            "وضعیت": view["status"].map(lambda s: NC_STATUS.get(s, s)), "کد در نرم‌افزار فروش": view["sales_code"],
        })
        st.dataframe(table[table.columns[::-1]], hide_index=True, width="stretch", height=min(460, 38 + 35 * len(table)))
        buf = io.BytesIO()
        table.to_excel(buf, index=False, sheet_name="New customers")
        st.download_button("📥 Excel مشتریان جدید", buf.getvalue(), file_name="PeechaVisit_New_Customers.xlsx")

        st.markdown("<div class='sec-t' style='margin-top:12px'>✏️ بررسی و ویرایش</div>", unsafe_allow_html=True)
        pick = st.selectbox("مشتری", list(view["id"]), key="nc_pick",
                            format_func=lambda i: (lambda r: f"{r['name']} — {r['code']} — {r['visitor']}")(view[view['id'] == i].iloc[0]))
        if pick is not None:
            r = view[view["id"] == pick].iloc[0]
            # ── اتصال به مشتری تعریف‌شده در نرم‌افزار فروش + انتقال سوابق ──
            with st.container(border=True):
                st.markdown("<div class='sec-t'>🔗 اتصال به مشتری دیتابیس فروش</div>"
                            "<div class='sec-s'>وقتی واحد مالی این مشتری را در نرم‌افزار فروش تعریف کرد، او را این‌جا پیدا کنید. "
                            "همهٔ ویزیت‌ها، سفارش‌ها و دریافت‌هایی که با کد موقت ثبت شده‌اند به کد فروش منتقل می‌شوند و "
                            "از این به بعد هر ثبت با کد موقت (حتی از گوشی آفلاین) خودکار به همان کد فروش می‌رود.</div>",
                            unsafe_allow_html=True)
                lq = st.text_input("جستجو در مشتریان فروش (نام یا کد)", value="", key=f"nc_lq_{pick}",
                                   placeholder="خالی = آخرین مشتریان تعریف‌شده")
                cands = []
                try:
                    allc = sales_customers()
                    q = norm_fa(lq)
                    if q:
                        words = q.split()
                        cands = [c for c in allc if all(w in c[2] for w in words)][:100]
                    else:
                        cands = allc[:50]          # جدیدترین کدها اول
                except Exception as e:
                    st.error(f"❌ خواندن مشتریان دیتابیس فروش ممکن نشد: {e}")
                cands = [(c[0], c[1]) for c in cands]
                st.caption(f"{len(cands)} مشتری" + (" (جدیدترین‌ها)" if not lq.strip() else ""))
                if cands:
                    target = st.selectbox("مشتری متناظر در نرم‌افزار فروش", cands, key=f"nc_target_{pick}",
                                          format_func=lambda c: f"{c[1]} — کد {c[0]}")
                    if st.button(f"🔗 اتصال «{r['name']}» به کد {target[0]} و انتقال سوابق", type="primary",
                                 key=f"nc_link_{pick}"):
                        if len(target[0]) > 10:
                            st.error("کد فروش بیشتر از ۱۰ کاراکتر است و در ستون کد مشتری جا نمی‌شود.")
                        else:
                            conn = get_conn(); cur = conn.cursor()
                            moved = {}
                            for tbl in ("visits", "orders", "payments"):
                                cur.execute(f"UPDATE {tbl} SET customer_code=? WHERE customer_code=?", (target[0], r["code"]))
                                moved[tbl] = cur.rowcount
                            cur.execute("UPDATE new_customers SET status='done', sales_code=? WHERE id=?", (target[0], int(pick)))
                            conn.commit(); cur.close(); conn.close()
                            flash(f"✅ «{r['name']}» به مشتری «{target[1]}» (کد {target[0]}) وصل شد — منتقل‌شده: "
                                  f"{moved['visits']} ویزیت، {moved['orders']} سفارش، {moved['payments']} دریافت.")
                            st.rerun()
                elif lq.strip():
                    st.caption("مشتری‌ای با این نام یا کد در دیتابیس فروش پیدا نشد (بخشی از نام یا کد را امتحان کنید).")
            if r["latitude"] and r["longitude"]:
                st.markdown(f"📍 [موقعیت روی نقشه](https://www.google.com/maps?q={r['latitude']},{r['longitude']})")
            with st.form(f"nc_form_{pick}"):
                c1, c2 = st.columns(2)
                e_name = c1.text_input("نام مشتری", r["name"])
                e_contact = c2.text_input("مسئول", r["contact"])
                e_mobile = c1.text_input("موبایل", r["mobile"])
                e_phone = c2.text_input("تلفن", r["phone"])
                e_city = c1.text_input("شهر", r["city"])
                e_nid = c2.text_input("کد/شناسهٔ ملی", r["national_id"])
                e_addr = st.text_area("آدرس", r["address"], height=70)
                e_desc = st.text_area("توضیحات", r["description"], height=70)
                c3, c4 = st.columns(2)
                e_status = c3.selectbox("وضعیت", list(NC_STATUS), index=list(NC_STATUS).index(r["status"]) if r["status"] in NC_STATUS else 0,
                                        format_func=lambda s: NC_STATUS[s])
                e_sales = c4.text_input("کد در نرم‌افزار فروش (بعد از تعریف)", r["sales_code"])
                ok_nc = st.form_submit_button("💾 ذخیره", type="primary")
            if ok_nc:
                if not e_name.strip():
                    st.error("نام مشتری خالی است.")
                elif len(e_sales.strip()) > 10:
                    st.error("کد فروش بیشتر از ۱۰ کاراکتر است و در ستون کد مشتری جا نمی‌شود.")
                else:
                    run_sql("""UPDATE new_customers SET name=?, contact=?, mobile=?, phone=?, city=?, national_id=?,
                               address=?, description=?, status=?, sales_code=? WHERE id=?""",
                            (e_name.strip()[:200], e_contact.strip()[:100] or None, e_mobile.strip()[:40] or None,
                             e_phone.strip()[:40] or None, e_city.strip()[:60] or None, e_nid.strip()[:20] or None,
                             e_addr.strip()[:400] or None, e_desc.strip()[:400] or None, e_status,
                             e_sales.strip()[:50] or None, int(pick)))
                    note = ""
                    if e_status == "done" and e_sales.strip():
                        # همان کار «اتصال»: سوابق کد موقت به کد فروش منتقل می‌شود
                        conn = get_conn(); cur = conn.cursor(); moved = 0
                        for tbl in ("visits", "orders", "payments"):
                            cur.execute(f"UPDATE {tbl} SET customer_code=? WHERE customer_code=?",
                                        (e_sales.strip()[:10], r["code"]))
                            moved += cur.rowcount
                        conn.commit(); cur.close(); conn.close()
                        note = f" {moved} ثبت به کد {e_sales.strip()} منتقل شد."
                    flash(f"✅ اطلاعات «{e_name.strip()}» ذخیره شد.{note}")
                    st.rerun()


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
    live = ("MOBILE", "GPS", "CATALOG", "VASETEH")     # این‌ها بدون ری‌استارت اعمال می‌شوند
    loaded = {s: getattr(config, s) for s in DEFAULTS if s not in live}
    if {s: v for s, v in cur_cfg.items() if s not in live} != loaded:
        if os.environ.get("PEECHA_PARENT"):
            st.info("🔄 تنظیمات تازه ذخیره شده است؛ سرویس‌ها ظرف چند ثانیه خودکار دوباره شروع می‌شوند "
                    "و این صفحه دوباره وصل می‌شود.")
        else:
            st.warning("⚠️ تنظیمات ذخیره‌شده با تنظیمات در حال اجرا فرق دارد. "
                       "برای اعمال، پنجرهٔ سرویس‌ها را ببندید و start.bat را دوباره اجرا کنید.")
    if SECURITY["SESSION_SECRET"] == INSECURE_SECRET:
        st.error("🔑 کلید امنیتی توکن‌ها هنوز مقدار پیش‌فرض است و هر کسی کد را دارد می‌تواند توکن جعل کند. "
                 "پایین همین صفحه «ساخت کلید جدید» را بزنید.")

    # ── اپ موبایل (بدون ری‌استارت) ──
    M = cur_cfg.get("MOBILE")
    if M is None:
        st.error("⚠️ فایل config.py قدیمی است یا پنل بعد از به‌روزرسانی ری‌استارت نشده. "
                 "همهٔ پنجره‌های سیاه را ببندید و start.bat را دوباره اجرا کنید. اگر باز هم این پیام را دیدید، "
                 "config.py را از نسخهٔ جدید جایگزین کنید (نام SQL Server و IP را می‌توانید همین‌جا در تنظیمات وارد کنید).")
    else:
        with st.form("mobile_form"):
            st.markdown("<div class='sec-t'>📱 اپ موبایل ویزیتورها</div>"
                        "<div class='sec-s'>بلافاصله اعمال می‌شود؛ روی گوشی با دکمهٔ «همگام‌سازی» یا باز کردن دوبارهٔ اپ.</div>",
                        unsafe_allow_html=True)
            m_cols = st.columns(2)
            m_vals = {}
            for i, (k, label) in enumerate(MOBILE_LABELS.items()):
                m_vals[k] = m_cols[i % 2].toggle(label, value=bool(M.get(k)))
            G = cur_cfg.get("GPS") or {}
            g1, g2 = st.columns(2)
            g_acc = g1.number_input("📍 دقت مطلوب موقعیت (متر)", 5, 500, int(G.get("MAX_ACCURACY_METERS", 30)),
                                    help="اپ تا رسیدن به این دقت منتظر GPS می‌ماند؛ اگر نرسید از ویزیتور می‌پرسد.")
            g_time = g2.number_input("⏱️ حداکثر زمان انتظار برای GPS (ثانیه)", 5, 120, int(G.get("TIMEOUT_SECONDS", 25)))
            st.caption("برای تنظیم جداگانه برای یک ویزیتور: تب «کاربران» ← «ویرایش و عملیات» آن کاربر.")
            save_mobile = st.form_submit_button("💾 ذخیرهٔ تنظیمات اپ موبایل", type="primary")
        if save_mobile:
            config.save_settings({"MOBILE": m_vals,
                                  "GPS": {"MAX_ACCURACY_METERS": g_acc, "TIMEOUT_SECONDS": g_time}})
            flash("✅ تنظیمات اپ موبایل ذخیره شد و از همین حالا اعمال می‌شود.")
            st.rerun()

        # ── عکس کالا و کاتالوگ (بدون ری‌استارت) ──
        with st.container(border=True):
            st.markdown("<div class='sec-t'>📚 عکس کالا و کاتالوگ اپ</div>"
                        "<div class='sec-s'>عکس‌ها از جدول عکس‌های نرم‌افزار فروش (مثل HLOpicturs) خوانده می‌شوند: "
                        "یا از <b>مسیر فایل</b> (ستون PicturePath) یا <b>داخل دیتابیس</b> (ستون Picture). "
                        "اگر آن جدول نباشد، از ستونی در جدول article.</div>", unsafe_allow_html=True)
            C = cur_cfg.get("CATALOG") or {}
            try:
                import catalog as _cat
                src_now = _cat.source_text()
            except Exception as e:
                src_now = f"❌ {e}"
            st.caption(f"منبع فعلی: {src_now}")
            MODES = {"path": "مسیر فایل (PicturePath)", "db": "داخل دیتابیس (Picture)", "auto": "خودکار: مسیر، وگرنه دیتابیس"}
            with st.form("catalog_form"):
                k1, k2, k3 = st.columns([1.2, 1.4, 1])
                c_tbl = k1.text_input("جدول عکس‌ها", C.get("IMAGE_TABLE") or "",
                                      help="خالی = استفاده از ستونی در جدول article")
                c_mode = k2.radio("روش ذخیرهٔ عکس", list(MODES), format_func=MODES.get, horizontal=False,
                                  index=list(MODES).index(C.get("IMAGE_MODE") or "auto") if (C.get("IMAGE_MODE") or "auto") in MODES else 2)
                c_type = k3.text_input("Type عکس کالا", C.get("IMAGE_TYPE") if C.get("IMAGE_TYPE") is not None else "1",
                                       help="۱ = عکس کالا؛ خالی = همهٔ ردیف‌ها")
                c_ctype = k3.text_input("Type عکس مشتری", C.get("CUSTOMER_TYPE") if C.get("CUSTOMER_TYPE") is not None else "2",
                                        help="۲ = عکس طرف حساب (پروفایل مشتری در اپ و داشبورد)")
                k4, k5, k6 = st.columns(3)
                c_code = k4.text_input("ستون کد کالا", C.get("IMAGE_CODE_COL") or "Code")
                c_path = k5.text_input("ستون مسیر", C.get("IMAGE_PATH_COL") or "PicturePath")
                c_blob = k6.text_input("ستون عکس (داخل دیتابیس)", C.get("IMAGE_BLOB_COL") or "Picture")
                c_dir = st.text_input("پوشهٔ عکس‌ها (فقط اگر مسیرها نسبی یا فقط نام فایل هستند)", C.get("IMAGE_DIR") or "",
                                      placeholder=r"D:\Images یا \\SERVER\Images")
                c_col = st.text_input("حالت ستون article: نام ستون (خالی = تشخیص خودکار)", C.get("IMAGE_COLUMN") or "")
                k7, k8 = st.columns([2, 1])
                c_test = k7.text_input("آزمون: کد یک کالا", placeholder="مثلاً 0701001")
                c_ctest = k7.text_input("آزمون: کد یک مشتری", placeholder="مثلاً 00003")
                save_cat = k8.form_submit_button("💾 ذخیره و آزمون", type="primary")
            if save_cat:
                config.save_settings({"CATALOG": {
                    "IMAGE_TABLE": c_tbl.strip(), "IMAGE_MODE": c_mode, "IMAGE_TYPE": c_type.strip(),
                    "CUSTOMER_TYPE": c_ctype.strip(),
                    "IMAGE_CODE_COL": c_code.strip(), "IMAGE_PATH_COL": c_path.strip(), "IMAGE_BLOB_COL": c_blob.strip(),
                    "IMAGE_DIR": c_dir.strip(), "IMAGE_COLUMN": c_col.strip()}})
                try:
                    import catalog as _cat
                    st.caption(f"منبع: {_cat.source_text()} · کالاهای دارای عکس: {len(_cat.has_image_values('article'))}"
                               f" · مشتریان دارای عکس: {len(_cat.has_image_values('customer'))}")
                    if c_ctest.strip():
                        for line in _cat.diagnose(c_ctest.strip(), "customer"):
                            st.caption(line)
                        cimg = _cat.thumbnail(c_ctest.strip(), 300, "customer")
                        if cimg:
                            st.image(cimg, caption=f"عکس مشتری {c_ctest.strip()}", width=160)
                        else:
                            st.warning("برای این مشتری عکسی پیدا نشد.")
                    if c_test.strip():
                        for line in _cat.diagnose(c_test.strip()):
                            st.caption(line)
                        img = _cat.thumbnail(c_test.strip(), 300)
                        if img:
                            st.image(img, caption=f"عکس کالای {c_test.strip()}", width=220)
                        else:
                            st.warning("برای این کالا عکسی پیدا نشد (ردیفی در جدول عکس نیست، مقدار خالی است یا فایل در مسیر نیست). "
                                       "سرویس ویندوز با حساب SYSTEM اجرا می‌شود؛ برای پوشهٔ شبکه دسترسی آن را بررسی کنید.")
                except Exception as e:
                    st.error(f"❌ {e}")
                st.success("✅ تنظیمات کاتالوگ ذخیره شد (بدون ری‌استارت؛ در اپ با «همگام‌سازی»).")

        # ── واسطه / ویزیتور نرم‌افزار فروش (بدون ری‌استارت) ──
        with st.container(border=True):
            st.markdown("<div class='sec-t'>🔗 واسطه / ویزیتور نرم‌افزار فروش</div>"
                        "<div class='sec-s'>ویزیتور در جدول customer با <b>Vaseteh = True</b> تعریف می‌شود و مشتریانش در جدول "
                        "<b>CustomerVaseteh</b> هستند. به هر کاربر (تب کاربران) یک یا چند واسطه بدهید تا در اپ فقط "
                        "مشتریان خودش را ببیند.</div>", unsafe_allow_html=True)
            VS = cur_cfg.get("VASETEH") or {}
            NO_CODE = {"all": "همهٔ مشتریان را ببیند", "none": "هیچ مشتری‌ای نبیند"}
            with st.form("vaseteh_form"):
                v_on = st.toggle("فقط مشتریان واسطهٔ هر کاربر در اپ نمایش داده شود", value=bool(VS.get("ENABLED", True)))
                v1, v2, v3, v4 = st.columns(4)
                v_tbl = v1.text_input("جدول مشتری ← واسطه", VS.get("TABLE") or "CustomerVaseteh")
                v_cc = v2.text_input("ستون کد مشتری", VS.get("CUST_COL") or "C_Code")
                v_vc = v3.text_input("ستون کد واسطه", VS.get("VASETEH_COL") or "Vaseteh_Code")
                v_flag = v4.text_input("ستون واسطه در customer", VS.get("FLAG_COL") or "Vaseteh")
                v_none = st.radio("کاربری که واسطه ندارد", list(NO_CODE), format_func=NO_CODE.get, horizontal=True,
                                  index=1 if VS.get("NO_CODE") == "none" else 0)
                save_vas = st.form_submit_button("💾 ذخیره و آزمون", type="primary")
            if save_vas:
                config.save_settings({"VASETEH": {
                    "ENABLED": v_on, "TABLE": v_tbl.strip(), "CUST_COL": v_cc.strip(),
                    "VASETEH_COL": v_vc.strip(), "FLAG_COL": v_flag.strip(), "NO_CODE": v_none}})
                vaseteh_list.clear()
                rows, err = vaseteh_list()
                if err:
                    st.error(f"❌ {err}")
                else:
                    st.success(f"✅ ذخیره شد · {len(rows)} واسطه پیدا شد (بدون ری‌استارت؛ در اپ با «همگام‌سازی»).")
                    if rows:
                        st.dataframe(pd.DataFrame([{"کد": r["code"], "نام": r["name"], "تعداد مشتری": r["customers"]}
                                                   for r in rows]), hide_index=True, width="stretch")

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

        save = st.form_submit_button("💾 ذخیرهٔ تنظیمات", type="primary", width="stretch")

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
            flash(RESTART_NOTE("✅ تنظیمات ذخیره شد. برای اعمال، سرویس‌ها را ری‌استارت کنید."))
            st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    k1, k2 = st.columns(2)
    with k1:
        with st.container(border=True):
            st.markdown("<div class='sec-t'>🔑 کلید امنیتی توکن‌ها</div>"
                        "<div class='sec-s'>با ساخت کلید جدید، همهٔ ویزیتورها باید دوباره وارد اپ شوند.</div>",
                        unsafe_allow_html=True)
            if st.button("🔑 ساخت کلید جدید", width="stretch"):
                config.save_settings({"SECURITY": {"SESSION_SECRET": secrets.token_hex(32)}})
                flash(RESTART_NOTE("✅ کلید جدید ساخته شد. app.py را ری‌استارت کنید."))
                st.rerun()
    with k2:
        with st.container(border=True):
            overrides = config.read_settings_file()
            st.markdown("<div class='sec-t'>↩️ بازگشت به پیش‌فرض</div>"
                        f"<div class='sec-s'>{sum(len(v) for v in overrides.values())} مقدار سفارشی در "
                        f"<code>settings.json</code></div>", unsafe_allow_html=True)
            with st.popover("حذف همهٔ تنظیمات سفارشی", width="stretch", disabled=not overrides):
                st.write("همهٔ مقادیر به config.py برمی‌گردند (کلید امنیتی هم).")
                if st.button("بله، بازگردانی شود", type="primary"):
                    config.reset_settings()
                    flash(RESTART_NOTE("✅ تنظیمات به پیش‌فرض برگشت. سرویس‌ها را ری‌استارت کنید."))
                    st.rerun()


# ══════════════════════════════════════════════
# تب ۴ — وضعیت سیستم
# ══════════════════════════════════════════════
def api_info() -> dict | None:
    """مشخصات API در حال اجرا روی پورت موبایل (نسخه‌های قدیمی این مسیر را ندارند → None)"""
    try:
        import json as _json
        port = config.NETWORK["FLASK_PORT"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/server-info", timeout=2) as r:
            d = _json.loads(r.read().decode("utf-8"))
            return d if d.get("version") else None
    except Exception:
        return None


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

        # API روی پورت موبایل واقعاً کدام نسخه است و با چه تنظیماتی کار می‌کند؟
        info = api_info() if alive else None
        cur_db = config.current_settings()["DATABASES"]
        if alive and not info:
            st.error("⚠️ روی پورت API یک سرور **قدیمی** پیچا ویزیت در حال اجراست (این نسخه نیست). "
                     "احتمالاً هم نسخهٔ نصبی و هم start.bat قدیمی هم‌زمان اجرا شده‌اند و گوشی‌ها به نسخهٔ قدیمی وصل‌اند. "
                     "پنجره‌های قدیمی «PeechaVisit» را ببندید (یا کامپیوتر را ری‌استارت کنید).")
        elif info:
            same_file = os.path.normcase(str(info.get("settings_file"))) == os.path.normcase(SETTINGS_FILE)
            same_db = (info.get("tracking_db"), info.get("sales_db")) == (cur_db["TRACKING_DB"], cur_db["SALES_DB"])
            st.markdown(f"<div class='sec-s'>API پاسخ‌دهنده: نسخهٔ {info.get('version')} · دیتابیس فروش "
                        f"<b>{info.get('sales_db')}</b> · ردیابی <b>{info.get('tracking_db')}</b> · "
                        f"اجرا از {info.get('started')}</div>", unsafe_allow_html=True)
            if not same_file:
                st.error(f"⚠️ API موبایل از فایل تنظیمات دیگری استفاده می‌کند ({info.get('settings_file')})؛ "
                         "یعنی یک نسخهٔ دیگر پیچا ویزیت (مثلاً start.bat قدیمی کنار نسخهٔ نصبی) پورت API را گرفته است. "
                         "فقط یکی از آن‌ها را اجرا کنید.")
            elif not same_db:
                st.warning(f"⚠️ API هنوز با دیتابیس قبلی کار می‌کند (فروش: {info.get('sales_db')}، در تنظیمات: "
                           f"{cur_db['SALES_DB']}). دکمهٔ «ری‌استارت سرویس‌ها» را بزنید.")
        if os.environ.get("PEECHA_PARENT"):
            if st.button("🔄 ری‌استارت همهٔ سرویس‌ها", width="stretch",
                         help="API، داشبورد، وب‌اپ و همین پنل دوباره اجرا می‌شوند تا تنظیمات تازه اعمال شود."):
                try:
                    from peecha_server import request_restart
                    request_restart()
                    st.success("✅ درخواست ثبت شد؛ سرویس‌ها ظرف چند ثانیه دوباره اجرا می‌شوند و این صفحه دوباره وصل می‌شود.")
                except Exception as e:
                    st.error(f"❌ ری‌استارت ممکن نشد: {e}")

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
        if st.button("🔄 تست دوباره", width="stretch"):
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("ℹ️ تنظیمات در حال اجرا"):
        for title, sec in [("شبکه", "NETWORK"), ("دیتابیس", "DATABASES"), ("امنیت", "SECURITY"), ("برنامه", "APP")]:
            rows = "".join(
                f"<tr><td>{k}</td><td>{'••••••' if any(x in k for x in ('SECRET', 'PASSWORD')) and v else v}</td></tr>"
                for k, v in getattr(config, sec).items())
            st.markdown(f"<b>{title}</b><table class='cfg-tbl'>{rows}</table><br>", unsafe_allow_html=True)
        st.caption(f"فایل تنظیمات: {SETTINGS_FILE}")
