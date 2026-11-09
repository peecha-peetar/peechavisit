# catalog.py - پیچا ویزیت | عکس کالا از دیتابیس فروش (برای اپ: هنگام سفارش و کاتالوگ)
# ════════════════════════════════════════════════
# ستون عکس جدول article از تنظیمات (CATALOG.IMAGE_COLUMN) خوانده می‌شود؛ اگر خالی باشد
# ستونی با نامی شبیه Pic / Image / Img / Photo / Aks / Path پیدا می‌شود.
# مقدار ستون می‌تواند مسیر کامل فایل، مسیر نسبی (نسبت به CATALOG.IMAGE_DIR)، فقط نام فایل،
# یا خود عکس (ستون باینری) باشد.
# ════════════════════════════════════════════════
import io
import os
import re
import time

import config
from db import get_conn

IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")
_HINTS = ("pic", "image", "img", "photo", "aks", "picture", "path", "file", "tasvir")
_cache = {}


def _settings():
    return config.current_settings().get("CATALOG") or {}


def _sales_db():
    return config.current_settings()["DATABASES"]["SALES_DB"]


def article_columns():
    """[(نام ستون, نوع)] جدول article در دیتابیس فروش"""
    conn = get_conn(_sales_db()); cur = conn.cursor()
    cur.execute("""SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_NAME='article' ORDER BY ORDINAL_POSITION""")
    cols = [(r[0], r[1]) for r in cur.fetchall()]
    cur.close(); conn.close()
    return cols


def image_column():
    """ستون عکس (یا None) — تنظیم دستی یا تشخیص خودکار؛ ۲ دقیقه نگه داشته می‌شود"""
    want = (_settings().get("IMAGE_COLUMN") or "").strip()
    key = ("col", _sales_db(), want)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 120:
        return hit[1]
    col = None
    try:
        cols = article_columns()
        names = {c.lower(): c for c, _ in cols}
        if want:
            col = names.get(want.lower())
        else:
            for c, t in cols:
                lc = c.lower()
                if lc in ("a_code", "a_name") or t in ("bit", "int", "float", "money", "decimal", "numeric", "datetime"):
                    continue
                if any(h in lc for h in _HINTS):
                    col = c
                    break
    except Exception as e:
        print(f"⚠️ image column: {e}")
    if col and not re.fullmatch(r"[A-Za-z0-9_]+", col):
        col = None
    _cache[key] = (time.time(), col)
    return col


def has_image_values():
    """{کد کالا: True} برای کالاهایی که مقدار عکس دارند"""
    col = image_column()
    if not col:
        return {}
    key = ("has", _sales_db(), col)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 120:
        return hit[1]
    out = {}
    try:
        conn = get_conn(_sales_db()); cur = conn.cursor()
        cur.execute(f"SELECT CAST(A_Code AS NVARCHAR(50)) FROM article WHERE [{col}] IS NOT NULL "
                    f"AND DATALENGTH([{col}]) > 0")
        out = {(r[0] or "").strip(): True for r in cur.fetchall()}
        cur.close(); conn.close()
    except Exception as e:
        print(f"⚠️ image list: {e}")
    _cache[key] = (time.time(), out)
    return out


def _resolve(value: str):
    """مقدار ستون → مسیر فایل عکس موجود (یا None)"""
    v = value.strip().strip('"')
    if not v or not v.lower().endswith(IMG_EXT):
        return None
    base = (_settings().get("IMAGE_DIR") or "").strip()
    candidates = [v] if os.path.isabs(v) or v.startswith("\\\\") else []
    if base:
        candidates += [os.path.join(base, v.lstrip("\\/")), os.path.join(base, os.path.basename(v))]
    candidates.append(v)
    for c in candidates:
        try:
            if os.path.isfile(c):
                return c
        except OSError:
            continue
    return None


def image_bytes(code: str):
    """عکس اصلی یک کالا (bytes) یا None"""
    col = image_column()
    if not col:
        return None
    conn = get_conn(_sales_db()); cur = conn.cursor()
    cur.execute(f"SELECT TOP 1 [{col}] FROM article WHERE A_Code = CAST(? AS VARCHAR(50))", (str(code).strip(),))
    r = cur.fetchone()
    cur.close(); conn.close()
    if not r or r[0] is None:
        return None
    val = r[0]
    if isinstance(val, (bytes, bytearray, memoryview)):
        return bytes(val)
    path = _resolve(str(val))
    if not path:
        return None
    with open(path, "rb") as f:
        return f.read()


def thumbnail(code: str, size: int) -> bytes | None:
    """عکس کوچک‌شده (JPEG) — در حافظه نگه داشته می‌شود"""
    size = max(80, min(int(size or 320), 1200))
    s = _settings()
    key = ("img", _sales_db(), str(code), size, s.get("IMAGE_COLUMN") or "", s.get("IMAGE_DIR") or "")
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < (600 if hit[1] else 30):    # «بدون عکس» فقط ۳۰ ثانیه
        return hit[1]
    raw = image_bytes(code)
    out = None
    if raw:
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as im:
            im = im.convert("RGB")
            im.thumbnail((size, size))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=78 if size <= 400 else 85)
            out = buf.getvalue()
    if len([k for k in _cache if k[0] == "img"]) > 600:          # حافظه را محدود نگه دار
        for k in [k for k in _cache if k[0] == "img"][:300]:
            _cache.pop(k, None)
    _cache[key] = (time.time(), out)
    return out
