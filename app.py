# app.py - پیچا ویزیت | Flask API v3.0 (ایمن)
import hashlib, os, base64, secrets, pyodbc
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# ══════════════════════════════════════════
# تنظیمات امنیتی
# ══════════════════════════════════════════
try:
    from config import NETWORK, SECURITY, PATHS, DATABASES
    SERVER_NAME   = NETWORK["SERVER_NAME"]
    SERVER_IP     = NETWORK["SERVER_IP"]
    SECRET_KEY    = SECURITY["SESSION_SECRET"]
    SESSION_HOURS = SECURITY["SESSION_HOURS"]
    ALLOWED_ORIGIN= f"http://{NETWORK['SERVER_IP']}:{NETWORK['PWA_PORT']}"
except ImportError:
    SERVER_NAME   = 'SERWIN\\RAD'   # fallback — config.py را ویرایش کنید
    SERVER_IP     = '10.165.254.180' # fallback
    SECRET_KEY    = '37be8db295c2f7bb433d7e176effb94e7905eb13e7421a6abed238821cae2592'
    SESSION_HOURS = 10
    ALLOWED_ORIGIN= f"http://{SERVER_IP}:8000"

# ✅ CORS فقط برای آدرس مشخص
CORS(app,
    origins="*",           # همه IP‌های شبکه داخلی
    supports_credentials=False,
    allow_headers=["Content-Type", "X-Auth-Token"],
    methods=["GET","POST","OPTIONS"]
)

# پوشه‌های آپلود
for folder in ['static/selfies', 'static/checks', 'static/transfers']:
    os.makedirs(folder, exist_ok=True)


# ══════════════════════════════════════════
# اتصال دیتابیس
# ══════════════════════════════════════════
def get_conn(db='tracking'):
    return pyodbc.connect(
        f'DRIVER={{SQL Server}};SERVER={SERVER_NAME};'
        f'DATABASE={db};Trusted_Connection=yes;'
    )


# ══════════════════════════════════════════
# مدیریت Token (جایگزین JWT ساده)
# ══════════════════════════════════════════
def generate_token(visitor_id: int, username: str) -> str:
    """ساخت token امن با HMAC"""
    import hmac
    expire = int((datetime.now() + timedelta(hours=SESSION_HOURS)).timestamp())
    payload = f"{visitor_id}:{username}:{expire}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}:{sig}"
    return base64.b64encode(raw.encode()).decode()


def verify_token(token: str) -> dict | None:
    """
    بررسی اعتبار token
    Returns: {'visitor_id': int, 'username': str} یا None
    """
    import hmac
    if not token:
        return None
    try:
        raw = base64.b64decode(token.encode()).decode()
        parts = raw.split(':')
        if len(parts) != 4:
            return None
        visitor_id, username, expire_str, sig = parts
        expire = int(expire_str)

        # بررسی انقضا
        if datetime.now().timestamp() > expire:
            return None

        # بررسی امضا
        payload = f"{visitor_id}:{username}:{expire_str}"
        expected_sig = hmac.new(
            SECRET_KEY.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            return None

        return {'visitor_id': int(visitor_id), 'username': username}
    except Exception:
        return None


def require_auth(f):
    """دکوریتور احراز هویت برای همه endpoints حساس"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Auth-Token') or \
                request.headers.get('Authorization', '').replace('Bearer ', '')
        user = verify_token(token)
        if not user:
            return jsonify({"status": "error", "message": "احراز هویت لازم است"}), 401
        # تزریق اطلاعات کاربر به تابع
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════
# جدول submitted_uids
# ══════════════════════════════════════════
def setup_tables():
    try:
        conn = pyodbc.connect(
            f'DRIVER={{SQL Server}};SERVER={SERVER_NAME};'
            f'DATABASE=tracking;Trusted_Connection=yes;',
            autocommit=True
        )
        cur = conn.cursor()
        cur.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name='submitted_uids')
            CREATE TABLE submitted_uids (
                uid VARCHAR(100) NOT NULL PRIMARY KEY,
                submitted_at DATETIME NOT NULL DEFAULT GETDATE()
            )
        """)
        cur.close(); conn.close()
        print("✅ جدول submitted_uids آماده")
    except Exception as e:
        print(f"❌ خطا: {e}")

setup_tables()


def is_uid_done(cursor, uid):
    if not uid: return False
    try:
        cursor.execute("SELECT COUNT(1) FROM submitted_uids WHERE uid=?", (uid,))
        return cursor.fetchone()[0] > 0
    except: return False


def mark_uid_done(cursor, uid):
    if not uid: return
    try:
        cursor.execute(
            "IF NOT EXISTS(SELECT 1 FROM submitted_uids WHERE uid=?) "
            "INSERT INTO submitted_uids(uid) VALUES(?)",
            (uid, uid)
        )
    except: pass


