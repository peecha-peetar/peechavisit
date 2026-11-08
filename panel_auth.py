# panel_auth.py - پیچا ویزیت | ورود مدیر برای داشبورد و پنل مدیریت
# ════════════════════════════════════════════════
# require_admin() را بعد از st.set_page_config صدا بزنید؛
# تا مدیر وارد نشود صفحهٔ ورود نمایش داده و اجرای صفحه متوقف می‌شود.
# ════════════════════════════════════════════════
import time
import streamlit as st
from config import APP, SECURITY
from auth import verify_login

_KEY = "pv_admin"

_LOGIN_CSS = """
<style>
.pv-login-card{background:#fff;border-radius:22px;padding:34px 30px 18px;
  box-shadow:0 18px 50px rgba(2,0,37,.12);border:1px solid #e6e9f5;
  text-align:center;direction:rtl;margin-top:6vh}
.pv-login-card .ic{font-size:44px;margin-bottom:8px}
.pv-login-card .t{font-size:20px;font-weight:900;color:%(c1)s}
.pv-login-card .s{font-size:12px;color:#94a3b8;margin-top:4px}
</style>
"""


def current_admin() -> dict | None:
    info = st.session_state.get(_KEY)
    if not info:
        return None
    # انقضای نشست بعد از SESSION_HOURS
    if time.time() - info["at"] > float(SECURITY["SESSION_HOURS"]) * 3600:
        st.session_state.pop(_KEY, None)
        return None
    return info


def require_admin(title: str, icon: str = "🔐") -> dict:
    admin = current_admin()
    if admin:
        return admin

    st.markdown(_LOGIN_CSS % {"c1": APP["PRIMARY_COLOR"]}, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.markdown(f"""
        <div class='pv-login-card'>
            <div class='ic'>{icon}</div>
            <div class='t'>{title}</div>
            <div class='s'>{APP["NAME"]} — ورود ویژهٔ مدیر سیستم</div>
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
                    res = verify_login(u, p, require_role="admin")
                except Exception as e:
                    st.error(f"❌ خطای اتصال به دیتابیس: {e}")
                    st.stop()
                if res["ok"]:
                    st.session_state[_KEY] = {**res["user"], "at": time.time()}
                    st.rerun()
                st.error(res["error"])
    st.stop()


def logout() -> None:
    st.session_state.pop(_KEY, None)
    st.rerun()
