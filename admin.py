# admin.py - پیچا ویزیت | پنل مدیریت v3.0
import streamlit as st
import pyodbc
import hashlib
import pandas as pd
from datetime import datetime

# ── بارگذاری از config ──
try:
    from config import NETWORK, DATABASES, APP
    SERVER = NETWORK["SERVER_NAME"]
    DB     = DATABASES["TRACKING_DB"]
    C1     = APP["PRIMARY_COLOR"]
except ImportError:
    SERVER = "SERWIN\\RAD"  # fallback: config.py را ویرایش کنید
    DB     = "tracking"
    C1     = "#020025"
C2      = "#3949ab"

st.set_page_config(
    page_title="مدیریت | پیچا ویزیت",
    page_icon="👥",
    layout="wide"
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800;900&display=swap');

/* ── فونت و جهت سراسری ── */
html, body, * {{
    font-family: 'Vazirmatn', Tahoma, sans-serif !important;
}}
.stApp {{
    background: #eef1fb !important;
    direction: rtl !important;
}}
.block-container {{
    padding: 22px 30px !important;
    max-width: 100% !important;
}}
/* ── تب‌ها ── */
.stTabs [data-baseweb="tab-list"] {{
    flex-direction: row-reverse !important;
    background: white !important;
    border-radius: 12px !important;
    padding: 5px !important;
    gap: 4px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,.07) !important;
    margin-bottom: 20px !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 9px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    color: #475569 !important;
    padding: 9px 20px !important;
}}
.stTabs [aria-selected="true"] {{
    background: linear-gradient(135deg, {C1}, {C2}) !important;
    color: white !important;
}}
/* ── label ── */
label, .stTextInput label, .stSelectbox label,
.stTextArea label, .stCheckbox label {{
    font-size: 12px !important;
    font-weight: 700 !important;
    color: {C1} !important;
    direction: rtl !important;
    display: block !important;
    margin-bottom: 4px !important;
}}
/* ── input / select / textarea ── */
.stTextInput input, .stTextArea textarea,
.stNumberInput input {{
    background: white !important;
    border: 2px solid #c8d0e0 !important;
    border-radius: 10px !important;
    color: #1e293b !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 10px 14px !important;
    direction: rtl !important;
    box-shadow: 0 1px 4px rgba(0,0,0,.06) !important;
    transition: border-color .2s, box-shadow .2s !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {C2} !important;
    box-shadow: 0 0 0 3px rgba(57,73,171,.15) !important;
    background: #fafcff !important;
}}
/* selectbox */
.stSelectbox [data-baseweb="select"] > div {{
    background: white !important;
    border: 2px solid #c8d0e0 !important;
    border-radius: 10px !important;
    color: #1e293b !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,.06) !important;
}}
.stSelectbox [data-baseweb="select"] > div:focus-within {{
    border-color: {C2} !important;
}}
/* ── checkbox ── */
.stCheckbox {{
    background: white !important;
    border: 2px solid #c8d0e0 !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
}}
/* ── دکمه‌ها ── */
.stButton > button {{
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 10px 18px !important;
    border: none !important;
    width: 100% !important;
    transition: all .2s !important;
}}
button[kind="primary"], .stButton > button[data-testid*="primary"] {{
    background: linear-gradient(135deg, {C1}, {C2}) !important;
    color: white !important;
    box-shadow: 0 4px 12px rgba(2,0,37,.25) !important;
}}
/* ── کارت کاربر ── */
.user-card {{
    background: white;
    border-radius: 14px;
    border: 1.5px solid #dde3f0;
    box-shadow: 0 2px 10px rgba(2,0,37,.06);
    margin-bottom: 12px;
    overflow: hidden;
}}
.user-card-head {{
    background: linear-gradient(135deg, #f8faff 0%, #f0f3ff 100%);
    border-bottom: 1.5px solid #dde3f0;
    padding: 13px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    direction: rtl;
    cursor: pointer;
}}
.user-card-head:hover {{ background: #eef1fb; }}
.u-name {{ font-size: 14px; font-weight: 800; color: {C1}; }}
.u-meta {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
.u-badges {{ display: flex; gap: 6px; align-items: center; }}
.badge {{
    display: inline-block; padding: 3px 10px;
    border-radius: 8px; font-size: 11px; font-weight: 700;
}}
.b-admin   {{ background: #ede9fe; color: #5b21b6; }}
.b-visitor {{ background: #dbeafe; color: #1e40af; }}
.b-active  {{ background: #d1fae5; color: #065f46; }}
.b-inactive{{ background: #fee2e2; color: #991b1b; }}
.b-locked  {{ background: #fff3e0; color: #e65100; }}
/* ── info grid ── */
.info-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    padding: 14px 18px;
    direction: rtl;
    border-bottom: 1px solid #f0f3fa;
}}
.info-cell {{ direction: rtl; }}
.info-cell .ic-lbl {{
    font-size: 10px; font-weight: 700; color: #94a3b8;
    text-transform: uppercase; margin-bottom: 3px;
}}
.info-cell .ic-val {{
    font-size: 13px; font-weight: 700; color: #1e293b;
    word-break: break-all;
}}
/* ── divider ── */
.sec-div {{
    font-size: 11px; font-weight: 800; color: #94a3b8;
    text-transform: uppercase; letter-spacing: .5px;
    padding: 10px 0 6px; border-top: 1px solid #f0f3fa;
    margin-top: 4px; direction: rtl;
}}
/* ── stat card ── */
.stat-card {{
    background: white; border-radius: 14px;
    padding: 18px 14px; text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,.06);
    border-top: 4px solid;
}}
/* ── cfg table ── */
.cfg-tbl {{ width:100%; border-collapse:collapse; direction:rtl; border-radius:10px; overflow:hidden; }}
.cfg-tbl th {{
    background: {C1}; color: white;
    padding: 10px 14px; text-align: right;
    font-size: 12px; font-weight: 700;
}}
.cfg-tbl td {{
    padding: 10px 14px; font-size: 13px;
    border-bottom: 1px solid #f0f2fa;
    direction: rtl;
}}
.cfg-tbl tr:hover td {{ background: #f8fafc; }}
.cfg-tbl .td-key {{ font-weight: 700; color: #475569; }}
.cfg-tbl .td-val {{ font-family: monospace; color: {C1}; }}
/* ── page header ── */
.pg-head {{
    background: white; border-radius: 15px;
    padding: 16px 22px; margin-bottom: 20px;
    box-shadow: 0 3px 16px rgba(2,0,37,.08);
    direction: rtl; display: flex;
    align-items: center; justify-content: space-between;
}}
/* مخفی keyboard tooltip */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[kind="header"] {{ display: none !important; }}
details > summary {{ list-style: none !important; }}
details > summary::marker,
details > summary::-webkit-details-marker {{ display: none !important; }}
span[aria-keyshortcuts], [class*="keyboard"],
[class*="KeyboardShortcut"] {{
    display: none !important; font-size: 0 !important;
}}
</style>
""", unsafe_allow_html=True)


# ══ توابع ══
def get_conn(autocommit=False):
    return pyodbc.connect(
        f'DRIVER={{SQL Server}};SERVER={SERVER};'
        f'DATABASE={DB};Trusted_Connection=yes;',
        autocommit=autocommit
    )

def hp(pw): return hashlib.sha256(pw.encode()).hexdigest()

def ensure_cols():
    cols = [
        ("role","VARCHAR(20) NOT NULL DEFAULT 'visitor'"),
        ("phone","VARCHAR(20) NULL"),("last_login","DATETIME NULL"),
        ("failed_attempts","INT NOT NULL DEFAULT 0"),
        ("locked_until","DATETIME NULL"),("notes","NVARCHAR(500) NULL"),
    ]
    try:
        conn = get_conn(autocommit=True); cur = conn.cursor()
        for c, d in cols:
            cur.execute(f"""IF NOT EXISTS(SELECT 1 FROM sys.columns
                WHERE object_id=OBJECT_ID('visitors') AND name='{c}')
                ALTER TABLE visitors ADD {c} {d}""")
        cur.close(); conn.close()
    except: pass

ensure_cols()

def load_users():
    try:
        conn = get_conn()
        df = pd.read_sql("""
            SELECT id, username, full_name,
                   ISNULL(role,'visitor') AS role,
                   ISNULL(phone,'') AS phone,
                   is_active,
                   last_login,
                   ISNULL(failed_attempts,0) AS failed_attempts,
                   locked_until,
                   ISNULL(notes,'') AS notes
            FROM visitors ORDER BY id
        """, conn)
        conn.close(); return df
    except Exception as e:
        st.error(f"خطای دیتابیس: {e}"); return pd.DataFrame()


# ══ ورود مدیر ══
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False

if not st.session_state.admin_ok:
    _, mc, _ = st.columns([1, 1.1, 1])
    with mc:
        st.markdown(f"""
        <div style='background:white;border-radius:22px;padding:40px 32px;
             box-shadow:0 12px 40px rgba(2,0,37,.18);direction:rtl;margin-top:50px;
             border-top:5px solid {C1}'>
            <div style='text-align:center;margin-bottom:28px'>
                <div style='font-size:48px;margin-bottom:10px'>👥</div>
                <div style='font-size:20px;font-weight:900;color:{C1}'>پنل مدیریت پیچا</div>
                <div style='font-size:12px;color:#94a3b8;margin-top:4px'>ورود ویژه مدیر سیستم</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        adm_u = st.text_input("🔑 نام کاربری مدیر:", placeholder="مثال: admin")
        adm_p = st.text_input("🔒 رمز عبور:", type="password", placeholder="••••••")
        if st.button("ورود به پنل مدیریت", type="primary", use_container_width=True):
            if not adm_u or not adm_p:
                st.error("نام کاربری و رمز الزامی است.")
            else:
                try:
                    conn = get_conn(); cur = conn.cursor()
                    cur.execute("""SELECT id FROM visitors
                        WHERE username=? AND password_hash=?
                        AND ISNULL(role,'visitor')='admin' AND is_active=1
                    """, (adm_u.strip(), hp(adm_p)))
                    if cur.fetchone():
                        st.session_state.admin_ok   = True
                        st.session_state.admin_user = adm_u
                        st.rerun()
                    else:
                        st.error("اطلاعات اشتباه یا دسترسی مدیر ندارید.")
                    cur.close(); conn.close()
                except Exception as e:
                    st.error(f"خطا: {e}")
    st.stop()


# ══ هدر ══
hc1, hc2 = st.columns([5, 1])
with hc1:
    st.markdown(f"""
    <div class='pg-head'>
        <div>
            <div style='font-size:18px;font-weight:900;color:{C1}'>👥 مدیریت کاربران | پیچا ویزیت</div>
            <div style='font-size:12px;color:#94a3b8;margin-top:2px'>
                مدیر: <b style='color:{C1}'>{st.session_state.get("admin_user","")}</b>
                &nbsp;|&nbsp; {datetime.now().strftime('%Y/%m/%d  %H:%M')}
            </div>
        </div>
        <div style='font-size:32px;opacity:.1'>{C1 and "👥"}</div>
    </div>
    """, unsafe_allow_html=True)
with hc2:
    if st.button("🚪 خروج", use_container_width=True):
        st.session_state.admin_ok = False; st.rerun()

users_df = load_users()
tab1, tab2, tab3 = st.tabs([
    f"📋 کاربران ({len(users_df)})",
    "➕ کاربر جدید",
    "⚙️ تنظیمات"
])


# ══════════════════════════════════════════════
# تب ۱ — لیست کاربران
# ══════════════════════════════════════════════
with tab1:
    if users_df.empty:
        st.info("هیچ کاربری ثبت نشده است.")
    else:
        # آمار
        total  = len(users_df)
        active = int(users_df['is_active'].sum())
        admins = int((users_df['role']=='admin').sum())
        try: locked = int(users_df['locked_until'].notna().sum())
        except: locked = 0

        s1,s2,s3,s4 = st.columns(4)
        for col,ic,v,lb,clr,bg in [
            (s1,"👥",total,  "کل کاربران", C1,       "#e8eaf6"),
            (s2,"✅",active, "فعال",        "#1b5e20","#e8f5e9"),
            (s3,"🛡️",admins, "مدیر",        "#7b1fa2","#f3e5f5"),
            (s4,"🔒",locked, "قفل‌شده",     "#e65100","#fff3e0"),
        ]:
            with col:
                st.markdown(f"""
                <div class='stat-card' style='border-color:{clr};background:{bg}'>
                    <div style='font-size:22px'>{ic}</div>
                    <div style='font-size:30px;font-weight:900;color:{clr}'>{v}</div>
                    <div style='font-size:12px;color:#64748b;font-weight:600'>{lb}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # لیست کاربران
        for _, u in users_df.iterrows():
            uid   = int(u['id'])
            uname = str(u['username'])
            fname = str(u['full_name'])
            role  = str(u['role'])
            phone = str(u['phone']) if u['phone'] else '—'
            notes = str(u['notes']) if u['notes'] else ''
            act   = bool(u['is_active'])
            failed= int(u['failed_attempts'])

            try:
                is_locked = pd.notna(u['locked_until']) and u['locked_until'] is not None
                lock_str  = str(u['locked_until'])[:16] if is_locked else ''
            except:
                is_locked = False; lock_str = ''

            try:
                last = str(u['last_login'])[:16] if pd.notna(u['last_login']) else '—'
            except:
                last = '—'

            # badge‌ها
            role_b  = f"<span class='badge b-admin'>🛡️ مدیر</span>" if role=='admin' else f"<span class='badge b-visitor'>👤 ویزیتور</span>"
            act_b   = f"<span class='badge b-active'>✅ فعال</span>" if act else f"<span class='badge b-inactive'>❌ غیرفعال</span>"
            lock_b  = f"<span class='badge b-locked'>🔒 قفل</span>" if is_locked else ""

            # ── هدر کارت ──
            st.markdown(f"""
            <div class='user-card'>
                <div class='user-card-head'>
                    <div>
                        <div class='u-name'>{'👑' if role=='admin' else '👤'} &nbsp;{fname}</div>
                        <div class='u-meta'>@{uname}</div>
                    </div>
                    <div class='u-badges'>{role_b}{act_b}{lock_b}</div>
                </div>
                <div class='info-grid'>
                    <div class='info-cell'>
                        <div class='ic-lbl'>تلفن</div>
                        <div class='ic-val'>{phone}</div>
                    </div>
                    <div class='info-cell'>
                        <div class='ic-lbl'>آخرین ورود</div>
                        <div class='ic-val'>{last}</div>
                    </div>
                    <div class='info-cell'>
                        <div class='ic-lbl'>تلاش ناموفق</div>
                        <div class='ic-val'>{failed} بار {('| 🔒 تا '+lock_str) if is_locked else ''}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── فرم ویرایش در container ──
            with st.container():
                st.markdown(f"""
                <div style='background:white;border:1.5px solid #dde3f0;
                     border-top:none;border-radius:0 0 14px 14px;
                     padding:18px 18px 20px;margin-top:-12px;margin-bottom:12px;
                     direction:rtl'>
                    <div style='font-size:11px;font-weight:800;color:#94a3b8;
                         margin-bottom:14px;padding-bottom:8px;
                         border-bottom:1px solid #f0f3fa'>
                        ✏️ ویرایش اطلاعات کاربر
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # ردیف ۱
                c1_, c2_, c3_ = st.columns(3)
                with c1_:
                    new_name = st.text_input("👤 نام کامل", value=fname, key=f"fn_{uid}")
                with c2_:
                    new_phone = st.text_input("📱 تلفن", value=u['phone'] or '', key=f"ph_{uid}")
                with c3_:
                    new_role = st.selectbox("🛡️ نقش",
                        ["visitor","admin"],
                        index=1 if role=='admin' else 0,
                        format_func=lambda x:"🛡️ مدیر" if x=="admin" else "👤 ویزیتور",
                        key=f"ro_{uid}")

                # ردیف ۲
                c4_, c5_, c6_ = st.columns(3)
                with c4_:
                    new_pass = st.text_input("🔒 رمز جدید",
                        type="password", placeholder="خالی = بدون تغییر",
                        key=f"pw_{uid}", help="حداقل ۶ کاراکتر")
                with c5_:
                    new_notes = st.text_input("📝 یادداشت",
                        value=u['notes'] or '', key=f"no_{uid}")
                with c6_:
                    new_act = st.checkbox("✅ حساب فعال باشد",
                        value=act, key=f"ac_{uid}")

                # دکمه‌ها
                b1, b2, b3 = st.columns([2, 2, 3])
                with b1:
                    if st.button("💾 ذخیره", key=f"sv_{uid}", use_container_width=True, type="primary"):
                        try:
                            conn = get_conn(); cur = conn.cursor()
                            if new_pass and len(new_pass) >= 6:
                                cur.execute("""UPDATE visitors SET
                                    full_name=?,phone=?,role=?,
                                    is_active=?,notes=?,password_hash=?
                                    WHERE id=?""",
                                    (new_name, new_phone or None, new_role,
                                     int(new_act), new_notes or None,
                                     hp(new_pass), uid))
                            else:
                                cur.execute("""UPDATE visitors SET
                                    full_name=?,phone=?,role=?,
                                    is_active=?,notes=?
                                    WHERE id=?""",
                                    (new_name, new_phone or None, new_role,
                                     int(new_act), new_notes or None, uid))
                            conn.commit(); cur.close(); conn.close()
                            st.success("✅ ذخیره شد!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")
                with b2:
                    if is_locked:
                        if st.button("🔓 رفع قفل", key=f"ul_{uid}", use_container_width=True):
                            try:
                                conn=get_conn(); cur=conn.cursor()
                                cur.execute("UPDATE visitors SET failed_attempts=0,locked_until=NULL WHERE id=?", (uid,))
                                conn.commit(); cur.close(); conn.close()
                                st.success("✅ قفل برداشته شد!"); st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# تب ۲ — کاربر جدید
# ══════════════════════════════════════════════
with tab2:
    st.markdown(f"""
    <div style='background:white;border-radius:16px;padding:24px 26px;
         box-shadow:0 3px 14px rgba(2,0,37,.07);direction:rtl;
         max-width:700px;margin:0 auto 20px;border-top:4px solid {C1}'>
        <div style='font-size:16px;font-weight:900;color:{C1};margin-bottom:4px'>
            ➕ ثبت کاربر / ویزیتور جدید
        </div>
        <div style='font-size:12px;color:#94a3b8'>
            پس از ثبت، کاربر با اطلاعات زیر می‌تواند وارد سامانه شود.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("""
        <div style='background:white;border-radius:16px;padding:24px 26px;
             max-width:700px;margin:0 auto;
             box-shadow:0 3px 14px rgba(2,0,37,.07);direction:rtl'>
        </div>""", unsafe_allow_html=True)

        nc1, nc2 = st.columns(2)
        with nc1:
            n_full  = st.text_input("👤 نام و نام خانوادگی *",
                                    placeholder="مثال: علی محمدی")
            n_user  = st.text_input("🔑 نام کاربری *",
                                    placeholder="مثال: ali.m  (بدون فاصله)")
            n_phone = st.text_input("📱 شماره موبایل",
                                    placeholder="09121234567")
        with nc2:
            n_pass  = st.text_input("🔒 رمز عبور *", type="password",
                                    placeholder="حداقل ۶ کاراکتر")
            n_pass2 = st.text_input("🔒 تکرار رمز عبور *", type="password",
                                    placeholder="تکرار رمز")
            n_role  = st.selectbox("🛡️ نقش کاربر",
                                   ["visitor","admin"],
                                   format_func=lambda x:
                                   "👤 ویزیتور" if x=="visitor" else "🛡️ مدیر سیستم")

        n_notes = st.text_area("📝 یادداشت (اختیاری)",
                               height=80,
                               placeholder="توضیحات اضافی...")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("✅ ثبت کاربر جدید", type="primary"):
            errs = []
            if not n_full.strip():  errs.append("نام کامل الزامی است")
            if not n_user.strip():  errs.append("نام کاربری الزامی است")
            if ' ' in n_user.strip(): errs.append("نام کاربری نباید فاصله داشته باشد")
            if not n_pass:          errs.append("رمز عبور الزامی است")
            elif len(n_pass) < 6:   errs.append("رمز باید حداقل ۶ کاراکتر باشد")
            if n_pass != n_pass2:   errs.append("رمز و تکرار آن یکسان نیست")
            if not users_df.empty and n_user.strip() in users_df['username'].values:
                errs.append("این نام کاربری قبلاً ثبت شده است")

            if errs:
                for e in errs: st.error(f"❌ {e}")
            else:
                try:
                    conn = get_conn(); cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO visitors
                            (username,password_hash,full_name,role,phone,notes,is_active)
                        VALUES (?,?,?,?,?,?,1)
                    """, (n_user.strip(), hp(n_pass), n_full.strip(),
                          n_role, n_phone.strip() or None,
                          n_notes.strip() or None))
                    conn.commit(); cur.close(); conn.close()
                    st.success(f"✅ کاربر «{n_full.strip()}» با نام کاربری @{n_user.strip()} ثبت شد!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ خطا: {e}")


# ══════════════════════════════════════════════
# تب ۳ — تنظیمات
# ══════════════════════════════════════════════
with tab3:
    st.markdown(f"""
    <div style='font-size:15px;font-weight:900;color:{C1};
         margin-bottom:16px;direction:rtl'>⚙️ تنظیمات سیستم</div>
    """, unsafe_allow_html=True)

    # بارگذاری تنظیمات
    try:
        from config import NETWORK, DATABASES, SECURITY, GPS, PATHS, APP
        cfgs = [
            ("🌐 شبکه و سرور",   NETWORK),
            ("🗄️ دیتابیس",       DATABASES),
            ("🔒 امنیت",         SECURITY),
            ("📍 GPS",           GPS),
            ("📁 مسیرها",        PATHS),
            ("🏷️ اطلاعات برنامه",APP),
        ]
    except ImportError:
        cfgs = [
            ("🌐 شبکه", {"SERVER_NAME": SERVER, "FLASK_PORT": 5000,
                          "PWA_PORT": 8000, "DASHBOARD_PORT": 8501, "ADMIN_PORT": 8502}),
            ("🔒 امنیت",{"MAX_LOGIN_ATTEMPTS": 5, "LOCKOUT_MINUTES": 30, "PASSWORD_MIN_LEN": 6}),
        ]

    for title, cfg in cfgs:
        with st.expander(title, expanded=False):
            rows = ""
            for k, v in cfg.items():
                dv = "••••••" if any(x in k.upper() for x in ["SECRET","PASS","KEY"]) else str(v)
                rows += f"<tr><td class='td-key'>{k}</td><td class='td-val'>{dv}</td></tr>"
            st.markdown(f"""
            <table class='cfg-tbl'>
                <thead><tr>
                    <th style='width:42%'>تنظیم</th>
                    <th>مقدار</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>""", unsafe_allow_html=True)
            st.caption("برای تغییر، فایل config.py را ویرایش و سرور را ری‌استارت کنید.")

    st.markdown("<br>", unsafe_allow_html=True)

    # تست اتصال
    st.markdown(f"""
    <div style='font-size:14px;font-weight:800;color:{C1};
         margin-bottom:10px;direction:rtl'>🔌 تست اتصال دیتابیس</div>
    """, unsafe_allow_html=True)

    t1, t2 = st.columns(2)
    with t1:
        if st.button("🔌 تست tracking", use_container_width=True):
            try:
                conn=get_conn(); cur=conn.cursor()
                cur.execute("SELECT COUNT(*) FROM visitors")
                cnt=cur.fetchone()[0]; cur.close(); conn.close()
                st.success(f"✅ اتصال OK | {cnt} کاربر")
            except Exception as e:
                st.error(f"❌ {e}")
    with t2:
        if st.button("🔌 تست dejavuDB1", use_container_width=True):
            try:
                conn=pyodbc.connect(
                    f'DRIVER={{SQL Server}};SERVER={SERVER};'
                    f'DATABASE=dejavuDB1;Trusted_Connection=yes;')
                cur=conn.cursor()
                cur.execute("SELECT COUNT(*) FROM customer WHERE [Delete]=0 OR [Delete] IS NULL")
                cnt=cur.fetchone()[0]; cur.close(); conn.close()
                st.success(f"✅ اتصال OK | {cnt} مشتری")
            except Exception as e:
                st.error(f"❌ {e}")

    # ریست اضطراری
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔴 ریست اضطراری رمز"):
        st.warning("⚠️ فقط در موارد اضطراری استفاده کنید.")
        rc1, rc2, rc3 = st.columns([2, 2, 1])
        with rc1: ru = st.text_input("نام کاربری:", key="rstu")
        with rc2: rp = st.text_input("رمز جدید:", type="password", key="rstp")
        with rc3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 ریست", use_container_width=True):
                if ru and rp and len(rp) >= 6:
                    try:
                        conn=get_conn(); cur=conn.cursor()
                        cur.execute("""UPDATE visitors
                            SET password_hash=?,failed_attempts=0,locked_until=NULL
                            WHERE username=?""", (hp(rp), ru.strip()))
                        if cur.rowcount > 0:
                            conn.commit()
                            st.success(f"✅ رمز @{ru} ریست شد.")
                        else:
                            st.error("کاربر یافت نشد.")
                        cur.close(); conn.close()
                    except Exception as e:
                        st.error(f"❌ {e}")
                else:
                    st.error("نام کاربری و رمز (حداقل ۶ کاراکتر) الزامی است.")
