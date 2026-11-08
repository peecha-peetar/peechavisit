# panel_auth.py - پیچا ویزیت | ورود به پنل مدیریت و داشبورد
# ════════════════════════════════════════════════
# require_admin()     : فقط مدیر (پنل مدیریت)
# require_dashboard() : مدیر یا کاربری که در پنل مدیریت دسترسی داشبورد گرفته
# بعد از st.set_page_config صدا بزنید؛ تا ورود انجام نشود، اجرای صفحه متوقف می‌شود.
# ════════════════════════════════════════════════
import time
import streamlit as st
from config import APP, SECURITY
from auth import verify_login
from db import get_conn
import perms as P
import audit


def _log(source, event, user=None, username=None, detail=None):
    try:
        ip = getattr(st.context, "ip_address", None)
        ua = (st.context.headers or {}).get("User-Agent", "")[:200]
    except Exception:
        ip, ua = None, ""
    audit.log_event(source, event, (user or {}).get("id"), (user or {}).get("username") or username, ip, ua, detail)

_KEY = "pv_admin"

_LOGIN_CSS = """
<style>
.pv-login-card{background:#fff;border-radius:16px;padding:30px 26px 16px;
  border:1px solid #dfe3ea;text-align:center;direction:rtl;margin-top:8vh}
.pv-login-card .ic{font-size:40px;margin-bottom:6px}
.pv-login-card .t{font-size:20px;font-weight:800;color:%(c1)s}
.pv-login-card .s{font-size:12px;color:#6b7686;margin-top:4px}
</style>
"""


def _user_row(uid: int):
    """نقش، فعال بودن و دسترسی داشبورد کاربر (تازه از دیتابیس)"""
    conn = get_conn(); cur = conn.cursor()
    try:
        try:
            cur.execute("SELECT ISNULL(role,'visitor'), is_active, dash_perms FROM visitors WHERE id=?", (uid,))
        except Exception:   # ستون dash_perms هنوز ساخته نشده
            cur.execute("SELECT ISNULL(role,'visitor'), is_active, NULL FROM visitors WHERE id=?", (uid,))
        return cur.fetchone()
    finally:
        cur.close(); conn.close()


def current_admin() -> dict | None:
    info = st.session_state.get(_KEY)
    if not info:
        return None
    # انقضای نشست بعد از SESSION_HOURS
    if time.time() - info["at"] > float(SECURITY["SESSION_HOURS"]) * 3600:
        st.session_state.pop(_KEY, None)
        return None
    return info


def _login_form(title, icon, subtitle, check, source):
    st.markdown(_LOGIN_CSS % {"c1": APP["PRIMARY_COLOR"]}, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.markdown(f"""
        <div class='pv-login-card'>
            <div class='ic'>{icon}</div>
            <div class='t'>{title}</div>
            <div class='s'>{APP["NAME"]} — {subtitle}</div>
        </div>""", unsafe_allow_html=True)
        with st.form("pv_admin_login", clear_on_submit=False):
            u = st.text_input("👤 نام کاربری", placeholder="admin")
            p = st.text_input("🔒 رمز عبور", type="password")
            ok = st.form_submit_button("ورود", type="primary", use_container_width=True)
        if ok:
            if not u or not p:
                st.error("نام کاربری و رمز الزامی است.")
            else:
                try:
                    res = verify_login(u, p)
                    err = check(res["user"]) if res["ok"] else res["error"]
                except Exception as e:
                    st.error(f"❌ خطای اتصال به دیتابیس: {e}")
                    st.stop()
                if not err:
                    st.session_state[_KEY] = {**res["user"], "at": time.time()}
                    _log(source, "login", res["user"])
                    st.rerun()
                _log(source, "login_failed", username=u, detail=err)
                st.error(err)
    st.stop()


def require_admin(title: str, icon: str = "🔐") -> dict:
    admin = current_admin()
    if admin and admin.get("role") == "admin":
        return admin
    _login_form(title, icon, "ورود ویژهٔ مدیر سیستم",
                lambda u: None if u["role"] == "admin" else "این حساب دسترسی مدیر ندارد", "admin")


def require_dashboard(title: str, icon: str = "📊") -> dict:
    """کاربر واردشده + دسترسی‌هایش در user['perms']"""
    def check(u):
        row = _user_row(u["id"])
        if not row:
            return "حساب پیدا نشد"
        p = P.effective(row[0], row[2])
        return None if p["access"] else "این حساب دسترسی داشبورد ندارد. از مدیر سیستم بخواهید."

    user = current_admin()
    if user:
        row = _user_row(user["id"])          # تغییر دسترسی‌ها بدون خروج و ورود اعمال شود
        if row and row[1]:
            p = P.effective(row[0], row[2])
            if p["access"]:
                return {**user, "role": row[0], "perms": p}
        st.session_state.pop(_KEY, None)
    _login_form(title, icon, "ورود به داشبورد", check, "dashboard")


def logout() -> None:
    st.session_state.pop(_KEY, None)
    st.rerun()