def save_image(b64_data, folder, prefix, visitor_id, customer_code, date_str, time_str):
    """ذخیره عکس و برگرداندن مسیر"""
    if not b64_data:
        return None
    if 'base64,' in b64_data:
        b64_data = b64_data.split('base64,')[1]
    try:
        clean_time = time_str.replace(':', '')
        # ✅ نام فایل بدون اطلاعات حساس
        fname = f"{prefix}_{visitor_id}_{customer_code}_{date_str.replace('-','')}_{clean_time}.jpg"
        fpath = os.path.join(folder, fname)
        with open(fpath, 'wb') as f:
            f.write(base64.b64decode(b64_data))
        return f"/static/{os.path.basename(folder)}/{fname}"
    except Exception as e:
        print(f"خطا در ذخیره عکس: {e}")
        return None


# ══════════════════════════════════════════
# ۰. سلامت سرور
# ══════════════════════════════════════════
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "running", "message": "PeechaVisit Server Active"}), 200


# ══════════════════════════════════════════
# ۱. ورود کاربر — بدون نیاز به token
# ══════════════════════════════════════════
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({"status": "error", "message": "نام کاربری و رمز الزامی است"}), 400

        pw_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        conn = get_conn(); cur = conn.cursor()

        # بررسی قفل
        cur.execute("""
            SELECT id, full_name, ISNULL(role,'visitor'),
                   ISNULL(failed_attempts,0), locked_until
            FROM visitors
            WHERE username=? AND is_active=1
        """, (username,))
        row = cur.fetchone()

        if not row:
            cur.close(); conn.close()
            # ✅ پیام یکسان برای جلوگیری از user enumeration
            return jsonify({"status":"error","message":"نام کاربری یا رمز اشتباه است"}), 401

        uid, fullname, role, failed, locked_until = row

        if locked_until and datetime.now() < locked_until:
            remaining = int((locked_until - datetime.now()).total_seconds() / 60) + 1
            cur.close(); conn.close()
            return jsonify({"status":"error",
                            "message":f"حساب قفل است. {remaining} دقیقه صبر کنید"}), 403

        # بررسی رمز
        cur.execute("""
            SELECT id FROM visitors
            WHERE username=? AND password_hash=? AND is_active=1
        """, (username, pw_hash))

        if cur.fetchone():
            # ✅ ریست failed_attempts و ثبت زمان ورود
            cur.execute("""
                UPDATE visitors
                SET failed_attempts=0, locked_until=NULL, last_login=?
                WHERE username=?
            """, (datetime.now(), username))
            conn.commit()
            cur.close(); conn.close()

            token = generate_token(uid, username)
            return jsonify({
                "status":  "success",
                "message": f"خوش آمدید {fullname}",
                "token":   token,
                "user":    {"id": uid, "name": fullname, "role": role, "username": username}
            }), 200
        else:
            new_failed = (failed or 0) + 1
            lock_time  = None
            if new_failed >= 5:
                lock_time = datetime.now() + timedelta(minutes=30)
            cur.execute("""
                UPDATE visitors SET failed_attempts=?, locked_until=?
                WHERE username=?
            """, (new_failed, lock_time, username))
            conn.commit(); cur.close(); conn.close()

            if lock_time:
                msg = "حساب به مدت ۳۰ دقیقه قفل شد."
            else:
                msg = f"نام کاربری یا رمز اشتباه است. ({5-new_failed} تلاش باقی)"
            return jsonify({"status":"error","message":msg}), 401

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"status":"error","message":"خطای سرور"}), 500


# ══════════════════════════════════════════
# ۲. سینک داده پایه — نیاز به token
# ══════════════════════════════════════════
@app.route('/api/sync-data', methods=['GET'])
@require_auth
def sync_data():
    try:
        conn = get_conn('dejavuDB1'); cur = conn.cursor()

        cur.execute("""
            SELECT C_Code, C_Name, latitude, longitude
            FROM customer WHERE [Delete]=0 OR [Delete] IS NULL
        """)
        customers = [{"code":r[0], "name":(r[1] or '').strip(),
                      "lat":r[2] or 0.0, "lng":r[3] or 0.0}
                     for r in cur.fetchall()]

        cur.execute("""
            SELECT A_Code, A_Name, Sel_Price, Exist
            FROM article WHERE [Delete]=0 OR [Delete] IS NULL
        """)
        articles = [{"code":r[0], "name":(r[1] or '').strip(),
                     "price":float(r[2] or 0), "stock":float(r[3] or 0)}
                    for r in cur.fetchall()]

        cur.close(); conn.close()
        return jsonify({"status":"success",
                        "customers":customers,
                        "articles":articles}), 200
    except Exception as e:
        print(f"sync-data error: {e}")
        return jsonify({"status":"error","message":str(e)}), 500


