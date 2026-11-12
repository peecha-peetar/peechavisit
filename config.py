# config.py - پیچا ویزیت | تنظیمات مرکزی
# ════════════════════════════════════════════════
# مقادیر پیش‌فرض اینجاست — بقیه فایل‌ها از اینجا می‌خونن
# تغییرات از «پنل مدیریت ← تنظیمات» در settings.json ذخیره می‌شوند
# و روی این مقادیر اعمال می‌شوند (settings.json اولویت دارد)
# بعد از تغییر: سرویس‌ها را ری‌استارت کنید
# ════════════════════════════════════════════════
import json as _json
import os as _os
import copy as _copy

# ── شبکه و سرور ──
NETWORK = {
    "SERVER_NAME":    "SERWIN\\RAD",          # نام SQL Server
    "SERVER_IP":      "10.165.254.180",        # ← آی‌پی سرور (اینجا عوض کنید)
    "FLASK_HOST":     "0.0.0.0",
    "FLASK_PORT":     5000,
    "PWA_PORT":       8000,
    "DASHBOARD_PORT": 8501,
    "ADMIN_PORT":     8502,
    "DEBUG":          False,
}

# ── دیتابیس‌ها ──
DATABASES = {
    "TRACKING_DB": "tracking",
    "SALES_DB":    "dejavuDB1",
    "DRIVER":      "SQL Server",
    "TIMEOUT":     30,
    # خالی = ورود ویندوزی (Trusted_Connection) — در غیر این صورت ورود SQL
    "USER":        "",
    "PASSWORD":    "",
    # پارامترهای اضافهٔ اتصال، مثلاً "TrustServerCertificate=yes"
    "EXTRA":       "",
}

# ── برنامه ──
APP = {
    "NAME":          "پیچا ویزیت",
    "NAME_EN":       "PeechaVisit",
    "VERSION":       "3.5",
    "WEBSITE":       "https://peecha.ir",
    "PRIMARY_COLOR": "#020025",
    "ACCENT_COLOR":  "#4f6ef7",
}

# ── امنیت ──
SECURITY = {
    "SESSION_SECRET":     "peecha-secret-change-me-2025",  # ← حتماً عوض کنید
    "SESSION_HOURS":      10,
    "MAX_LOGIN_ATTEMPTS": 5,
    "LOCKOUT_MINUTES":    30,
    "PASSWORD_MIN_LEN":   6,
}

# ── مسیرها ──
PATHS = {
    "SELFIES_DIR":   "static/selfies",
    "CHECKS_DIR":    "static/checks",
    "TRANSFERS_DIR": "static/transfers",
    "LOGS_DIR":      "logs",
}

# ── اپ موبایل ──
# از «پنل مدیریت ← تنظیمات» قابل تغییر است و بدون ری‌استارت روی گوشی‌ها
# اعمال می‌شود (با بروزرسانی لیست در اپ)
MOBILE = {
    "REQUIRE_SELFIE": True,    # سلفی برای ثبت ویزیت اجباری باشد
    "SHOW_PRICE":     True,    # قیمت کالا در اپ نمایش داده شود
    "SHOW_STOCK":     True,    # موجودی کالا در اپ نمایش داده شود
    "ONLY_IN_STOCK":  False,   # فقط کالاهای دارای موجودی در لیست بیایند
    "ALLOW_OVERSELL": False,   # سفارش بیشتر از موجودی مجاز باشد
    "PEER_MESSAGES":  True,    # ویزیتورها همدیگر را در پیام‌ها ببینند (خاموش = فقط مدیران)
}

# ── GPS ──
GPS = {
    "MAX_ACCURACY_METERS": 30,     # تا رسیدن به این دقت (متر) منتظر GPS می‌ماند
    "TIMEOUT_SECONDS":     25,     # حداکثر زمان انتظار برای GPS
    "CACHE_SECONDS":       0,
}


