# catalog.py - پیچا ویزیت | عکس کالا از دیتابیس فروش (برای اپ: هنگام سفارش و کاتالوگ)
# ════════════════════════════════════════════════
# روش ۱ — جدول جدای عکس‌ها (HLOPictures: Code, Picture, PicturePath, Type — ۱ = کالا، ۲ = مشتری):
#   IMAGE_MODE = path → فایل از مسیر PicturePath · db → خود عکس از ستون Picture · auto → مسیر، وگرنه دیتابیس
# روش ۲ — اگر آن جدول نباشد: ستون عکس جدول article از تنظیمات (CATALOG.IMAGE_COLUMN)؛ اگر خالی باشد
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


_ident = lambda s: bool(s) and re.fullmatch(r"[A-Za-z0-9_]+", s) is not None


def _find_table(want: str):
    """نام واقعی جدول عکس: همان نام تنظیم‌شده (بدون حساسیت به حروف) یا جدولی که ستون‌های کد، مسیر و عکس را دارد"""
    s = _settings()
    code_c = (s.get("IMAGE_CODE_COL") or "Code").strip()
    blob_c = (s.get("IMAGE_BLOB_COL") or "Picture").strip()
    path_c = (s.get("IMAGE_PATH_COL") or "PicturePath").strip()
    conn = get_conn(_sales_db()); cur = conn.cursor()
    try:
        if want:
            cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE LOWER(TABLE_NAME) = LOWER(?)", (want,))
            r = cur.fetchone()
            if r:
                return r[0]
        cur.execute("""SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS
                       WHERE LOWER(COLUMN_NAME) IN (LOWER(?), LOWER(?), LOWER(?)) AND TABLE_NAME <> 'article'
                       GROUP BY TABLE_NAME HAVING COUNT(DISTINCT LOWER(COLUMN_NAME)) = 3
                       ORDER BY CASE WHEN TABLE_NAME LIKE '%pict%' THEN 0 ELSE 1 END, TABLE_NAME""",
                    (code_c, blob_c, path_c))
        r = cur.fetchone()
        return r[0] if r else None
    finally:
        cur.close(); conn.close()


def table_mode(kind: str = "article"):
    """تنظیمات جدول عکس (اگر در دیتابیس فروش هست)، وگرنه None — kind: article / customer"""
    s = _settings()
    want = (s.get("IMAGE_TABLE") or "").strip()
    cols = {k: (s.get(k) or "").strip() for k in ("IMAGE_CODE_COL", "IMAGE_PATH_COL", "IMAGE_BLOB_COL")}
    if not _ident(cols["IMAGE_CODE_COL"]):
        return None
    key = ("tbl", _sales_db(), want, repr(sorted(cols.items())))
    hit = _cache.get(key)
    if not (hit and time.time() - hit[0] < 120):
        name = None
        try:
            name = _find_table(want)
        except Exception as e:
            print(f"⚠️ image table: {e}")
        hit = (time.time(), name)
        _cache[key] = hit
    t = hit[1]
    if not t or not _ident(t):
        return None
    mode = (s.get("IMAGE_MODE") or "auto").strip().lower()
    typ = (s.get("CUSTOMER_TYPE") if kind == "customer" else s.get("IMAGE_TYPE")) or ""
    return {"table": t, "code": cols["IMAGE_CODE_COL"],
            "path": cols["IMAGE_PATH_COL"] if _ident(cols["IMAGE_PATH_COL"]) else None,
            "blob": cols["IMAGE_BLOB_COL"] if _ident(cols["IMAGE_BLOB_COL"]) else None,
            "mode": mode if mode in ("path", "db", "auto") else "auto",
            "type": str(typ).strip(), "kind": kind}


def _tbl_filters(tm):
    """شرط «عکس دارد» + فیلتر Type"""
    conds = []
    if tm["mode"] in ("path", "auto") and tm["path"]:
        conds.append(f"(ISNULL([{tm['path']}], '') <> '')")
    if tm["mode"] in ("db", "auto") and tm["blob"]:
        conds.append(f"(DATALENGTH([{tm['blob']}]) > 0)")
    where = "(" + " OR ".join(conds) + ")" if conds else "1=0"
    params = ()
    if tm["type"]:
        where += " AND [Type] = ?"
        params = (tm["type"],)
    return where, params


def source_text():
    """توضیح منبع عکس برای پنل مدیریت"""
    tm = table_mode()
    if tm:
        m = {"path": f"مسیر فایل ({tm['path']})", "db": f"داخل دیتابیس ({tm['blob']})",
             "auto": f"مسیر ({tm['path']})، وگرنه دیتابیس ({tm['blob']})"}[tm["mode"]]
        return f"جدول {tm['table']} — {m}"
    col = image_column()
    return f"ستون {col} در جدول article" if col else "منبع عکس پیدا نشد"


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