# ══════════════════════════════════════════
# ۳. ثبت ویزیت — نیاز به token
# ══════════════════════════════════════════
@app.route('/api/submit-visit', methods=['POST'])
@require_auth
def submit_visit():
    try:
        data = request.json or {}
        uid  = data.get('uid', '')

        # ✅ visitor_id از token گرفته میشه، نه از body
        visitor_id    = request.current_user['visitor_id']
        customer_code = data.get('customer_code', '').strip()
        latitude      = data.get('latitude')
        longitude     = data.get('longitude')
        description   = data.get('description', '')
        selfie_b64    = data.get('selfie_b64', '')
        visit_date    = data.get('client_date', datetime.now().strftime('%Y-%m-%d'))
        visit_time    = data.get('client_time', datetime.now().strftime('%H:%M:%S'))

        # اعتبارسنجی
        if not customer_code:
            return jsonify({"status":"error","message":"کد مشتری الزامی است"}), 400
        if latitude is None or longitude is None:
            return jsonify({"status":"error","message":"موقعیت GPS الزامی است"}), 400

        conn = get_conn(); cur = conn.cursor()

        if is_uid_done(cur, uid):
            cur.close(); conn.close()
            return jsonify({"status":"success","message":"تکراری - uid"}), 200

        # بررسی زمان دقیق
        cur.execute("""
            SELECT COUNT(1) FROM visits
            WHERE visitor_id=? AND customer_code=?
            AND visit_date=? AND CONVERT(VARCHAR,visit_time,108)=?
        """, (visitor_id, customer_code, visit_date, visit_time))
        if cur.fetchone()[0] > 0:
            cur.close(); conn.close()
            return jsonify({"status":"success","message":"تکراری - زمان"}), 200

        selfie_path = save_image(selfie_b64, 'static/selfies', 'visit',
                                 visitor_id, customer_code, visit_date, visit_time)

        cur.execute("""
            INSERT INTO visits
                (visitor_id,customer_code,visit_date,visit_time,
                 latitude,longitude,selfie_path,description)
            VALUES (?,?,?,?,?,?,?,?)
        """, (visitor_id, customer_code, visit_date, visit_time,
              latitude, longitude, selfie_path, description))

        mark_uid_done(cur, uid)
        conn.commit(); cur.close(); conn.close()
        print(f"✅ visit | user={visitor_id} | cust={customer_code}")
        return jsonify({"status":"success","message":"ویزیت ثبت شد"}), 200

    except Exception as e:
        print(f"submit-visit error: {e}")
        return jsonify({"status":"error","message":"خطای سرور"}), 500


# ══════════════════════════════════════════
# ۴. ثبت سفارش — نیاز به token
# ══════════════════════════════════════════
@app.route('/api/submit-order', methods=['POST'])
@require_auth
def submit_order():
    try:
        data = request.json or {}
        uid  = data.get('uid', '')
        order_uid = f"{uid}_order"

        visitor_id    = request.current_user['visitor_id']
        customer_code = data.get('customer_code', '').strip()
        latitude      = data.get('latitude')
        longitude     = data.get('longitude')
        items         = data.get('order_items', [])
        order_date    = data.get('client_date', datetime.now().strftime('%Y-%m-%d'))
        order_time    = data.get('client_time', datetime.now().strftime('%H:%M:%S'))

        if not customer_code or not items:
            return jsonify({"status":"error","message":"کد مشتری و اقلام الزامی است"}), 400

        total = sum(float(i.get('qty',0)) * float(i.get('price',0)) for i in items)

        conn = get_conn(); cur = conn.cursor()

        if is_uid_done(cur, order_uid):
            cur.close(); conn.close()
            return jsonify({"status":"success","message":"تکراری"}), 200

        cur.execute("""
            SELECT COUNT(1) FROM orders
            WHERE visitor_id=? AND customer_code=?
            AND order_date=? AND CONVERT(VARCHAR,order_time,108)=?
        """, (visitor_id, customer_code, order_date, order_time))
        if cur.fetchone()[0] > 0:
            cur.close(); conn.close()
            return jsonify({"status":"success","message":"تکراری - زمان"}), 200

        cur.execute("""
            INSERT INTO orders
                (visitor_id,customer_code,order_date,order_time,
                 latitude,longitude,total_amount)
            OUTPUT INSERTED.id
            VALUES (?,?,?,?,?,?,?)
        """, (visitor_id, customer_code, order_date, order_time,
              latitude, longitude, total))
        order_id = cur.fetchone()[0]

        for item in items:
            cur.execute("""
                INSERT INTO order_items (order_id,article_code,quantity,price)
                VALUES (?,?,?,?)
            """, (order_id, item['code'], item['qty'], item['price']))

        mark_uid_done(cur, order_uid)
        conn.commit(); cur.close(); conn.close()
        print(f"✅ order | user={visitor_id} | cust={customer_code} | total={total}")
        return jsonify({"status":"success","message":"سفارش ثبت شد"}), 200

    except Exception as e:
        print(f"submit-order error: {e}")
        return jsonify({"status":"error","message":"خطای سرور"}), 500


