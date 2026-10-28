# auth.py - سیستم احراز هویت پیچا ویزیت
import hashlib, secrets, pyodbc
from datetime import datetime, timedelta
from config import NETWORK, DATABASES, SECURITY

SERVER_NAME = NETWORK["SERVER_NAME"]

def get_conn():
    return pyodbc.connect(
        f'DRIVER={{{DATABASES["DRIVER"]}}};'
        f'SERVER={SERVER_NAME};'
        f'DATABASE={DATABASES["TRACKING_DB"]};'
        f'Trusted_Connection=yes;'
    )

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_login(username: str, password: str) -> dict | None:
    """
    بررسی اطلاعات ورود
    Returns: dict کاربر یا None در صورت خطا
    """
    conn = get_conn()
    cur = conn.cursor()

    # بررسی قفل بودن حساب
    cur.execute("""
        SELECT failed_attempts, locked_until
        FROM visitors
        WHERE username=? AND is_active=1
    """, (username,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None

    failed, locked_until = row
    if locked_until and datetime.now() < locked_until:
        cur.close(); conn.close()
        remaining = int((locked_until - datetime.now()).total_seconds() / 60) + 1
        return {"error": f"حساب قفل است. {remaining} دقیقه دیگر تلاش کنید."}

    # بررسی رمز عبور
    pw_hash = hash_password(password)
    cur.execute("""
        SELECT id, full_name, role, phone
        FROM visitors
        WHERE username=? AND password_hash=? AND is_active=1
    """, (username, pw_hash))
    user = cur.fetchone()

    if user:
        # ریست failed_attempts
        cur.execute("""
            UPDATE visitors
            SET failed_attempts=0, locked_until=NULL, last_login=?
            WHERE username=?
        """, (datetime.now(), username))
        conn.commit()
        cur.close(); conn.close()
        return {
            "id": user[0], "name": user[1],
            "role": user[2] or "visitor", "phone": user[3] or ""
        }
    else:
        # افزایش تلاش ناموفق
        new_failed = (failed or 0) + 1
        lock_time = None
        if new_failed >= SECURITY["MAX_LOGIN_ATTEMPTS"]:
            lock_time = datetime.now() + timedelta(minutes=SECURITY["LOCKOUT_MINUTES"])
        cur.execute("""
            UPDATE visitors
            SET failed_attempts=?, locked_until=?
            WHERE username=?
        """, (new_failed, lock_time, username))
        conn.commit()
        cur.close(); conn.close()
        remaining_tries = SECURITY["MAX_LOGIN_ATTEMPTS"] - new_failed
        if remaining_tries > 0:
            return {"error": f"رمز عبور اشتباه است. {remaining_tries} تلاش باقی دارید."}
        return {"error": f"حساب به مدت {SECURITY['LOCKOUT_MINUTES']} دقیقه قفل شد."}
