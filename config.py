# config.py - پیچا ویزیت | تنظیمات مرکزی
# ════════════════════════════════════════════════
# فقط این فایل رو ویرایش کنید — بقیه فایل‌ها از اینجا می‌خونن
# بعد از تغییر: سرویس‌ها را ری‌استارت کنید
# ════════════════════════════════════════════════

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
}

# ── برنامه ──
APP = {
    "NAME":          "پیچا ویزیت",
    "NAME_EN":       "PeechaVisit",
    "VERSION":       "2.2",
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

# ── GPS ──
GPS = {
    "MAX_ACCURACY_METERS": 100,
    "TIMEOUT_SECONDS":     12,
    "CACHE_SECONDS":       0,
}