# ── کاتالوگ و عکس کالا (از دیتابیس فروش) ──
# بدون ری‌استارت اعمال می‌شود
CATALOG = {
    # جدول جدای عکس‌ها (مثل HLOpicturs)؛ اگر در دیتابیس نباشد از ستونی در جدول article استفاده می‌شود
    "IMAGE_TABLE":    "HLOPictures",   # اگر با این نام نبود، جدولی با ستون‌های کد/مسیر/عکس پیدا می‌شود
    "IMAGE_CODE_COL": "Code",          # کد کالا در جدول عکس
    "IMAGE_PATH_COL": "PicturePath",   # مسیر فایل عکس
    "IMAGE_BLOB_COL": "Picture",       # خود عکس داخل دیتابیس (نوع image)
    "IMAGE_MODE":     "auto",          # path = مسیر فایل · db = داخل دیتابیس · auto = مسیر، وگرنه دیتابیس
    "IMAGE_TYPE":     "1",             # Type در جدول عکس: ۱ = کالا، ۲ = مشتری (خالی = همه)
    "CUSTOMER_TYPE":  "2",             # Type عکس طرف حساب (مشتری) برای پروفایل در اپ و داشبورد
    "IMAGE_COLUMN":   "",              # حالت ستون article: ستون مسیر عکس (خالی = تشخیص خودکار)
    "IMAGE_DIR":      "",              # پوشهٔ پایه برای مسیرهای نسبی یا فقط نام فایل
}


# ════════════════════════════════════════════════
# settings.json — تنظیمات ذخیره‌شده از پنل مدیریت
# ════════════════════════════════════════════════
from paths import DATA_DIR as _DATA_DIR
SETTINGS_FILE = _os.path.join(_DATA_DIR, "settings.json")

_SECTIONS = {
    "NETWORK": NETWORK, "DATABASES": DATABASES, "APP": APP,
    "SECURITY": SECURITY, "PATHS": PATHS, "GPS": GPS, "MOBILE": MOBILE, "CATALOG": CATALOG,
}
DEFAULTS = _copy.deepcopy(_SECTIONS)


def _coerce(default, value):
    """نوع مقدار ذخیره‌شده را هم‌نوع مقدار پیش‌فرض می‌کند"""
    if isinstance(default, bool):
        return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes")
    if isinstance(default, int):
        return int(value)
    return str(value)


def read_settings_file() -> dict:
    """محتوای settings.json (فقط بخش‌ها و کلیدهای شناخته‌شده)"""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            raw = _json.load(f)
    except (OSError, ValueError):
        return {}
    clean = {}
    for sec, values in (raw or {}).items():
        if sec in DEFAULTS and isinstance(values, dict):
            for k, v in values.items():
                if k in DEFAULTS[sec]:
                    try:
                        clean.setdefault(sec, {})[k] = _coerce(DEFAULTS[sec][k], v)
                    except (TypeError, ValueError):
                        pass
    return clean


def current_settings() -> dict:
    """پیش‌فرض‌ها + settings.json (خواندن تازه از دیسک)"""
    merged = _copy.deepcopy(DEFAULTS)
    for sec, values in read_settings_file().items():
        merged[sec].update(values)
    return merged


def save_settings(changes: dict) -> None:
    """ذخیرهٔ تغییرات در settings.json — فقط مقادیر متفاوت با پیش‌فرض نگه داشته می‌شوند"""
    data = read_settings_file()
    for sec, values in changes.items():
        for k, v in values.items():
            if sec not in DEFAULTS or k not in DEFAULTS[sec]:
                continue
            v = _coerce(DEFAULTS[sec][k], v)
            if v == DEFAULTS[sec][k]:
                data.get(sec, {}).pop(k, None)
            else:
                data.setdefault(sec, {})[k] = v
    data = {s: v for s, v in data.items() if v}
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
    _os.replace(tmp, SETTINGS_FILE)


def reset_settings() -> None:
    """بازگشت به مقادیر پیش‌فرض"""
    try:
        _os.remove(SETTINGS_FILE)
    except FileNotFoundError:
        pass


# اعمال settings.json روی مقادیر بالا
for _sec, _values in read_settings_file().items():
    _SECTIONS[_sec].update(_values)