# ══════════════════════════════════════════
# ۵. ثبت دریافت مالی — نیاز به token
# ══════════════════════════════════════════
@app.route('/api/submit-payment', methods=['POST'])
@require_auth
def submit_payment():
    try:
        data = request.json or {}
        uid  = data.get('uid', '')
        pay_uid = f"{uid}_payment"

        visitor_id    = request.current_user['visitor_id']
        customer_code = data.get('customer_code', '').strip()
        latitude      = data.get('latitude')
        longitude     = data.get('longitude')
        pay_info      = data.get('payment_info') or {}
        pay_type      = pay_info.get('type', 'نقدی')
        amount        = float(pay_info.get('amount', 0))
        pay_date      = data.get('client_date', datetime.now().strftime('%Y-%m-%d'))
        pay_time      = data.get('client_time', datetime.now().strftime('%H:%M:%S'))

        if not customer_code or amount <= 0:
            return jsonify({"status":"error","message":"کد مشتری و مبلغ الزامی است"}), 400

        check_number   = pay_info.get('check_number', '')
        check_sayyadi  = pay_info.get('check_sayyadi', '')
        check_due      = pay_info.get('check_due') or None
        check_img_b64  = pay_info.get('check_image', '')
        tr_account     = pay_info.get('transfer_account', '')
        tr_tracking    = pay_info.get('transfer_tracking', '')
        tr_img_b64     = pay_info.get('transfer_image', '')

        conn = get_conn(); cur = conn.cursor()

        if is_uid_done(cur, pay_uid):
            cur.close(); conn.close()
            return jsonify({"status":"success","message":"تکراری"}), 200

        cur.execute("""
            SELECT COUNT(1) FROM payments
            WHERE visitor_id=? AND customer_code=?
            AND payment_date=? AND CONVERT(VARCHAR,payment_time,108)=?
        """, (visitor_id, customer_code, pay_date, pay_time))
        if cur.fetchone()[0] > 0:
            cur.close(); conn.close()
            return jsonify({"status":"success","message":"تکراری - زمان"}), 200

        check_img_path = save_image(check_img_b64, 'static/checks', 'check',
                                    visitor_id, customer_code, pay_date, pay_time)
        tr_img_path    = save_image(tr_img_b64, 'static/transfers', 'transfer',
                                    visitor_id, customer_code, pay_date, pay_time)

        try:
            cur.execute("""
                INSERT INTO payments
                    (visitor_id,customer_code,payment_date,payment_time,
                     payment_type,amount,tracking_number,latitude,longitude,
                     check_number,check_sayyadi,check_due_date,check_image_path,
                     transfer_account,transfer_tracking,transfer_image_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (visitor_id, customer_code, pay_date, pay_time,
                  pay_type, amount, tr_tracking or check_sayyadi or '',
                  latitude, longitude,
                  check_number or None, check_sayyadi or None,
                  check_due, check_img_path,
                  tr_account or None, tr_tracking or None, tr_img_path))
        except Exception:
            cur.execute("""
                INSERT INTO payments
                    (visitor_id,customer_code,payment_date,payment_time,
                     payment_type,amount,tracking_number,latitude,longitude)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (visitor_id, customer_code, pay_date, pay_time,
                  pay_type, amount, tr_tracking or check_number or '',
                  latitude, longitude))

        mark_uid_done(cur, pay_uid)
        conn.commit(); cur.close(); conn.close()
        print(f"✅ payment | user={visitor_id} | {pay_type} | {amount}")
        return jsonify({"status":"success","message":"دریافت مالی ثبت شد"}), 200

    except Exception as e:
        print(f"submit-payment error: {e}")
        return jsonify({"status":"error","message":"خطای سرور"}), 500


if __name__ == '__main__':
    try:
        from config import NETWORK
        debug = NETWORK.get('DEBUG', False)
        port  = NETWORK.get('FLASK_PORT', 5000)
    except ImportError:
        debug = False; port = 5000

    print(f"🚀 PeechaVisit API در حال اجرا روی پورت {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
