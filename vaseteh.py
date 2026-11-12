# vaseteh.py - پیچا ویزیت | اتصال کاربر اپ به «واسطه / ویزیتور» نرم‌افزار فروش
# ════════════════════════════════════════════════
# در نرم‌افزار فروش، ویزیتور (واسطه) خودش یک ردیف در جدول customer است با Vaseteh = True
# و مشتریان هر واسطه در جدول CustomerVaseteh (C_Code ← Vaseteh_Code) هستند؛
# یک مشتری می‌تواند چند واسطه داشته باشد.
#
# در پنل مدیریت به هر کاربر اپ یک یا چند کد واسطه داده می‌شود (ستون visitors.sales_codes)
# و اپ فقط مشتریان همان واسطه‌ها را می‌گیرد. تنظیمات: بخش VASETEH (بدون ری‌استارت).
# ════════════════════════════════════════════════
import re
import time

import config
from db import get_conn

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_cache = {}


def _fa(v) -> str:
    return (v or "").strip().replace("ي", "ی").replace("ك", "ک").replace("ى", "ی")


def cfg() -> dict:
    return config.current_settings().get("VASETEH") or {}


def _sales_db() -> str:
    return config.current_settings()["DATABASES"]["SALES_DB"]


def _q(name: str) -> str:
    """نام جدول/ستون از تنظیمات — فقط حروف و عدد لاتین (جلوگیری از تزریق SQL)"""
    name = (name or "").strip()
    if not _IDENT.match(name):
        raise ValueError(f"نام نامعتبر در تنظیمات واسطه: «{name}»")
    return f"[{name}]"


def parse_codes(raw) -> list:
    out = []
    for c in re.split(r"[,\s;،]+", str(raw or "")):
        c = c.strip()
        if c and c not in out:
            out.append(c[:50])
    return out


def dump_codes(codes) -> str | None:
    s = ",".join(parse_codes(",".join(codes or [])))
    return s[:400] or None


def vasetehs(max_age: int = 60) -> list:
    """فهرست واسطه‌ها (ویزیتورهای نرم‌افزار فروش) با تعداد مشتریان هر کدام"""
    c = cfg()
    key = ("list", _sales_db(), tuple(sorted(c.items())))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    tbl, ccol, vcol, flag = _q(c.get("TABLE") or "CustomerVaseteh"), _q(c.get("CUST_COL") or "C_Code"), \
        _q(c.get("VASETEH_COL") or "Vaseteh_Code"), _q(c.get("FLAG_COL") or "Vaseteh")
    conn = get_conn(_sales_db()); cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT LTRIM(RTRIM(CAST(c.C_Code AS NVARCHAR(50)))), CAST(c.C_Name AS NVARCHAR(200)), ISNULL(n.cnt, 0)
            FROM customer c
            LEFT JOIN (SELECT LTRIM(RTRIM(CAST({vcol} AS NVARCHAR(50)))) AS vc, COUNT(DISTINCT {ccol}) AS cnt
                       FROM {tbl} GROUP BY LTRIM(RTRIM(CAST({vcol} AS NVARCHAR(50))))) n
                   ON n.vc = LTRIM(RTRIM(CAST(c.C_Code AS NVARCHAR(50))))
            WHERE CAST(c.{flag} AS NVARCHAR(10)) IN (N'1', N'True', N'true')
              AND (c.[Delete] = 0 OR c.[Delete] IS NULL)
            ORDER BY c.C_Name""")
        rows = [{"code": r[0], "name": _fa(r[1]) or r[0], "customers": int(r[2] or 0)}
                for r in cur.fetchall() if r[0]]
    finally:
        cur.close(); conn.close()
    _cache[key] = (time.time(), rows)
    return rows


def customers_of(codes) -> set:
    """کد مشتریانی که یکی از این واسطه‌ها را دارند"""
    codes = parse_codes(",".join(codes or []))
    if not codes:
        return set()
    c = cfg()
    tbl, ccol, vcol = _q(c.get("TABLE") or "CustomerVaseteh"), _q(c.get("CUST_COL") or "C_Code"), \
        _q(c.get("VASETEH_COL") or "Vaseteh_Code")
    conn = get_conn(_sales_db()); cur = conn.cursor()
    try:
        cur.execute(f"""SELECT DISTINCT LTRIM(RTRIM(CAST({ccol} AS NVARCHAR(50)))) FROM {tbl}
                        WHERE LTRIM(RTRIM(CAST({vcol} AS NVARCHAR(50)))) IN ({','.join('?' * len(codes))})""", codes)
        return {r[0] for r in cur.fetchall() if r[0]}
    finally:
        cur.close(); conn.close()


def user_codes(visitor_id) -> tuple:
    """(role, [کدهای واسطه]) کاربر از دیتابیس پیچا ویزیت"""
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT ISNULL(role,'visitor'), sales_codes FROM visitors WHERE id=?", (visitor_id,))
        r = cur.fetchone()
    except Exception:            # ستون هنوز ساخته نشده
        cur.execute("SELECT ISNULL(role,'visitor') FROM visitors WHERE id=?", (visitor_id,))
        r = cur.fetchone()
        r = (r[0], None) if r else None
    finally:
        cur.close(); conn.close()
    return (r[0], parse_codes(r[1])) if r else ("visitor", [])


def allowed_customers(visitor_id):
    """None = همهٔ مشتریان؛ وگرنه مجموعهٔ کد مشتریانی که این کاربر می‌بیند"""
    c = cfg()
    if not c.get("ENABLED", True):
        return None
    role, codes = user_codes(visitor_id)
    if role == "admin":
        return None
    if not codes:
        return set() if c.get("NO_CODE") == "none" else None
    return customers_of(codes)
