# ui_theme.py - پیچا ویزیت | ظاهر مشترک پنل مدیریت و داشبورد (هم‌سبک اپ اندروید)
# ════════════════════════════════════════════════
# رنگ‌ها و اجزای ساده و تخت: نوار بالای سرمه‌ای، دکمه و فیلد با گوشهٔ گرد،
# تب‌ها به شکل «دکمه‌های کنار هم» مثل اپ. فونت از ui_font.py می‌آید.
# ════════════════════════════════════════════════
from config import APP

BRAND = APP.get("PRIMARY_COLOR", "#020025")
PRIMARY = "#3b5bdb"


def theme_css() -> str:
    return f"""<style>
:root {{ --brand:{BRAND}; --primary:{PRIMARY}; --soft:#edf1ff; --bg:#f4f5f8; --card:#fff;
         --border:#dfe3ea; --text:#17202e; --muted:#6b7686; }}
.stApp {{ background:var(--bg); direction:rtl; }}
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display:none !important; }}
/* بلوک‌هایی که فقط <style> دارند جا نگیرند (CSS داخلشان همچنان اعمال می‌شود) */
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style):not(:has(div.pv-bar, .pv-login-card, .gal, .pv-notes)) {{ display:none; }}
.block-container {{ padding:0 18px 24px !important; max-width:100% !important; }}
p, label, .stMarkdown, .stCaption, .stAlert {{ direction:rtl; text-align:right; }}

/* نوار بالا */
.pv-bar {{ background:var(--brand); color:#fff; margin:0 -18px 12px; padding:10px 18px;
           display:flex; align-items:center; gap:12px; flex-wrap:wrap; min-height:52px; }}
.pv-bar .t {{ font-size:17px; font-weight:800; white-space:nowrap; }}
.pv-bar .s {{ font-size:12px; opacity:.75; white-space:nowrap; }}
.pv-bar .sp {{ flex:1; }}
.pv-bar .chip {{ background:rgba(255,255,255,.12); border-radius:20px; padding:4px 12px; font-size:12px;
                 font-weight:600; white-space:nowrap; }}
.pv-bar .chip b {{ font-size:14px; margin-left:3px; }}

/* دکمه‌ها و فیلدها */
.stButton > button, .stDownloadButton > button, .stLinkButton > a, [data-testid="stPopover"] > button,
.stFormSubmitButton > button {{
    border-radius:10px !important; border:1px solid var(--border) !important; font-weight:700 !important;
    box-shadow:none !important; min-height:40px; }}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"],
.stFormSubmitButton > button[kind="primary"] {{
    background:var(--primary) !important; border-color:var(--primary) !important; color:#fff !important; }}
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {{ border-radius:10px !important; }}

/* تب‌ها مثل دکمه‌های کنار هم در اپ */
.stTabs [data-baseweb="tab-list"] {{ background:#e7e9ef; border-radius:12px; padding:4px; gap:4px; }}
.stTabs [data-baseweb="tab"] {{ border-radius:9px; padding:6px 14px; font-weight:700; color:var(--muted); height:auto; }}
.stTabs [aria-selected="true"] {{ background:#fff !important; color:var(--text) !important;
                                  box-shadow:0 1px 2px rgba(16,24,40,.12); }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none; }}

/* کارت و جدول */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:12px !important; }}
[data-testid="stDataFrame"] {{ border:1px solid var(--border); border-radius:12px; overflow:hidden; background:#fff; }}
[data-testid="stExpander"] details {{ border-radius:12px !important; border-color:var(--border) !important; background:#fff; }}
</style>"""


def app_bar(title: str, subtitle: str = "", chips: list[str] | None = None) -> str:
    chips_html = "".join(f"<span class='chip'>{c}</span>" for c in (chips or []))
    sub = f"<span class='s'>{subtitle}</span>" if subtitle else ""
    return f"<div class='pv-bar'><span class='t'>{title}</span>{sub}<span class='sp'></span>{chips_html}</div>"
