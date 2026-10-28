# dashboard.py - پیچا ویزیت v5.0
import streamlit as st
import pyodbc
import pandas as pd
import folium
from streamlit_folium import st_folium
import jdatetime
from datetime import datetime
import io

def fa_num(n, is_currency=True):
    """فرمت عدد با جداکننده سه‌رقمی"""
    if n is None: return '—'
    try:
        n = float(n)
        s = f"{n:,.0f}"
        return s + (' ریال' if is_currency else '')
    except:
        return str(n)

st.set_page_config(
    page_title="PeechaVisit | داشبورد",
    page_icon="📍", layout="wide",
    initial_sidebar_state="expanded"
)

# ── بارگذاری از config ──
try:
    from config import NETWORK, DATABASES, APP, SECURITY
    SERVER_IP   = NETWORK["SERVER_IP"]
    SERVER_NAME = NETWORK["SERVER_NAME"]
    C1          = APP["PRIMARY_COLOR"]
except ImportError:
    SERVER_IP   = "10.165.254.180"
    SERVER_NAME = "SERWIN\\RAD"
    C1          = "#020025"

# ══════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800;900&display=swap');

html,body,*,[class*="css"],[data-testid],
p,span,div,label,h1,h2,h3,h4,h5,h6,
button,input,select,textarea,th,td,li,a {{
    font-family:'Vazirmatn',Tahoma,sans-serif !important;
}}
.stApp {{ background:#f0f2fa !important; direction:rtl !important; }}
.block-container {{ padding:20px 28px !important; max-width:100% !important; }}

/* ── RTL همه‌جا ── */
.stMarkdown,.stDataFrame,th,td,label,p,span,div,
[data-testid="stDataFrame"],[data-testid="column"],
.stTabs,.stExpander,details,summary,
.stAlert,.stInfo {{ direction:rtl !important; text-align:right !important; }}

/* ── سایدبار ── */
[data-testid="stSidebar"] {{
    background:linear-gradient(180deg,{C1} 0%,#0d0d4a 70%,#150035 100%) !important;
    min-width:290px !important; width:290px !important;
}}
[data-testid="stSidebar"] > div:first-child {{ padding:0 !important; min-width:290px !important; }}
[data-testid="stSidebar"] * {{
    color:#e8eaf6 !important;
    font-family:'Vazirmatn',Tahoma,sans-serif !important;
    direction:rtl !important;
}}
[data-testid="stSidebar"] label {{ color:#9fa8da !important; font-size:12px !important; font-weight:700 !important; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{
    background:rgba(255,255,255,.08) !important;
    border:1.5px solid rgba(255,255,255,.18) !important;
    border-radius:10px !important; color:white !important;
    font-size:13px !important;
}}
[data-testid="stSidebar"] .stButton>button {{
    background:linear-gradient(135deg,#3949ab,#5c6bc0) !important;
    color:white !important; border-radius:10px !important;
    border:none !important; font-weight:700 !important;
    width:100% !important; padding:11px !important; font-size:14px !important;
}}
[data-testid="stSidebar"] hr {{ border-color:rgba(255,255,255,.12) !important; margin:8px 0 !important; }}
/* مخفی کردن دکمه‌های collapse سایدبار */
[data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
button[kind="header"] {{ display:none !important; }}

/* ── حذف keyboard و اصلاح expander ── */
/* مخفی کردن تمام متن‌های keyboard در همه نسخه‌های Streamlit */
[data-testid="stExpander"] summary p + *,
[data-testid="stExpander"] details summary > div > div:last-child:not(:first-child),
details summary span:not([data-testid]):empty,
details summary div + div:last-child,
.st-emotion-cache-sh2krr,
.st-emotion-cache-1h9usn1,
.st-emotion-cache-p5msec,
details > summary span[aria-label*="keyboard"],
details > summary span[aria-label*="Keyboard"],
button[aria-keyshortcuts],
span[aria-keyshortcuts],
[class*="shortcut"],
[class*="keyboard"]:not(input):not(textarea),
[class*="KeyboardShortcut"] {{
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    font-size: 0 !important;
    opacity: 0 !important;
    position: absolute !important;
    pointer-events: none !important;
}}

/* expander RTL - فلش راست، متن راست */
[data-testid="stExpander"] details > summary {{
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 14px 16px !important;
    list-style: none !important;
    direction: rtl !important;
    cursor: pointer !important;
}}
[data-testid="stExpander"] details > summary::marker,
[data-testid="stExpander"] details > summary::-webkit-details-marker {{ display:none !important; }}

/* فلش در سمت راست (اول) */
[data-testid="stExpander"] details > summary > svg,
[data-testid="stExpander"] details > summary [data-testid="stExpanderToggleIcon"] {{
    order: 0 !important;
    flex-shrink: 0 !important;
    color: #94a3b8 !important;
}}

/* متن عنوان */
[data-testid="stExpander"] details > summary > div {{
    order: 1 !important;
    flex: 1 !important;
    direction: rtl !important;
    text-align: right !important;
}}
[data-testid="stExpander"] details > summary p {{
    margin: 0 !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    color: {C1} !important;
    direction: rtl !important;
    text-align: right !important;
    font-family: 'Vazirmatn', Tahoma, sans-serif !important;
}}

/* ── KPI ── */
.kpi-box {{
    background:white; border-radius:16px; padding:18px 14px;
    text-align:center; box-shadow:0 3px 16px rgba(2,0,37,.08);
    border-top:4px solid; transition:transform .18s;
}}
.kpi-box:hover {{ transform:translateY(-3px); }}
.kpi-i {{ font-size:24px; margin-bottom:5px; }}
.kpi-v {{ font-size:30px; font-weight:900; line-height:1.1; }}
.kpi-l {{ font-size:12px; color:#64748b; font-weight:600; margin-top:3px; }}
.kpi-s {{ font-size:11px; font-weight:700; margin-top:4px; }}

/* ── تب‌ها ── */
.stTabs [data-baseweb="tab-list"] {{
    background:white !important; border-radius:12px !important;
    padding:4px !important; gap:3px !important;
    box-shadow:0 2px 10px rgba(0,0,0,.07) !important;
    flex-direction:row-reverse !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius:9px !important; font-weight:700 !important;
    font-size:13px !important; color:#475569 !important;
    padding:8px 16px !important;
}}
.stTabs [aria-selected="true"] {{
    background:linear-gradient(135deg,{C1},#3949ab) !important; color:white !important;
}}

/* ── کارت رکورد ── */
.rec-card {{
    background:white; border-radius:14px;
    border:1.5px solid #e2e8f0; margin-bottom:10px;
    box-shadow:0 2px 10px rgba(2,0,37,.06);
    overflow:hidden; transition:box-shadow .18s;
    direction:rtl;
}}
.rec-card:hover {{ box-shadow:0 5px 20px rgba(2,0,37,.11); }}

/* هدر کارت - کلیک‌پذیر */
.rec-head {{
    display:flex; align-items:center; justify-content:space-between;
    padding:13px 16px; cursor:pointer; background:#f8fafc;
    border-bottom:1.5px solid transparent; direction:rtl;
    transition:background .15s;
}}
.rec-head:hover {{ background:#f0f4ff; }}
.rec-head-open {{ border-bottom-color:#e2e8f0 !important; background:#f0f4ff !important; }}

.rec-head-right {{ display:flex; align-items:center; gap:10px; direction:rtl; }}
.rec-badge {{ display:inline-flex; align-items:center; gap:4px;
    padding:3px 10px; border-radius:8px; font-size:11px; font-weight:700; }}
.rec-type-visit   {{ background:#e8eaf6; color:{C1}; border:1px solid #c5cae9; }}
.rec-type-order   {{ background:#f3e5f5; color:#6a1b9a; border:1px solid #ce93d8; }}
.rec-type-pay     {{ background:#e8f5e9; color:#1b5e20; border:1px solid #a5d6a7; }}
.rec-type-cash    {{ background:#e3f2fd; color:#0d47a1; }}
.rec-type-check   {{ background:#fce4ec; color:#880e4f; }}
.rec-type-transfer{{ background:#fff3e0; color:#e65100; }}

.rec-name {{ font-size:14px; font-weight:800; color:{C1}; }}
.rec-meta {{ font-size:11px; color:#64748b; margin-top:2px; direction:rtl; }}

.rec-left {{ display:flex; align-items:center; gap:8px; }}
.rec-amount {{ font-size:14px; font-weight:800; color:#1b5e20; white-space:nowrap; }}
.rec-arrow {{ color:#94a3b8; font-size:14px; transition:transform .2s; }}
.rec-arrow-open {{ transform:rotate(180deg) !important; }}

/* بدنه کارت */
.rec-body {{ padding:14px 16px; direction:rtl; }}

/* گرید اطلاعات */
.info-grid {{
    display:grid; grid-template-columns:1fr 1fr;
    gap:8px; direction:rtl; margin-bottom:10px;
}}
.info-cell {{
    background:#f8fafc; border-radius:9px;
    padding:9px 12px; direction:rtl;
}}
.info-cell .lbl {{ font-size:10px; color:#94a3b8; font-weight:700; margin-bottom:2px; }}
.info-cell .val {{ font-size:13px; font-weight:700; color:#1e293b; }}

/* جدول اقلام سفارش */
.items-table {{ width:100%; border-collapse:collapse; direction:rtl; margin-top:8px; }}
.items-table th {{
    background:{C1}; color:white; padding:9px 12px;
    font-size:12px; font-weight:700; text-align:right;
}}
.items-table td {{
    padding:9px 12px; font-size:12px; text-align:right;
    border-bottom:1px solid #f0f2fa;
}}
.items-table tr:last-child td {{ border-bottom:none; }}
.items-table tr:hover td {{ background:#f8fafc; }}
.items-total {{
    display:flex; justify-content:space-between; align-items:center;
    background:#f0f2fa; border-radius:8px; padding:10px 14px;
    margin-top:6px; direction:rtl;
}}
.items-total .lbl {{ font-size:12px; color:#64748b; font-weight:600; }}
.items-total .val {{ font-size:14px; font-weight:900; color:#7b1fa2; }}

/* عکس */
.img-thumb {{
    border-radius:10px; overflow:hidden;
    border:2px solid #e2e8f0; margin-top:8px;
    cursor:pointer; transition:transform .18s;
    display:inline-block; max-width:200px;
}}
.img-thumb:hover {{ transform:scale(1.02); }}
.img-thumb img {{ width:100%; display:block; }}
.img-cap {{ font-size:10px; color:#94a3b8; text-align:center; margin-top:3px; }}

/* تگ وضعیت */
.status-tag {{
    display:inline-flex; align-items:center; gap:4px;
    padding:4px 10px; border-radius:8px;
    font-size:11px; font-weight:700; margin:2px;
}}
.status-ok  {{ background:#d1fae5; color:#065f46; }}
.status-no  {{ background:#fee2e2; color:#991b1b; }}

/* اطلاعات چک */
.check-info,.transfer-info {{
    border-radius:10px; padding:12px 14px;
    margin-top:8px; direction:rtl; font-size:12px; line-height:2;
}}
.check-info {{ background:#fce4ec; border:1px solid #f48fb1; }}
.transfer-info {{ background:#e3f2fd; border:1px solid #90caf9; }}

/* دکمه دانلود */
.stDownloadButton button {{
    background:linear-gradient(135deg,#1b5e20,#2e7d32) !important;
    color:white !important; border-radius:10px !important;
    border:none !important; font-weight:700 !important;
    padding:10px 20px !important; font-size:13px !important;
}}
.stAlert {{ border-radius:11px !important; }}

/* footer */
.dash-footer {{
    text-align:center; padding:16px; font-size:12px;
    color:#94a3b8; direction:rtl; margin-top:20px;
    border-top:1px solid #e2e8f0;
}}
.dash-footer a {{ color:#4f6ef7; text-decoration:none; font-weight:700; }}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# توابع
# ══════════════════════════════════════════════════════
def qry(sql, params=None, db="tracking"):
    try:
        conn = pyodbc.connect(
            f'DRIVER={{SQL Server}};SERVER={SERVER_NAME};'
            f'DATABASE={db};Trusted_Connection=yes;'
        )
        df = pd.read_sql(sql, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"خطای دیتابیس: {e}")
        return pd.DataFrame()

def to_j(d):
    try:
        if pd.isna(d): return '—'
    except: pass
    try:
        if isinstance(d, str): d = datetime.strptime(str(d)[:10], '%Y-%m-%d').date()
        if hasattr(d, 'date'): d = d.date()
        return jdatetime.date.fromgregorian(date=d).strftime('%Y/%m/%d')
    except: return str(d)[:10] if d else '—'

def ct(t):
    s = str(t).split('.')[0]
    return s if s not in ('None','nan','') else '—'

def img(path):
    if path and str(path).strip() not in ('','None','nan'):
        return f"http://{SERVER_IP}:5000{path}"
    return None

def ensure_cols():
    cols = [
        ("check_number","VARCHAR(50)"),("check_sayyadi","VARCHAR(50)"),
        ("check_due_date","DATE"),("check_image_path","NVARCHAR(500)"),
        ("transfer_account","VARCHAR(100)"),("transfer_tracking","VARCHAR(100)"),
        ("transfer_image_path","NVARCHAR(500)"),
    ]
    try:
        conn = pyodbc.connect(
            f'DRIVER={{SQL Server}};SERVER={SERVER_NAME};'
            f'DATABASE=tracking;Trusted_Connection=yes;', autocommit=True
        )
        cur = conn.cursor()
        for col,dtype in cols:
            try:
                cur.execute(f"""IF NOT EXISTS(SELECT 1 FROM sys.columns
                    WHERE object_id=OBJECT_ID('payments') AND name='{col}')
                    ALTER TABLE payments ADD {col} {dtype} NULL""")
            except: pass
        cur.close(); conn.close()
    except: pass

ensure_cols()


# ══════════════════════════════════════════════════════
# سایدبار
# ══════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style='padding:22px 20px 14px;direction:rtl'>
        <div style='display:flex;align-items:center;gap:12px'>
            <span style='font-size:30px'>📍</span>
            <div>
                <div style='font-size:19px;font-weight:900;color:white'>پیچا ویزیت</div>
                <div style='font-size:10px;color:#9fa8da;direction:ltr'>PeechaVisit.ir</div>
            </div>
        </div>
    </div><hr>
    """, unsafe_allow_html=True)

    st.markdown("<div style='color:#9fa8da;font-size:12px;font-weight:700;padding:0 20px 6px'>👤 ویزیتور</div>", unsafe_allow_html=True)
    vdf = qry("SELECT id,full_name FROM visitors WHERE is_active=1 OR is_active IS NULL")
    if vdf.empty:
        sel_vid=None; sel_vname="همه ویزیتورها"
    else:
        vopts = {"👥 همه ویزیتورها": None}
        vopts.update({r['full_name']:r['id'] for _,r in vdf.iterrows()})
        sel_vname = st.selectbox("ویزیتور", list(vopts.keys()), label_visibility="collapsed")
        sel_vid = vopts[sel_vname]

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div style='color:#9fa8da;font-size:12px;font-weight:700;padding:0 20px 8px'>📅 بازه گزارش شمسی</div>", unsafe_allow_html=True)

    today_j = jdatetime.date.today()
    months = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور",
              "مهر","آبان","آذر","دی","بهمن","اسفند"]
    years = [1403,1404,1405,1406]

    st.markdown("<div style='color:#c5cae9;font-size:11px;padding:0 20px 4px'>🔹 از تاریخ</div>", unsafe_allow_html=True)
    a,b,c = st.columns([3,3,2])
    with a: sy = st.selectbox("سال از",years,index=2,key="sy",label_visibility="collapsed")
    with b: sm = st.selectbox("ماه از",range(1,13),index=today_j.month-1,key="sm",
                               format_func=lambda x:months[x-1],label_visibility="collapsed")
    with c: sd = st.selectbox("روز از",range(1,32),index=0,key="sd",label_visibility="collapsed")

    st.markdown("<div style='color:#c5cae9;font-size:11px;padding:4px 20px'>🔸 تا تاریخ</div>", unsafe_allow_html=True)
    d,e,f_ = st.columns([3,3,2])
    with d: ey = st.selectbox("سال تا",years,index=2,key="ey",label_visibility="collapsed")
    with e: em = st.selectbox("ماه تا",range(1,13),index=today_j.month-1,key="em",
                               format_func=lambda x:months[x-1],label_visibility="collapsed")
    with f_: ed = st.selectbox("روز تا",range(1,32),index=today_j.day-1,key="ed",label_visibility="collapsed")

    try:
        j0 = jdatetime.date(int(sy),int(sm),int(sd))
        j1 = jdatetime.date(int(ey),int(em),int(ed))
        g0 = j0.togregorian().strftime('%Y-%m-%d')
        g1 = j1.togregorian().strftime('%Y-%m-%d')
    except:
        st.error("❌ تاریخ نامعتبر")
        j0=j1=today_j
        g0=g1=today_j.togregorian().strftime('%Y-%m-%d')

    st.markdown(f"""
    <div style='background:rgba(255,255,255,.08);border-radius:10px;
         padding:10px 14px;margin:8px 16px;font-size:12px;color:#c5cae9;
         direction:rtl;text-align:center'>
        <b style='color:white'>{j0.strftime('%Y/%m/%d')}</b>
        &nbsp; ← &nbsp;
        <b style='color:white'>{j1.strftime('%Y/%m/%d')}</b>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='padding:4px 16px 16px'>", unsafe_allow_html=True)
    if st.button("🔄 بروزرسانی", use_container_width=True):
        st.rerun()
    st.markdown("</div><hr>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='padding:8px 20px 20px;font-size:11px;color:#7986cb;text-align:center'>
        <a href='https://peecha.ir' target='_blank' style='color:#7986cb;text-decoration:none'>🌐 peecha.ir</a>
        &nbsp;|&nbsp; PeechaVisit © ۱۴۰۵
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# واکشی داده‌ها
# ══════════════════════════════════════════════════════
# ── فیلتر ویزیتور: None = همه ──
def _w(date_col, visitor_col_alias, params_base):
    """ساخت WHERE clause با alias صحیح برای هر جدول"""
    if sel_vid is not None:
        return f"{date_col} BETWEEN ? AND ? AND {visitor_col_alias}.visitor_id=?", params_base + (sel_vid,)
    return f"{date_col} BETWEEN ? AND ?", params_base

vw, vp = _w("v.visit_date", "v", (g0,g1))
ow, op = _w("o.order_date", "o", (g0,g1))
pw, pp = _w("p.payment_date","p", (g0,g1))

# اضافه کردن نام ویزیتور در نمایش همه
visitor_col = ", vis.full_name AS visitor_name" if sel_vid is None else ", '' AS visitor_name"

visits_df = qry(f"""
    SELECT v.id, v.visitor_id, v.customer_code, v.visit_date, v.visit_time,
           v.latitude, v.longitude,
           ISNULL(v.selfie_path,'')        AS selfie_path,
           ISNULL(v.description,'')        AS description,
           ISNULL(c.C_Name,v.customer_code) AS C_Name
           {visitor_col}
    FROM visits v
    LEFT JOIN dejavuDB1.dbo.customer c ON v.customer_code=c.C_Code
    {"LEFT JOIN visitors vis ON v.visitor_id=vis.id" if sel_vid is None else ""}
    WHERE {vw}
    ORDER BY v.visit_date,v.visit_time
""", vp)

orders_df = qry(f"""
    SELECT o.id, o.visitor_id, o.customer_code, o.order_date, o.order_time,
           o.latitude, o.longitude, o.total_amount,
           ISNULL(c.C_Name,o.customer_code) AS C_Name
           {", vis2.full_name AS visitor_name" if sel_vid is None else ", \'\' AS visitor_name"}
    FROM orders o
    LEFT JOIN dejavuDB1.dbo.customer c ON o.customer_code=c.C_Code
    {"LEFT JOIN visitors vis2 ON o.visitor_id=vis2.id" if sel_vid is None else ""}
    WHERE {ow}
    ORDER BY o.order_date,o.order_time
""", op)

pays_df = qry(f"""
    SELECT p.id, p.visitor_id, p.customer_code, p.payment_date, p.payment_time,
           p.payment_type, p.amount,
           ISNULL(p.check_number,'')        AS check_number,
           ISNULL(p.check_sayyadi,'')       AS check_sayyadi,
           p.check_due_date,
           ISNULL(p.check_image_path,'')    AS check_image_path,
           ISNULL(p.transfer_account,'')    AS transfer_account,
           ISNULL(p.transfer_image_path,'') AS transfer_image_path,
           ISNULL(p.tracking_number,'')     AS tracking_number,
           ISNULL(c.C_Name,p.customer_code) AS C_Name
           {", vis3.full_name AS visitor_name" if sel_vid is None else ", \'\' AS visitor_name"}
    FROM payments p
    LEFT JOIN dejavuDB1.dbo.customer c ON p.customer_code=c.C_Code
    {"LEFT JOIN visitors vis3 ON p.visitor_id=vis3.id" if sel_vid is None else ""}
    WHERE {pw}
    ORDER BY p.payment_date,p.payment_time
""", pp)


# ══════════════════════════════════════════════════════
# هدر
# ══════════════════════════════════════════════════════
tv=len(visits_df); to_=len(orders_df)
toa=orders_df['total_amount'].sum() if not orders_df.empty else 0
tp=len(pays_df); tpa=pays_df['amount'].sum() if not pays_df.empty else 0

st.markdown(f"""
<div style='background:white;border-radius:15px;padding:15px 22px;
     box-shadow:0 3px 16px rgba(2,0,37,.08);margin-bottom:16px;
     direction:rtl;display:flex;align-items:center;justify-content:space-between'>
    <div>
        <div style='font-size:19px;font-weight:900;color:{C1}'>📊 داشبورد پیچا ویزیت</div>
        <div style='font-size:12px;color:#64748b;margin-top:3px'>
            👤 <b style='color:#3949ab'>{sel_vname}</b>
            &nbsp;|&nbsp; {j0.strftime('%Y/%m/%d')} تا {j1.strftime('%Y/%m/%d')}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ══ KPI ══
k1,k2,k3,k4 = st.columns(4)
kdata=[
    (k1,"📍",tv,"ویزیت",f"{tv} مشتری","#3949ab","#e8eaf6"),
    (k2,"📦",to_,"سفارش",fa_num(toa),"#7b1fa2","#f3e5f5"),
    (k3,"💰",tp,"دریافت",fa_num(tpa),"#1b5e20","#e8f5e9"),
    (k4,"🎯",len(orders_df['customer_code'].unique()) if not orders_df.empty else 0,
     "مشتری با سفارش",f"از {tv} ویزیت","#e65100","#fff3e0"),
]
for col,ic,v,lb,sub,clr,bg in kdata:
    with col:
        st.markdown(f"""<div class='kpi-box' style='border-color:{clr};background:{bg}'>
            <div class='kpi-i'>{ic}</div>
            <div class='kpi-v' style='color:{clr}'>{v}</div>
            <div class='kpi-l'>{lb}</div>
            <div class='kpi-s' style='color:{clr}'>{sub}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# نقشه
# ══════════════════════════════════════════════════════
st.markdown(f"<div style='font-size:16px;font-weight:800;color:{C1};margin-bottom:10px;direction:rtl'>🗺️ نقشه مسیر</div>", unsafe_allow_html=True)

if not visits_df.empty:
    m = folium.Map(location=[visits_df['latitude'].mean(), visits_df['longitude'].mean()], zoom_start=14)
    pts=[]; n=len(visits_df)
    for i,(_,row) in enumerate(visits_df.iterrows()):
        pt=[float(row['latitude']),float(row['longitude'])]; pts.append(pt)
        step=i+1; color="green" if step==1 else ("red" if step==n else "blue")
        d_ord=orders_df[orders_df['customer_code']==row['customer_code']] if not orders_df.empty else pd.DataFrame()
        d_pay=pays_df[pays_df['customer_code']==row['customer_code']] if not pays_df.empty else pd.DataFrame()

        # popup فشرده - فقط اطلاعات همین ویزیت
        sp_link = img(row.get("selfie_path",""))

        # فیلتر دقیق: همون مشتری AND همون تاریخ ویزیت
        visit_date_str = str(row['visit_date'])[:10]
        d_ord = orders_df[
            (orders_df['customer_code']==row['customer_code']) &
            (orders_df['order_date'].astype(str).str[:10]==visit_date_str)
        ] if not orders_df.empty else pd.DataFrame()
        d_pay = pays_df[
            (pays_df['customer_code']==row['customer_code']) &
            (pays_df['payment_date'].astype(str).str[:10]==visit_date_str)
        ] if not pays_df.empty else pd.DataFrame()

        ord_txt = f"✔ {fa_num(d_ord['total_amount'].sum())} ({len(d_ord)} فاکتور)" if not d_ord.empty else "❌ بدون سفارش"
        pay_txt = f"✔ {fa_num(d_pay['amount'].sum())}" if not d_pay.empty else "❌ بدون دریافت"
        ord_clr = "#6a1b9a" if not d_ord.empty else "#dc2626"
        pay_clr = "#1b5e20" if not d_pay.empty else "#dc2626"

        selfie_html = (
            f"<div style=\'margin-top:7px\'>"
            f"<a href=\'{sp_link}\' target=\'_blank\'>"
            f"<img src=\'{sp_link}\' style=\'width:100%;height:72px;object-fit:cover;"
            f"border-radius:7px;border:1.5px solid rgba(255,255,255,.3);display:block\'></a>"
            f"<div style=\'font-size:9px;color:rgba(255,255,255,.6);text-align:center;margin-top:2px\'>📸 کلیک برای بزرگنمایی</div>"
            f"</div>"
        ) if sp_link else ""

        popup_html = (
            "<div style=\'direction:rtl;font-family:Tahoma,Arial;font-size:11px;"
            "width:220px;text-align:right;"
            "animation:pvPop .25s cubic-bezier(.34,1.56,.64,1)\'>"
            "<style>.leaflet-popup-content-wrapper{border-radius:14px!important;"
            "box-shadow:0 8px 28px rgba(0,0,0,.22)!important;overflow:hidden!important;padding:0!important}"
            ".leaflet-popup-content{margin:0!important;width:220px!important}"
            f"@keyframes pvPop{{from{{opacity:0;transform:scale(.85) translateY(8px)}}to{{opacity:1;transform:scale(1) translateY(0)}}}}</style>"
            f"<div style=\'background:linear-gradient(135deg,{C1},#3949ab);color:white;"
            f"padding:10px 12px 8px\'>"
            f"<div style=\'font-size:12px;font-weight:bold;margin-bottom:3px\'>📍 {row['C_Name']}</div>"
            f"<div style=\'font-size:10px;opacity:.75\'>گام {step} از {n}  ·  {to_j(row['visit_date'])}</div>"
            f"</div>"
            f"<div style=\'background:white;padding:9px 12px\'>"
            f"<div style=\'display:flex;justify-content:space-between;align-items:center;"
            f"padding:5px 0;border-bottom:1px solid #f0f2fa\'>"
            f"<span style=\'color:#64748b;font-size:10px\'>📦 سفارش</span>"
            f"<span style=\'color:{ord_clr};font-weight:700;font-size:11px\'>{ord_txt}</span>"
            f"</div>"
            f"<div style=\'display:flex;justify-content:space-between;align-items:center;"
            f"padding:5px 0\'>"
            f"<span style=\'color:#64748b;font-size:10px\'>💰 دریافت</span>"
            f"<span style=\'color:{pay_clr};font-weight:700;font-size:11px\'>{pay_txt}</span>"
            f"</div>"
            f"{selfie_html}"
            f"<div style=\'font-size:10px;color:#94a3b8;margin-top:5px;text-align:center\'>"
            f"⏰ {ct(row['visit_time'])}</div>"
            f"</div>"
            "</div>"
        )

        folium.Marker(pt,
            popup=folium.Popup(popup_html, max_width=230),
            tooltip=f"{'🟢' if step==1 else '🔴' if step==n else '🔵'} گام {step}: {row['C_Name']}",
            icon=folium.Icon(color=color, icon="map-marker")
        ).add_to(m)

    if len(pts)>1:
        folium.PolyLine(pts,color=C1,weight=3,opacity=0.7,dash_array='6,4').add_to(m)
    st_folium(m, height=440, use_container_width=True)
else:
    st.info("در این بازه ویزیتی ثبت نشده.")

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# تابع رندر کارت رکورد
# ══════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════
# session state
# ══════════════════════════════════════════════════════
if 'sel_type' not in st.session_state: st.session_state.sel_type = None
if 'sel_idx'  not in st.session_state: st.session_state.sel_idx  = None

def set_sel(t, i):
    st.session_state.sel_type = t
    st.session_state.sel_idx  = i

def fa(v):
    try: return f"{float(v):,.0f} ریال"
    except: return str(v)

# ══════════════════════════════════════════════════════
# Layout: ستون اصلی + ستون جزئیات سمت راست
# ══════════════════════════════════════════════════════
has_detail = st.session_state.sel_type is not None

if has_detail:
    main_col, detail_col = st.columns([3, 1.4])
else:
    main_col = st.container()
    detail_col = None


# ══════════════════════════════════════════════════════
# ستون اصلی — تب‌ها و لیست‌ها
# ══════════════════════════════════════════════════════
with main_col:

    tab1, tab2, tab3 = st.tabs([
        f"📋 ویزیت‌ها ({tv})",
        f"📦 سفارشات ({to_})",
        f"💰 دریافت‌ها ({tp})",
    ])

    # ─── CSS لیست‌ها ───
    st.markdown("""
    <style>
    .list-row {
        display:flex; align-items:center; direction:rtl;
        padding:6px 14px; border-bottom:1px solid #f0f2fa;
        transition:background .12s; gap:8px;
    }
    .list-row:hover { background:#f8faff; }
    .list-row.selected { background:#eef1fb; }
    .lr-name  { flex:2; font-size:13px; font-weight:700; color:#1e293b; direction:rtl; }
    .lr-date  { flex:1.2; font-size:12px; font-weight:700; color:#3949ab; direction:rtl; }
    .lr-time  { flex:1; font-size:12px; color:#64748b; direction:rtl; }
    .lr-extra { flex:1.5; font-size:12px; direction:rtl; }
    .lr-badge { display:inline-block; padding:3px 8px; border-radius:7px;
                font-size:11px; font-weight:700; }
    .lr-hdr   { display:flex; align-items:center; direction:rtl;
                padding:8px 14px; background:#f0f2fa;
                border-radius:10px 10px 0 0; gap:8px;
                font-size:11px; font-weight:800; color:#64748b; }
    </style>
    """, unsafe_allow_html=True)


    # ─── تب ویزیت‌ها ───
    with tab1:
        if visits_df.empty:
            st.info("در این بازه ویزیتی ثبت نشده.")
        else:
            # هدر
            st.markdown("""
            <div class='lr-hdr'>
                <div style='flex:0.3'>ردیف</div>
                <div style='flex:2'>نام مشتری</div>
                <div style='flex:1.2'>تاریخ</div>
                <div style='flex:1'>ساعت</div>
                <div style='flex:1.5'>توضیحات</div>
                <div style='flex:0.7'></div>
            </div>
            """, unsafe_allow_html=True)

            for i, (_, row) in enumerate(visits_df.iterrows()):
                jdate  = to_j(row['visit_date'])
                vtime  = ct(row['visit_time'])
                cname  = row['C_Name']
                desc   = str(row.get('description','') or '')[:18]
                is_sel = (st.session_state.sel_type=='v' and st.session_state.sel_idx==i)

                rc = st.columns([0.3, 2, 1.2, 1, 1.5, 0.7])
                with rc[0]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:11px;color:#94a3b8;direction:rtl'>{i+1}</div>", unsafe_allow_html=True)
                with rc[1]:
                    st.markdown(f"<div style='padding:5px 4px;font-weight:{'900' if is_sel else '600'};color:{'#020025' if is_sel else '#1e293b'};font-size:13px;direction:rtl'>{'🔵' if is_sel else '📍'} {cname}</div>", unsafe_allow_html=True)
                with rc[2]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:12px;color:#3949ab;font-weight:700;direction:rtl'>{jdate}</div>", unsafe_allow_html=True)
                with rc[3]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:12px;color:#64748b;direction:rtl'>{vtime}</div>", unsafe_allow_html=True)
                with rc[4]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:11px;color:#94a3b8;direction:rtl;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{desc}</div>", unsafe_allow_html=True)
                with rc[5]:
                    lbl = "✓" if is_sel else "🔍"
                    if st.button(lbl, key=f"vb_{i}", use_container_width=True,
                                 type="primary" if is_sel else "secondary"):
                        if is_sel:
                            st.session_state.sel_type = None
                            st.session_state.sel_idx  = None
                        else:
                            set_sel('v', i)
                        st.rerun()



    # ─── تب سفارشات ───
    with tab2:
        if orders_df.empty:
            st.info("در این بازه سفارشی ثبت نشده.")
        else:
            st.markdown(f"""<div style='display:flex;gap:8px;margin-bottom:10px;direction:rtl'>
                <span style='background:#f3e5f5;color:#6a1b9a;padding:4px 12px;border-radius:8px;font-size:12px;font-weight:700'>📦 {to_} فاکتور</span>
                <span style='background:#d1fae5;color:#065f46;padding:4px 12px;border-radius:8px;font-size:12px;font-weight:700'>💰 جمع: {fa_num(toa)}</span>
            </div>""", unsafe_allow_html=True)

            st.markdown("""
            <div class='lr-hdr'>
                <div style='flex:0.3'>ردیف</div>
                <div style='flex:2'>نام مشتری</div>
                <div style='flex:1.2'>تاریخ</div>
                <div style='flex:1'>ساعت</div>
                <div style='flex:1.5'>جمع فاکتور</div>
                <div style='flex:0.7'></div>
            </div>
            """, unsafe_allow_html=True)

            for i, (_, order) in enumerate(orders_df.iterrows()):
                jdate  = to_j(order['order_date'])
                otime  = ct(order['order_time'])
                cname  = order['C_Name']
                amt    = fa_num(order['total_amount'])
                is_sel = (st.session_state.sel_type=='o' and st.session_state.sel_idx==i)

                rc = st.columns([0.3, 2, 1.2, 1, 1.5, 0.7])
                with rc[0]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:11px;color:#94a3b8'>{i+1}</div>", unsafe_allow_html=True)
                with rc[1]:
                    st.markdown(f"<div style='padding:5px 4px;font-weight:{'900' if is_sel else '600'};color:{'#020025' if is_sel else '#1e293b'};font-size:13px;direction:rtl'>{'🔵' if is_sel else '📦'} {cname}</div>", unsafe_allow_html=True)
                with rc[2]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:12px;color:#3949ab;font-weight:700;direction:rtl'>{jdate}</div>", unsafe_allow_html=True)
                with rc[3]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:12px;color:#64748b;direction:rtl'>{otime}</div>", unsafe_allow_html=True)
                with rc[4]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:13px;font-weight:800;color:#7b1fa2;direction:rtl'>{amt}</div>", unsafe_allow_html=True)
                with rc[5]:
                    lbl = "✓" if is_sel else "🔍"
                    if st.button(lbl, key=f"ob_{i}", use_container_width=True,
                                 type="primary" if is_sel else "secondary"):
                        if is_sel:
                            st.session_state.sel_type = None
                            st.session_state.sel_idx  = None
                        else:
                            set_sel('o', i)
                        st.rerun()



    # ─── تب دریافت‌ها ───
    with tab3:
        if pays_df.empty:
            st.info("در این بازه دریافتی ثبت نشده.")
        else:
            cash_s  = pays_df[pays_df['payment_type']=='نقدی']['amount'].sum()
            check_s = pays_df[pays_df['payment_type']=='چک']['amount'].sum()
            trans_s = pays_df[pays_df['payment_type']=='حواله']['amount'].sum()

            kc1,kc2,kc3,kc4 = st.columns(4)
            for col,ic2,v,lb,clr,bg in [
                (kc1,"💰",tpa,    "جمع کل","#1b5e20","#e8f5e9"),
                (kc2,"💵",cash_s, "نقدی",  "#0d47a1","#e3f2fd"),
                (kc3,"📋",check_s,"چک",    "#880e4f","#fce4ec"),
                (kc4,"🏦",trans_s,"حواله", "#e65100","#fff3e0"),
            ]:
                with col:
                    st.markdown(f"""<div class='kpi-box' style='border-color:{clr};background:{bg};padding:12px 8px'>
                        <div style='font-size:20px'>{ic2}</div>
                        <div style='font-size:17px;font-weight:900;color:{clr}'>{fa_num(v)}</div>
                        <div style='font-size:11px;color:#64748b;font-weight:600'>{lb}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("""
            <div class='lr-hdr'>
                <div style='flex:0.3'>ردیف</div>
                <div style='flex:2'>نام مشتری</div>
                <div style='flex:1.2'>تاریخ</div>
                <div style='flex:1'>ساعت</div>
                <div style='flex:0.9'>نوع</div>
                <div style='flex:1.5'>مبلغ</div>
                <div style='flex:0.7'></div>
            </div>
            """, unsafe_allow_html=True)

            for i, (_, pay) in enumerate(pays_df.iterrows()):
                jdate  = to_j(pay['payment_date'])
                ptime  = ct(pay['payment_time'])
                ptype  = pay.get('payment_type','')
                icon   = "💵" if ptype=="نقدی" else "📋" if ptype=="چک" else "🏦"
                bg_t   = "#e3f2fd" if ptype=="نقدی" else "#fce4ec" if ptype=="چک" else "#fff3e0"
                fc_t   = "#0d47a1" if ptype=="نقدی" else "#880e4f" if ptype=="چک" else "#e65100"
                is_sel = (st.session_state.sel_type=='p' and st.session_state.sel_idx==i)

                rc = st.columns([0.3, 2, 1.2, 1, 0.9, 1.5, 0.7])
                with rc[0]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:11px;color:#94a3b8'>{i+1}</div>", unsafe_allow_html=True)
                with rc[1]:
                    st.markdown(f"<div style='padding:5px 4px;font-weight:{'900' if is_sel else '600'};color:{'#020025' if is_sel else '#1e293b'};font-size:13px;direction:rtl'>{'🔵' if is_sel else icon+' '}{pay['C_Name']}</div>", unsafe_allow_html=True)
                with rc[2]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:12px;color:#3949ab;font-weight:700;direction:rtl'>{jdate}</div>", unsafe_allow_html=True)
                with rc[3]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:12px;color:#64748b;direction:rtl'>{ptime}</div>", unsafe_allow_html=True)
                with rc[4]:
                    st.markdown(f"<div style='padding:8px 4px'><span style='background:{bg_t};color:{fc_t};padding:3px 8px;border-radius:7px;font-size:11px;font-weight:700'>{ptype}</span></div>", unsafe_allow_html=True)
                with rc[5]:
                    st.markdown(f"<div style='padding:5px 4px;font-size:13px;font-weight:800;color:#1b5e20;direction:rtl'>{fa_num(pay['amount'])}</div>", unsafe_allow_html=True)
                with rc[6]:
                    lbl = "✓" if is_sel else "🔍"
                    if st.button(lbl, key=f"pb_{i}", use_container_width=True,
                                 type="primary" if is_sel else "secondary"):
                        if is_sel:
                            st.session_state.sel_type = None
                            st.session_state.sel_idx  = None
                        else:
                            set_sel('p', i)
                        st.rerun()




# ══════════════════════════════════════════════════════
# ستون جزئیات سمت راست
# ══════════════════════════════════════════════════════
if has_detail and detail_col is not None:
    t   = st.session_state.sel_type
    idx = st.session_state.sel_idx

    with detail_col:

        st.markdown("""
        <style>
        .dp-wrap {
            background: white; border-radius: 14px;
            overflow: hidden; border: 1.5px solid #dde3f0;
            box-shadow: 0 6px 24px rgba(2,0,37,.12);
            direction: rtl; font-family: 'Vazirmatn',Tahoma,sans-serif;
        }
        .dp-head {
            padding: 13px 15px; color: white;
        }
        .dp-title { font-size: 13px; font-weight: 900; margin-bottom: 2px; }
        .dp-sub   { font-size: 11px; opacity: .75; }
        .dp-body  { padding: 12px 12px 8px; }
        .dp-cell  {
            background: #f8fafc; border-radius: 9px;
            padding: 8px 11px; margin-bottom: 7px;
            border: 1px solid #e8edf5; direction: rtl;
        }
        .dp-lbl { font-size: 10px; font-weight: 700; color: #94a3b8; margin-bottom: 2px; }
        .dp-val { font-size: 13px; font-weight: 700; color: #1e293b; word-break: break-all; }
        .dp-section {
            font-size: 11px; font-weight: 800; color: #020025;
            border-top: 1px solid #f0f2fa;
            padding: 7px 0 5px; margin-top: 2px;
        }
        .dp-img {
            width: 100%; border-radius: 9px;
            border: 2px solid #e2e8f0; cursor: zoom-in;
            display: block; margin-top: 5px;
            transition: border-color .2s;
        }
        .dp-img:hover { border-color: #4f6ef7; }
        .dp-extra {
            border-radius: 9px; padding: 9px 11px;
            margin-bottom: 7px; direction: rtl;
            font-size: 12px; line-height: 1.9;
        }
        .dp-item {
            background: #f8fafc; border-radius: 8px;
            padding: 7px 10px; margin-bottom: 5px;
            border: 1px solid #e8edf5; direction: rtl;
        }
        .dp-item-name { font-size: 12px; font-weight: 700; color: #1e293b; margin-bottom: 3px; }
        .dp-item-sub  { display: flex; justify-content: space-between; font-size: 11px; color: #64748b; }
        .dp-total {
            background: #f3e5f5; border-radius: 8px;
            padding: 9px 12px; display: flex;
            justify-content: space-between; margin-top: 4px;
            direction: rtl;
        }
        </style>
        """, unsafe_allow_html=True)

        # ─── ویزیت ───
        if t == 'v' and idx < len(visits_df):
            row   = visits_df.iloc[idx]
            jdate = to_j(row['visit_date'])
            vtime = ct(row['visit_time'])
            sp    = img(row.get('selfie_path',''))

            # هد
            st.markdown(
                "<div class='dp-wrap'>"
                "<div class='dp-head' style='background:linear-gradient(135deg,#020025,#3949ab)'>"
                f"<div class='dp-title'>📍 {row['C_Name']}</div>"
                f"<div class='dp-sub'>{jdate} · {vtime}</div>"
                "</div><div class='dp-body'>"
                f"<div class='dp-cell'><div class='dp-lbl'>کد مشتری</div><div class='dp-val'>{row['customer_code']}</div></div>"
                f"<div class='dp-cell'><div class='dp-lbl'>تاریخ</div><div class='dp-val'>{jdate}</div></div>"
                f"<div class='dp-cell'><div class='dp-lbl'>ساعت</div><div class='dp-val'>{vtime}</div></div>"
                f"<div class='dp-cell'><div class='dp-lbl'>توضیحات</div><div class='dp-val' style='font-size:12px'>{row.get('description','') or '—'}</div></div>",
                unsafe_allow_html=True
            )
            if sp:
                st.markdown(
                    "<div class='dp-section'>📸 سلفی حضور</div>"
                    f"<a href='{sp}' target='_blank'><img class='dp-img' src='{sp}'></a>"
                    "<div style='text-align:center;font-size:10px;color:#94a3b8;margin-top:3px;direction:rtl'>کلیک برای بزرگنمایی</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    "<div class='dp-cell' style='text-align:center;color:#94a3b8;font-size:12px'>📷 بدون سلفی</div>",
                    unsafe_allow_html=True
                )
            st.markdown("</div></div>", unsafe_allow_html=True)

        # ─── سفارش ───
        elif t == 'o' and idx < len(orders_df):
            order = orders_df.iloc[idx]
            jdate = to_j(order['order_date'])
            otime = ct(order['order_time'])

            st.markdown(
                "<div class='dp-wrap'>"
                "<div class='dp-head' style='background:linear-gradient(135deg,#020025,#7b1fa2)'>"
                f"<div class='dp-title'>📦 {order['C_Name']}</div>"
                f"<div class='dp-sub'>{jdate} · {fa_num(order['total_amount'])}</div>"
                "</div><div class='dp-body'>"
                f"<div class='dp-cell'><div class='dp-lbl'>تاریخ</div><div class='dp-val'>{jdate}</div></div>"
                f"<div class='dp-cell'><div class='dp-lbl'>ساعت</div><div class='dp-val'>{otime}</div></div>"
                f"<div class='dp-cell'><div class='dp-lbl'>جمع فاکتور</div>"
                f"<div class='dp-val' style='color:#7b1fa2;font-size:15px'>{fa_num(order['total_amount'])}</div></div>"
                "<div class='dp-section'>📋 اقلام سفارش</div>",
                unsafe_allow_html=True
            )
            try:
                conn_it = pyodbc.connect(
                    f'DRIVER={{SQL Server}};SERVER={SERVER_NAME};DATABASE=tracking;Trusted_Connection=yes;'
                )
                its = pd.read_sql("""
                    SELECT ISNULL(a.A_Name,oi.article_code) AS nm,
                           CAST(oi.quantity AS FLOAT) AS qty,
                           CAST(oi.price AS BIGINT)   AS prc,
                           CAST(oi.quantity*oi.price AS BIGINT) AS tot
                    FROM order_items oi
                    LEFT JOIN dejavuDB1.dbo.article a ON oi.article_code=a.A_Code
                    WHERE oi.order_id=?
                """, conn_it, params=(int(order['id']),))
                conn_it.close()
                if not its.empty:
                    items_html = ""
                    for _, it in its.iterrows():
                        items_html += (
                            "<div class='dp-item'>"
                            f"<div class='dp-item-name'>{it['nm']}</div>"
                            "<div class='dp-item-sub'>"
                            f"<span>{it['qty']:g} عدد × {it['prc']:,}</span>"
                            f"<span style='font-weight:800;color:#7b1fa2'>{it['tot']:,} ریال</span>"
                            "</div></div>"
                        )
                    total_html = (
                        "<div class='dp-total'>"
                        "<span style='color:#64748b;font-weight:600;font-size:12px'>جمع کل:</span>"
                        f"<span style='color:#7b1fa2;font-weight:900;font-size:14px'>{fa_num(order['total_amount'])}</span>"
                        "</div>"
                    )
                    st.markdown(items_html + total_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"خطا: {e}")
            st.markdown("</div></div>", unsafe_allow_html=True)

        # ─── دریافت ───
        elif t == 'p' and idx < len(pays_df):
            pay   = pays_df.iloc[idx]
            jdate = to_j(pay['payment_date'])
            ptime = ct(pay['payment_time'])
            ptype = pay.get('payment_type','')
            icon  = "💵" if ptype=="نقدی" else "📋" if ptype=="چک" else "🏦"
            clr_p = "#0d47a1" if ptype=="نقدی" else "#880e4f" if ptype=="چک" else "#e65100"
            chk_i = img(pay.get('check_image_path',''))
            tr_i  = img(pay.get('transfer_image_path',''))

            st.markdown(
                "<div class='dp-wrap'>"
                f"<div class='dp-head' style='background:linear-gradient(135deg,#020025,{clr_p})'>"
                f"<div class='dp-title'>{icon} {pay['C_Name']}</div>"
                f"<div class='dp-sub'>{jdate} · {ptype}</div>"
                "</div><div class='dp-body'>"
                f"<div class='dp-cell'><div class='dp-lbl'>مشتری</div><div class='dp-val'>{pay['C_Name']}</div></div>"
                f"<div class='dp-cell'><div class='dp-lbl'>تاریخ</div><div class='dp-val'>{jdate}</div></div>"
                f"<div class='dp-cell'><div class='dp-lbl'>ساعت</div><div class='dp-val'>{ptime}</div></div>"
                f"<div class='dp-cell'><div class='dp-lbl'>مبلغ دریافتی</div>"
                f"<div class='dp-val' style='color:#1b5e20;font-size:15px'>{fa_num(pay['amount'])}</div></div>",
                unsafe_allow_html=True
            )

            # اطلاعات چک یا حواله
            if ptype == "چک":
                due = to_j(pay.get('check_due_date')) if pay.get('check_due_date') else '—'
                st.markdown(
                    "<div class='dp-section'>📋 اطلاعات چک</div>"
                    "<div class='dp-extra' style='background:#fce4ec;border:1px solid #f48fb1'>"
                    f"<b>شماره چک:</b> {pay.get('check_number','—')}<br>"
                    f"<b>شماره صیادی:</b> {pay.get('check_sayyadi','—')}<br>"
                    f"<b>تاریخ سررسید:</b> {due}"
                    "</div>",
                    unsafe_allow_html=True
                )
            elif ptype == "حواله":
                st.markdown(
                    "<div class='dp-section'>🏦 اطلاعات حواله</div>"
                    "<div class='dp-extra' style='background:#e3f2fd;border:1px solid #90caf9'>"
                    f"<b>حساب مقصد:</b> {pay.get('transfer_account','—')}<br>"
                    f"<b>شماره پیگیری:</b> {pay.get('tracking_number','—')}"
                    "</div>",
                    unsafe_allow_html=True
                )

            # عکس‌ها
            if chk_i:
                st.markdown(
                    "<div class='dp-section'>📸 عکس چک</div>"
                    f"<a href='{chk_i}' target='_blank'><img class='dp-img' src='{chk_i}'></a>",
                    unsafe_allow_html=True
                )
            if tr_i:
                st.markdown(
                    "<div class='dp-section'>📸 رسید حواله</div>"
                    f"<a href='{tr_i}' target='_blank'><img class='dp-img' src='{tr_i}'></a>",
                    unsafe_allow_html=True
                )

            st.markdown("</div></div>", unsafe_allow_html=True)

        # دکمه بستن
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✕ بستن پانل", use_container_width=True):
            st.session_state.sel_type = None
            st.session_state.sel_idx  = None
            st.rerun()



def make_excel_visits():
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as w:
        wb = w.book
        hf = wb.add_format({'bold':True,'bg_color':'#020025','font_color':'white','align':'right','font_name':'Tahoma','border':1})
        cf = wb.add_format({'align':'right','font_name':'Tahoma','border':1})
        if not visits_df.empty:
            ws = wb.add_worksheet('ویزیت‌ها'); ws.right_to_left()
            hdrs = ['نام مشتری','کد مشتری','تاریخ شمسی','ساعت','توضیحات']
            for ci,h in enumerate(hdrs): ws.write(0,ci,h,hf); ws.set_column(ci,ci,20)
            for ri,(_,row) in enumerate(visits_df.iterrows()):
                vals = [row['C_Name'],row['customer_code'],to_j(row['visit_date']),ct(row['visit_time']),row.get('description','')]
                for ci,v in enumerate(vals): ws.write(ri+1,ci,str(v) if v else '',cf)
    return out.getvalue()

def make_excel_orders():
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as w:
        wb = w.book
        hf = wb.add_format({'bold':True,'bg_color':'#7b1fa2','font_color':'white','align':'right','font_name':'Tahoma','border':1})
        cf = wb.add_format({'align':'right','font_name':'Tahoma','border':1})
        nf = wb.add_format({'align':'right','font_name':'Tahoma','border':1,'num_format':'#,##0'})
        if not orders_df.empty:
            ws = wb.add_worksheet('سفارشات'); ws.right_to_left()
            hdrs = ['نام مشتری','کد مشتری','تاریخ شمسی','ساعت','جمع فاکتور (ریال)']
            for ci,h in enumerate(hdrs): ws.write(0,ci,h,hf); ws.set_column(ci,ci,20)
            for ri,(_,row) in enumerate(orders_df.iterrows()):
                ws.write(ri+1,0,row['C_Name'],cf)
                ws.write(ri+1,1,row['customer_code'],cf)
                ws.write(ri+1,2,to_j(row['order_date']),cf)
                ws.write(ri+1,3,ct(row['order_time']),cf)
                ws.write(ri+1,4,float(row['total_amount']),nf)
    return out.getvalue()

def make_excel_pays():
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as w:
        wb = w.book
        hf = wb.add_format({'bold':True,'bg_color':'#1b5e20','font_color':'white','align':'right','font_name':'Tahoma','border':1})
        cf = wb.add_format({'align':'right','font_name':'Tahoma','border':1})
        nf = wb.add_format({'align':'right','font_name':'Tahoma','border':1,'num_format':'#,##0'})
        p_all = qry("""
            SELECT ISNULL(c.C_Name,p.customer_code) AS [نام مشتری],
                   p.customer_code AS [کد مشتری],
                   CONVERT(VARCHAR,p.payment_date,23) AS [تاریخ],
                   CONVERT(VARCHAR,p.payment_time,108) AS [ساعت],
                   p.payment_type AS [نوع دریافت],
                   p.amount AS [مبلغ ریال],
                   ISNULL(p.check_number,'') AS [شماره چک],
                   ISNULL(p.check_sayyadi,'') AS [شماره صیادی],
                   ISNULL(p.transfer_account,'') AS [حساب مقصد],
                   ISNULL(p.tracking_number,'') AS [شماره پیگیری]
            FROM payments p
            LEFT JOIN dejavuDB1.dbo.customer c ON p.customer_code=c.C_Code
            WHERE p.visitor_id=? AND p.payment_date BETWEEN ? AND ?
            ORDER BY p.payment_date,p.payment_time
        """, (sel_vid,g0,g1))
        if not p_all.empty:
            ws = wb.add_worksheet('دریافت‌ها'); ws.right_to_left()
            cols = list(p_all.columns)
            cols.insert(1,'تاریخ شمسی')
            for ci,h in enumerate(cols): ws.write(0,ci,h,hf); ws.set_column(ci,ci,20)
            for ri,(_,row) in enumerate(p_all.iterrows()):
                ws.write(ri+1,0,str(row.get('نام مشتری','')),cf)
                ws.write(ri+1,1,to_j(str(row.get('تاریخ',''))),cf)
                for ci2,col in enumerate(p_all.columns[1:], 2):
                    v = row.get(col,'')
                    if col=='مبلغ ریال':
                        try: ws.write(ri+1,ci2,float(v),nf)
                        except: ws.write(ri+1,ci2,'',cf)
                    else:
                        ws.write(ri+1,ci2,str(v) if v else '',cf)
    return out.getvalue()


ec1, ec2, ec3 = st.columns(3)
with ec1:
    st.download_button("📥 Excel ویزیت‌ها", data=make_excel_visits(),
        file_name=f"Visits_{j0.strftime('%Y%m%d')}_{j1.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.ms-excel", use_container_width=True)
with ec2:
    st.download_button("📥 Excel سفارشات", data=make_excel_orders(),
        file_name=f"Orders_{j0.strftime('%Y%m%d')}_{j1.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.ms-excel", use_container_width=True)
with ec3:
    st.download_button("📥 Excel دریافت‌ها", data=make_excel_pays(),
        file_name=f"Payments_{j0.strftime('%Y%m%d')}_{j1.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.ms-excel", use_container_width=True)

st.markdown(f"""
<div class='dash-footer'>
    <a href='https://peecha.ir' target='_blank'>🌐 peecha.ir</a>
    &nbsp;|&nbsp; پیچا ویزیت | PeechaVisit © ۱۴۰۵ &nbsp;|&nbsp; نسخه ۵.۱
</div>
""", unsafe_allow_html=True)