def has_image_values(kind: str = "article"):
    """{کد: True} برای کالاها (یا مشتری‌ها) که عکس دارند"""
    tm = table_mode(kind)
    if tm:
        key = ("has", _sales_db(), repr(sorted(tm.items())))
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < 120:
            return hit[1]
        out = {}
        try:
            where, params = _tbl_filters(tm)
            conn = get_conn(_sales_db()); cur = conn.cursor()
            cur.execute(f"SELECT DISTINCT CAST([{tm['code']}] AS NVARCHAR(50)) FROM [{tm['table']}] WHERE {where}", params)
            out = {(r[0] or "").strip(): True for r in cur.fetchall()}
            cur.close(); conn.close()
        except Exception as e:
            print(f"⚠️ image list (table): {e}")
        _cache[key] = (time.time(), out)
        return out
    if kind != "article":
        return {}
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


def _table_image(tm, code):
    where, params = _tbl_filters(tm)
    conn = get_conn(_sales_db()); cur = conn.cursor()
    try:
        base = f"FROM [{tm['table']}] WHERE [{tm['code']}] = CAST(? AS VARCHAR(50)) AND {where}"
        if tm["mode"] in ("path", "auto") and tm["path"]:
            cur.execute(f"SELECT TOP 1 [{tm['path']}] {base} AND ISNULL([{tm['path']}], '') <> '' ORDER BY 1",
                        (str(code).strip(),) + params)
            r = cur.fetchone()
            if r and r[0]:
                p = _resolve(str(r[0]))
                if p:
                    with open(p, "rb") as f:
                        return f.read()
                if tm["mode"] == "path":
                    print(f"⚠️ فایل عکس کالای {code} پیدا نشد: {r[0]}")
                    return None
        if tm["mode"] in ("db", "auto") and tm["blob"]:
            cur.execute(f"SELECT TOP 1 [{tm['blob']}] {base} AND DATALENGTH([{tm['blob']}]) > 0",
                        (str(code).strip(),) + params)
            r = cur.fetchone()
            if r and r[0]:
                return bytes(r[0])
        return None
    finally:
        cur.close(); conn.close()


def image_bytes(code: str, kind: str = "article"):
    """عکس اصلی یک کالا یا مشتری (bytes) یا None"""
    tm = table_mode(kind)
    if tm:
        return _table_image(tm, code)
    if kind != "article":
        return None
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


def thumbnail(code: str, size: int, kind: str = "article") -> bytes | None:
    """عکس کوچک‌شده (JPEG) — در حافظه نگه داشته می‌شود"""
    size = max(80, min(int(size or 320), 1200))
    s = _settings()
    key = ("img", _sales_db(), kind, str(code), size, repr(sorted(s.items())))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < (600 if hit[1] else 30):    # «بدون عکس» فقط ۳۰ ثانیه
        return hit[1]
    raw = image_bytes(code, kind)
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


def diagnose(code: str, kind: str = "article") -> list[str]:
    """برای پنل مدیریت: چرا عکس یک کالا (یا مشتری) پیدا می‌شود یا نمی‌شود"""
    out = [f"منبع: {source_text()}"]
    tm = table_mode(kind)
    if not tm:
        col = image_column()
        out.append(f"جدول عکس پیدا نشد؛ ستون article: {col or 'ندارد'}")
        return out
    try:
        conn = get_conn(_sales_db()); cur = conn.cursor()
        blob = f"DATALENGTH([{tm['blob']}])" if tm["blob"] else "0"
        path = f"[{tm['path']}]" if tm["path"] else "NULL"
        cur.execute(f"SELECT [Type], {path}, {blob} FROM [{tm['table']}] WHERE [{tm['code']}] = CAST(? AS VARCHAR(50))",
                    (str(code).strip(),))
        rows = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e:
        return out + [f"❌ خواندن جدول عکس: {e}"]
    if not rows:
        return out + [f"ردیفی با کد «{code}» در جدول {tm['table']} نیست."]
    for t, p, n in rows:
        used = "✔ استفاده می‌شود" if (not tm["type"] or str(t) == tm["type"]) else f"✘ کنار گذاشته شد (فیلتر Type = {tm['type']})"
        if p:
            rp = _resolve(str(p))
            ptxt = f"مسیر «{p}» — {'فایل روی همین سرور پیدا شد' if rp else 'فایل روی این کامپیوتر (سرور پیچا ویزیت) پیدا نشد'}"
        else:
            ptxt = "مسیر خالی"
        out.append(f"Type={t} · {ptxt} · عکس داخل دیتابیس: {f'{n:,} بایت' if n else 'ندارد'} · {used}")
    return out
