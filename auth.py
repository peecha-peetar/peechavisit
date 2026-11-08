# auth.py - سیستم احراز هویت پیچا ویزیت
# ════════════════════════════════════════════════
# منطق مشترک ورود برای API موبایل (app.py)، داشبورد و پنل مدیریت
# قفل حساب بعد از MAX_LOGIN_ATTEMPTS تلاش ناموفق به مدت LOCKOUT_MINUTES
# ════════════════════════════════════════════════
import hashlib
from datetime import datetime, timedelta
from config import SECURITY
from db import get_conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def is_locked(locked_until) -> bool:
    """قفل فقط تا زمان locked_until معتبر است"""
    return bool(locked_until) and datetime.now() < locked_until


def verify_login(username: str, password: str, require_role: str | None = None) -> dict:
    """
    بررسی اطلاعات ورود
    Returns:
        {"ok": True,  "user": {...}}
        {"ok": False, "error": "...", "status": 401|403}
    """
    max_tries = int(SECURITY["MAX_LOGIN_ATTEMPTS"])
    lock_min  = int(SECURITY["LOCKOUT_MINUTES"])
    username  = (username or '').strip()
    generic   = "نام کاربری یا رمز اشتباه است"

    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, full_name, ISNULL(role,'visitor'), ISNULL(phone,''),
                   ISNULL(failed_attempts,0), locked_until, password_hash
            FROM visitors
            WHERE username=? AND is_active=1
        """, (username,))
        row = cur.fetchone()
        if not row:
            # ✅ پیام یکسان برای جلوگیری از user enumeration
            return {"ok": False, "error": generic, "status": 401}

        uid, full_name, role, phone, failed, locked_until, pw_hash = row

        if is_locked(locked_until):
            remaining = int((locked_until - datetime.now()).total_seconds() / 60) + 1
            return {"ok": False, "status": 403,
                    "error": f"حساب قفل است. {remaining} دقیقه صبر کنید"}

        if pw_hash == hash_password(password):
            cur.execute("""
                UPDATE visitors
                SET failed_attempts=0, locked_until=NULL, last_login=?
                WHERE id=?
            """, (datetime.now(), uid))
            conn.commit()
            if require_role and role != require_role:
                return {"ok": False, "status": 403, "error": "این حساب دسترسی مدیر ندارد"}
            return {"ok": True, "user": {"id": uid, "name": full_name, "role": role,
                                         "phone": phone, "username": username}}

        # قفل منقضی‌شده یعنی شمارش از نو
        new_failed = 1 if locked_until else (failed or 0) + 1
        lock_time  = None
        if new_failed >= max_tries:
            lock_time = datetime.now() + timedelta(minutes=lock_min)
        cur.execute("""
            UPDATE visitors SET failed_attempts=?, locked_until=?
            WHERE id=?
        """, (new_failed, lock_time, uid))
        conn.commit()

        if lock_time:
            return {"ok": False, "status": 401,
                    "error": f"حساب به مدت {lock_min} دقیقه قفل شد."}
        return {"ok": False, "status": 401,
                "error": f"{generic}. ({max_tries - new_failed} تلاش باقی)"}
    finally:
        cur.close(); conn.close()
