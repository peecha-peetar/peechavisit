# ui_font.py - پیچا ویزیت | فونت وزیرمتن برای داشبورد و پنل مدیریت
# ════════════════════════════════════════════════
# فونت از pwa_client/fonts خوانده و داخل صفحه جاسازی می‌شود؛
# بدون نیاز به اینترنت یا Google Fonts.
# ════════════════════════════════════════════════
import base64
import os
from functools import lru_cache

_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "pwa_client", "fonts", "Vazirmatn-Variable.woff2")


@lru_cache(maxsize=1)
def font_css() -> str:
    """<style> با @font-face وزیرمتن و اعمال آن روی همهٔ صفحه (به‌جز آیکن‌های Streamlit)"""
    try:
        with open(_FONT, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        face = (f"@font-face{{font-family:'Vazirmatn';font-weight:100 900;font-display:swap;"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
    except OSError:
        face = ""
    return f"""<style>
{face}
html, body, .stApp, .stApp * {{ font-family: 'Vazirmatn', Tahoma, sans-serif !important; }}
.stApp [data-testid="stIconMaterial"], .stApp .material-symbols-rounded {{
    font-family: 'Material Symbols Rounded' !important;
}}
</style>"""
