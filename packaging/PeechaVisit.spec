# PeechaVisit.spec - ساخت برنامهٔ اجرایی پیچا ویزیت با PyInstaller
# ════════════════════════════════════════════════
# اجرا از ریشهٔ پروژه:   pyinstaller --noconfirm packaging/PeechaVisit.spec
# خروجی:                 dist/PeechaVisit/PeechaVisit.exe
#
# کد پروژه فقط به شکل کامپایل‌شده (bytecode) داخل برنامه قرار می‌گیرد؛
# هیچ فایل .py پروژه کنار برنامه نیست.
# ════════════════════════════════════════════════
import os
from PyInstaller.utils.hooks import (collect_data_files, collect_dynamic_libs,
                                     collect_submodules, copy_metadata)

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# ماژول‌های پروژه (داشبورد و پنل مدیریت با runpy اجرا می‌شوند، پس صریح اضافه می‌شوند)
PROJECT = ["app", "dashboard", "admin", "audit", "auth", "config", "db", "mobile_rules",
           "panel_auth", "paths", "perms", "report", "ui_font", "ui_theme", "create_tables",
           "peecha_server", "catalog"]

datas = [
    (os.path.join(ROOT, "pwa_client"), "pwa_client"),
    (os.path.join(ROOT, "fonts"), "fonts"),
    (os.path.join(ROOT, ".streamlit", "config.toml"), ".streamlit"),
]
binaries = []
hiddenimports = list(PROJECT) + ["waitress", "pyodbc", "jdatetime", "xlsxwriter", "PIL.Image"]

for pkg in ("streamlit", "streamlit_folium", "folium", "branca", "fpdf", "uharfbuzz"):
    # فقط فایل‌های داده (بدون سورس .py کتابخانه‌ها) + زیرماژول‌ها به شکل کامپایل‌شده
    datas += collect_data_files(pkg)
    binaries += collect_dynamic_libs(pkg)
    hiddenimports += collect_submodules(pkg, filter=lambda n: ".tests" not in n and ".testing" not in n)
for pkg in ("streamlit", "streamlit-folium", "folium", "branca", "fpdf2", "pandas", "numpy",
            "pyarrow", "altair", "jdatetime", "flask", "waitress"):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

a = Analysis(
    [os.path.join(ROOT, "peecha_server.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "notebook", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    # حالت UTF-8 پایتون: متن فارسی در لاگ‌ها و خروجی بدون خطای encoding
    [("X utf8_mode=1", None, "OPTION")],
    exclude_binaries=True,
    name="PeechaVisit",
    console=True,
    icon=os.path.join(SPECPATH, "peecha.ico") if os.path.exists(os.path.join(SPECPATH, "peecha.ico")) else None,
    version=os.path.join(SPECPATH, "version.txt") if os.path.exists(os.path.join(SPECPATH, "version.txt")) else None,
)

# ── آیکون کنار ساعت ویندوز (بدون پنجرهٔ سیاه) ──
t = Analysis(
    [os.path.join(ROOT, "tray_app.py")],
    pathex=[ROOT],
    hiddenimports=["pystray", "pystray._win32", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont", "ui_font"],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "streamlit", "pandas", "pyarrow", "numpy"],
    noarchive=False,
)
tpyz = PYZ(t.pure)
tray = EXE(
    tpyz,
    t.scripts,
    [("X utf8_mode=1", None, "OPTION")],
    exclude_binaries=True,
    name="PeechaVisitTray",
    console=False,
    icon=os.path.join(SPECPATH, "peecha.ico") if os.path.exists(os.path.join(SPECPATH, "peecha.ico")) else None,
)

coll = COLLECT(exe, tray, a.binaries, t.binaries, a.datas, t.datas, name="PeechaVisit")
