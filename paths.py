# paths.py - پیچا ویزیت | مسیر فایل‌های برنامه و داده
# ════════════════════════════════════════════════
# RES_DIR  : فایل‌های فقط‌خواندنی همراه برنامه (فونت، صفحات اپ)
# DATA_DIR : داده‌های قابل تغییر (settings.json، عکس‌ها، لاگ)
#
# حالت توسعه (اجرای .py) → هر دو پوشهٔ همین پروژه است.
# نسخهٔ نصبی (exe)       → RES_DIR داخل برنامه، DATA_DIR در
#                           C:\ProgramData\PeechaVisit (یا متغیر PEECHA_HOME)
# ════════════════════════════════════════════════
import os
import sys

FROZEN = bool(getattr(sys, "frozen", False))
_HERE = os.path.dirname(os.path.abspath(__file__))

RES_DIR = getattr(sys, "_MEIPASS", _HERE)

if os.environ.get("PEECHA_HOME"):
    DATA_DIR = os.environ["PEECHA_HOME"]
elif FROZEN:
    DATA_DIR = os.path.join(os.environ.get("PROGRAMDATA") or os.path.dirname(sys.executable), "PeechaVisit")
else:
    DATA_DIR = _HERE

STATIC_DIR = os.path.join(DATA_DIR, "static")
LOG_DIR = os.path.join(DATA_DIR, "logs")

for _d in (DATA_DIR, STATIC_DIR, LOG_DIR,
           *(os.path.join(STATIC_DIR, x) for x in ("selfies", "checks", "transfers"))):
    try:
        os.makedirs(_d, exist_ok=True)
    except OSError:
        pass
