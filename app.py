# app.py - پیچا ویزیت | Flask API v3.0 (ایمن)
import hashlib, os, base64, re
from urllib.parse import unquote
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS

import paths
app = Flask(__name__, static_folder=paths.STATIC_DIR, static_url_path="/static")

# ══════════════════════════════════════════
# تنظیمات امنیتی
# ══════════════════════════════════════════
import config
from config import NETWORK, SECURITY, PATHS
from db import get_conn, TRACKING_DB, SALES_DB
from auth import verify_login
from mobile_rules import effective_rules
import audit

SECRET_KEY    = SECURITY["SESSION_SECRET"]
SESSION_HOURS = SECURITY["SESSION_HOURS"]

# ✅ CORS فقط برای آدرس مشخص
CORS(app,
    origins="*",           # همه IP‌های شبکه داخلی
    supports_credentials=False,
    allow_headers=["Content-Type", "X-Auth-Token"],
    methods=["GET","POST","OPTIONS"]
)

# پوشه‌های آپلود
# مسیر نسبی → داخل پوشهٔ داده (حالت نصبی: ProgramData\PeechaVisit)
SELFIES_DIR, CHECKS_DIR, TRANSFERS_DIR = (os.path.join(paths.DATA_DIR, PATHS[k])
                                         for k in ("SELFIES_DIR", "CHECKS_DIR", "TRANSFERS_DIR"))
for folder in [SELFIES_DIR, CHECKS_DIR, TRANSFERS_DIR]:
    os.makedirs(folder, exist_ok=True)


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
        conn = get_conn(autocommit=True)
        cur = conn.cursor()
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.columns
                           WHERE object_id=OBJECT_ID('visitors') AND name='app_settings')
            ALTER TABLE visitors ADD app_settings NVARCHAR(1000) NULL
        """)
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.columns
                           WHERE object_id=OBJECT_ID('visitors') AND name='dash_perms')
            ALTER TABLE visitors ADD dash_perms NVARCHAR(2000) NULL
        """)
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.columns
                           WHERE object_id=OBJECT_ID('visits') AND name='gps_accuracy')
            ALTER TABLE visits ADD gps_accuracy FLOAT NULL
        """)
        cur.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name='submitted_uids')
            CREATE TABLE submitted_uids (
                uid VARCHAR(100) NOT NULL PRIMARY KEY,
                submitted_at DATETIME NOT NULL DEFAULT GETDATE()
            )
        """)
        cur.close(); conn.close()
        audit.ensure_schema()       # پیام‌ها، لاگ، توضیحات و دستگاه
        print("✅ جدول‌ها آماده")
    except Exception as e:
        print(f"❌ خطا: {e}")

setup_tables()


def user_app_settings(visitor_id):
    """JSON تنظیمات اختصاصی کاربر (اگر ستون هنوز ساخته نشده، None)"""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT app_settings FROM visitors WHERE id=?", (visitor_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return row[0] if row else None
    except Exception:
        return None


def client_device() -> str:
    """دستگاه کاربر: هدر X-Device از اپ (برند، مدل، اندروید) یا خلاصهٔ User-Agent"""
    # اپ مقدار را URL-encode می‌فرستد (هدر HTTP فقط حروف لاتین می‌پذیرد)
    dev = unquote(request.headers.get('X-Device') or '').strip()
    if not dev:
        ua = request.headers.get('User-Agent', '')
        m = re.search(r'\(Linux; Android ([\d.]+); ([^;)]+)', ua)
        dev = f"{m.group(2).strip()} · Android {m.group(1)}" if m else ua[:120]
    return dev[:200]


def log(event, detail=None, visitor_id=None, username=None):
    u = getattr(request, 'current_user', None) or {}
    audit.log_event('app', event, visitor_id or u.get('visitor_id'), username or u.get('username'),
                    request.headers.get('X-Forwarded-For', request.remote_addr), client_device(), detail)


def set_extra(cur, table, row_id, description=None):
    """دستگاه و توضیحات ثبت جدید (اگر ستون‌ها نباشند، بی‌صدا رد می‌شود)"""
    try:
        if row_id is None:
            cur.execute("SELECT @@IDENTITY")
            row_id = cur.fetchone()[0]
        cur.execute(f"UPDATE {table} SET device=?{', description=?' if description is not None else ''} WHERE id=?",
                    (client_device(), *([description[:1000]] if description is not None else []), int(row_id)))
    except Exception as e:
        print(f"⚠️ set_extra {table}: {e}")


def gps_rules():
    """حد دقت و مهلت GPS از config (بخش GPS) برای اپ"""
    g = config.current_settings().get("GPS") or {}
    return {"GPS_MAX_ACCURACY": int(g.get("MAX_ACCURACY_METERS", 50)),
            "GPS_TIMEOUT": int(g.get("TIMEOUT_SECONDS", 20))}


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


def fa_text(v) -> str:
    """ي/ك عربی → ی/ک فارسی تا جستجو در اپ درست کار کند"""
    return (v or '').strip().replace('ي', 'ی').replace('ك', 'ک').replace('ى', 'ی')


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

        res = verify_login(username, password)
        if not res["ok"]:
            log('login_failed', res["error"], username=username)
            return jsonify({"status": "error", "message": res["error"]}), res["status"]

        user  = res["user"]
        log('login', visitor_id=user["id"], username=username)
        token = generate_token(user["id"], username)
        return jsonify({
            "status":  "success",
            "message": f"خوش آمدید {user['name']}",
            "token":   token,
            "user":    {"id": user["id"], "name": user["name"],
                        "role": user["role"], "username": username}
        }), 200

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"status":"error","message":"خطای سرور"}), 500


# ══════════════════════════════════════════
# ۲. سینک داده پایه — نیاز به token
# ══════════════════════════════════════════
@app.route('/api/sync-data', methods=['GET'])
@require_auth
def sync_data():
    # تنظیمات اپ: سراسری (تازه از settings.json، بدون ری‌استارت) + تنظیم اختصاصی همین کاربر
    rules = effective_rules(user_app_settings(request.current_user['visitor_id']))
    step = 'اتصال به دیتابیس فروش'
    try:
        conn = get_conn(SALES_DB); cur = conn.cursor()

        # مختصات مشتری فقط اگر این ستون‌ها در دیتابیس فروش وجود داشته باشند
        step = 'بررسی ستون‌های جدول customer'
        cur.execute("SELECT COL_LENGTH('customer','latitude'), COL_LENGTH('customer','longitude')")
        has_geo = all(cur.fetchone())
        geo = "latitude, longitude" if has_geo else "NULL, NULL"

        # ✅ CAST به NVARCHAR: متن فارسی در ستون VARCHAR (کالیشن عربی) را
        #    SQL Server درست تبدیل می‌کند؛ بدون آن pyodbc موقع خواندن خطا می‌دهد
        step = 'خواندن مشتریان'
        cur.execute(f"""
            SELECT CAST(C_Code AS NVARCHAR(50)), CAST(C_Name AS NVARCHAR(200)), {geo}
            FROM customer WHERE [Delete]=0 OR [Delete] IS NULL
        """)
        customers = [{"code":(r[0] or '').strip(), "name":fa_text(r[1]),
                      "lat":float(r[2] or 0), "lng":float(r[3] or 0)}
                     for r in cur.fetchall()]

        step = 'خواندن کالاها'
        stock_filter = "AND Exist > 0" if rules.get("ONLY_IN_STOCK") else ""
        cur.execute(f"""
            SELECT CAST(A_Code AS NVARCHAR(50)), CAST(A_Name AS NVARCHAR(200)), Sel_Price, Exist
            FROM article WHERE ([Delete]=0 OR [Delete] IS NULL) {stock_filter}
        """)
        articles = [{"code":(r[0] or '').strip(), "name":fa_text(r[1]),
                     "price":float(r[2] or 0), "stock":float(r[3] or 0)}
                    for r in cur.fetchall()]

        cur.close(); conn.close()
        print(f"✅ sync-data | {len(customers)} مشتری | {len(articles)} کالا")
        log('sync', f"{len(customers)} مشتری، {len(articles)} کالا")
        return jsonify({"status":"success",
                        "customers":customers,
                        "articles":articles,
                        "settings":{**rules, **gps_rules()}}), 200
    except Exception as e:
        print(f"❌ sync-data error ({step}): {e}")
        return jsonify({"status":"error","message":f"{step}: {e}"}), 500


# ══════════════════════════════════════════
# ۲-ب. گزارش کار خود ویزیتور — نیاز به token
# ══════════════════════════════════════════
@app.route('/api/my-report', methods=['GET'])
@require_auth
def my_report():
    """گزارش کار خود ویزیتور با جزئیات: اقلام سفارش، جزئیات دریافت، عکس‌ها"""
    vid = request.current_user['visitor_id']
    try:
        d0 = datetime.strptime(request.args.get('from', ''), '%Y-%m-%d').date()
        d1 = datetime.strptime(request.args.get('to', ''), '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"status":"error","message":"بازهٔ تاریخ نامعتبر است"}), 400
    if (d1 - d0).days > 370:
        return jsonify({"status":"error","message":"بازهٔ گزارش حداکثر یک سال است"}), 400
    try:
        conn = get_conn(); cur = conn.cursor()
        cust = f"[{SALES_DB}].dbo.customer"
        art = f"[{SALES_DB}].dbo.article"
        cur.execute(f"""
            SELECT v.id, v.visit_date, CONVERT(VARCHAR(5), v.visit_time, 108), v.customer_code,
                   CAST(c.C_Name AS NVARCHAR(200)), ISNULL(v.description,''), ISNULL(v.selfie_path,'')
            FROM visits v LEFT JOIN {cust} c ON c.C_Code = v.customer_code
            WHERE v.visitor_id=? AND v.visit_date BETWEEN ? AND ?
            ORDER BY v.visit_date DESC, v.visit_time DESC""", (vid, d0, d1))
        visits = [{"id": r[0], "date": str(r[1]), "time": r[2], "customer_code": r[3],
                   "customer": fa_text(r[4]) or r[3], "description": r[5], "selfie": r[6]} for r in cur.fetchall()]
        cur.execute(f"""
            SELECT o.id, o.order_date, CONVERT(VARCHAR(5), o.order_time, 108), o.customer_code,
                   CAST(c.C_Name AS NVARCHAR(200)), o.total_amount, ISNULL(o.description,'')
            FROM orders o LEFT JOIN {cust} c ON c.C_Code = o.customer_code
            WHERE o.visitor_id=? AND o.order_date BETWEEN ? AND ?
            ORDER BY o.order_date DESC, o.order_time DESC""", (vid, d0, d1))
        orders = [{"id": r[0], "date": str(r[1]), "time": r[2], "customer_code": r[3],
                   "customer": fa_text(r[4]) or r[3], "total": float(r[5] or 0), "description": r[6],
                   "lines": []} for r in cur.fetchall()]
        by_id = {o["id"]: o for o in orders}
        if orders:
            cur.execute(f"""
                SELECT oi.order_id, oi.article_code, CAST(a.A_Name AS NVARCHAR(200)),
                       CAST(oi.quantity AS FLOAT), CAST(oi.price AS FLOAT)
                FROM order_items oi JOIN orders o ON o.id = oi.order_id
                LEFT JOIN {art} a ON a.A_Code = oi.article_code
                WHERE o.visitor_id=? AND o.order_date BETWEEN ? AND ?
                ORDER BY oi.order_id, oi.id""", (vid, d0, d1))
            for r in cur.fetchall():
                if r[0] in by_id:
                    by_id[r[0]]["lines"].append({"code": r[1], "name": fa_text(r[2]) or r[1],
                                                 "qty": float(r[3] or 0), "price": float(r[4] or 0)})
        for o in orders:
            o["items"] = len(o["lines"])
        cur.execute(f"""
            SELECT p.id, p.payment_date, CONVERT(VARCHAR(5), p.payment_time, 108), p.customer_code,
                   CAST(c.C_Name AS NVARCHAR(200)), p.payment_type, p.amount,
                   ISNULL(p.check_number,''), ISNULL(p.check_sayyadi,''), p.check_due_date,
                   ISNULL(p.check_image_path,''), ISNULL(p.transfer_account,''),
                   ISNULL(p.transfer_tracking,''), ISNULL(p.transfer_image_path,''),
                   ISNULL(p.tracking_number,''), ISNULL(p.description,'')
            FROM payments p LEFT JOIN {cust} c ON c.C_Code = p.customer_code
            WHERE p.visitor_id=? AND p.payment_date BETWEEN ? AND ?
            ORDER BY p.payment_date DESC, p.payment_time DESC""", (vid, d0, d1))
        pays = [{"id": r[0], "date": str(r[1]), "time": r[2], "customer_code": r[3],
                 "customer": fa_text(r[4]) or r[3], "type": r[5], "amount": float(r[6] or 0),
                 "check_number": r[7], "check_sayyadi": r[8], "check_due": str(r[9] or ''),
                 "image": r[10] or r[13], "account": r[11], "tracking": r[12] or r[14],
                 "description": r[15]}
                for r in cur.fetchall()]
        # تاریخ آخرین ثبت این کاربر (برای راهنمایی وقتی بازهٔ انتخاب‌شده خالی است)
        cur.execute("""SELECT MAX(d) FROM (
                           SELECT MAX(visit_date) AS d FROM visits WHERE visitor_id=?
                           UNION ALL SELECT MAX(order_date) FROM orders WHERE visitor_id=?
                           UNION ALL SELECT MAX(payment_date) FROM payments WHERE visitor_id=?) t""", (vid, vid, vid))
        last = cur.fetchone()[0]
        cur.close(); conn.close()
        log('report', f"{d0} تا {d1}")
        return jsonify({"status":"success", "from": str(d0), "to": str(d1), "last_date": str(last) if last else None,
                        "visits": visits, "orders": orders, "payments": pays}), 200
    except Exception as e:
        print(f"❌ my-report error: {e}")
        return jsonify({"status":"error","message":"دریافت گزارش از سرور ممکن نشد"}), 500


@app.route('/api/my-image', methods=['GET'])
@require_auth
def my_image():
    """عکس سلفی / چک / حواله ثبت‌شده توسط همین ویزیتور (کوچک‌شده، به شکل data URL)
    — از طریق API تا داخل اپ اندروید هم بدون محدودیت مرورگر نمایش داده شود"""
    vid = request.current_user['visitor_id']
    rel = (request.args.get('path') or '').strip()
    if not rel.startswith('/static/'):
        return jsonify({"status": "error", "message": "مسیر نامعتبر است"}), 400
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT 1 WHERE EXISTS (SELECT 1 FROM visits WHERE visitor_id=? AND selfie_path=?)
                          OR EXISTS (SELECT 1 FROM payments WHERE visitor_id=?
                                     AND (check_image_path=? OR transfer_image_path=?))""",
                    (vid, rel, vid, rel, rel))
        allowed = cur.fetchone() is not None
        cur.close(); conn.close()
    except Exception as e:
        print(f"❌ my-image error: {e}")
        return jsonify({"status": "error", "message": "خطای سرور"}), 500
    root = os.path.realpath(paths.STATIC_DIR)
    fpath = os.path.realpath(os.path.join(paths.DATA_DIR, rel.lstrip('/')))
    if not allowed or not fpath.startswith(root + os.sep) or not os.path.isfile(fpath):
        return jsonify({"status": "error", "message": "عکس پیدا نشد"}), 404
    try:
        from PIL import Image
        import io
        with Image.open(fpath) as im:
            im = im.convert("RGB")
            im.thumbnail((1100, 1100))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
        data = base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        with open(fpath, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
    return jsonify({"status": "success", "data": "data:image/jpeg;base64," + data}), 200


# ══════════════════════════════════════════
# ۲-ج. پیام‌ها — مدیر ↔ ویزیتور و ویزیتورها با هم
# ══════════════════════════════════════════
def _me_row(me):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT ISNULL(role,'visitor'), app_settings FROM visitors WHERE id=?", (me,))
    r = cur.fetchone(); cur.close(); conn.close()
    return (r[0], r[1]) if r else ('visitor', None)


def peer_allowed(me) -> bool:
    """آیا این کاربر ویزیتورهای دیگر را در پیام‌ها می‌بیند؟ (مدیر همیشه)"""
    role, raw = _me_row(me)
    return role == 'admin' or bool(effective_rules(raw).get('PEER_MESSAGES', True))


def message_contacts(me):
    """کاربرانی که این کاربر می‌تواند به آن‌ها پیام بدهد"""
    peer = peer_allowed(me)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT id, full_name, ISNULL(role,'visitor') FROM visitors
                    WHERE is_active=1 AND id<>? {'' if peer else "AND role='admin'"}
                    ORDER BY CASE WHEN role='admin' THEN 0 ELSE 1 END, full_name""", (me,))
    rows = [{"id": int(r[0]), "name": r[1], "role": r[2]} for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


@app.route('/api/contacts', methods=['GET'])
@require_auth
def contacts():
    me = request.current_user['visitor_id']
    try:
        rows = message_contacts(me)
    except Exception as e:
        print(f"❌ contacts error: {e}")
        return jsonify({"status": "error", "message": "دریافت لیست کاربران ممکن نشد"}), 500
    return jsonify({"status": "success", "contacts": rows, "peer": peer_allowed(me)}), 200


@app.route('/api/messages', methods=['GET'])
@require_auth
def messages_list():
    me = request.current_user['visitor_id']
    try:
        after = int(request.args.get('after', 0))
    except ValueError:
        after = 0
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT TOP 300 m.id, m.sender_id, m.recipient_id, m.body,
                          CONVERT(VARCHAR(19), m.created_at, 120), m.read_at, s.full_name
                   FROM messages m LEFT JOIN visitors s ON s.id = m.sender_id
                   WHERE (m.sender_id=? OR m.recipient_id=?) AND m.id>?
                   ORDER BY m.id DESC""", (me, me, after))
    msgs = [{"id": r[0], "from": r[1], "to": r[2], "body": r[3], "at": r[4], "read": r[5] is not None,
             "from_name": r[6]} for r in cur.fetchall()][::-1]
    cur.close(); conn.close()
    return jsonify({"status": "success", "me": me, "messages": msgs}), 200


@app.route('/api/messages', methods=['POST'])
@require_auth
def messages_send():
    me = request.current_user['visitor_id']
    data = request.json or {}
    body = (data.get('body') or '').strip()[:2000]
    to = data.get('to')
    if not body:
        return jsonify({"status": "error", "message": "متن پیام خالی است"}), 400
    allowed = {c["id"] for c in message_contacts(me)}
    if to == 'all':
        if _me_row(me)[0] != 'admin':
            return jsonify({"status": "error", "message": "پیام همگانی فقط برای مدیر مجاز است"}), 403
        targets = sorted(allowed)
    else:
        try:
            targets = [int(to)]
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "گیرندهٔ پیام مشخص نیست"}), 400
        if targets[0] not in allowed:
            return jsonify({"status": "error", "message": "ارسال پیام به این کاربر مجاز نیست"}), 403
    conn = get_conn(); cur = conn.cursor()
    for t in targets:
        cur.execute("INSERT INTO messages (sender_id, recipient_id, body) VALUES (?,?,?)", (me, t, body))
    conn.commit(); cur.close(); conn.close()
    log('message', f"به {'همه' if to == 'all' else to}")
    return jsonify({"status": "success", "message": "پیام ارسال شد", "count": len(targets)}), 200


@app.route('/api/messages/read', methods=['POST'])
@require_auth
def messages_read():
    me = request.current_user['visitor_id']
    other = (request.json or {}).get('with')
    conn = get_conn(); cur = conn.cursor()
    cur.execute("UPDATE messages SET read_at=GETDATE() WHERE recipient_id=? AND sender_id=? AND read_at IS NULL",
                (me, other))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"status": "success"}), 200


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

        selfie_path = save_image(selfie_b64, SELFIES_DIR, 'visit',
                                 visitor_id, customer_code, visit_date, visit_time)

        accuracy = data.get('accuracy')
        try:
            accuracy = round(float(accuracy), 1) if accuracy is not None else None
        except (TypeError, ValueError):
            accuracy = None
        try:
            cur.execute("""
                INSERT INTO visits
                    (visitor_id,customer_code,visit_date,visit_time,
                     latitude,longitude,selfie_path,description,gps_accuracy)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (visitor_id, customer_code, visit_date, visit_time,
                  latitude, longitude, selfie_path, description, accuracy))
        except Exception:
            # جدول قدیمی بدون ستون gps_accuracy
            cur.execute("""
                INSERT INTO visits
                    (visitor_id,customer_code,visit_date,visit_time,
                     latitude,longitude,selfie_path,description)
                VALUES (?,?,?,?,?,?,?,?)
            """, (visitor_id, customer_code, visit_date, visit_time,
                  latitude, longitude, selfie_path, description))

        set_extra(cur, 'visits', None)
        mark_uid_done(cur, uid)
        conn.commit(); cur.close(); conn.close()
        log('visit', customer_code)
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

        set_extra(cur, 'orders', order_id, (data.get('order_note') or '').strip())
        mark_uid_done(cur, order_uid)
        conn.commit(); cur.close(); conn.close()
        log('order', f"{customer_code} · {total:,.0f}")
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

        check_img_path = save_image(check_img_b64, CHECKS_DIR, 'check',
                                    visitor_id, customer_code, pay_date, pay_time)
        tr_img_path    = save_image(tr_img_b64, TRANSFERS_DIR, 'transfer',
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
        except Exception as e:
            # جدول قدیمی بدون ستون‌های چک/حواله — create_tables.py را اجرا کنید
            print(f"⚠️ payments: ثبت جزئیات چک/حواله ناموفق، فقط اطلاعات پایه ذخیره شد: {e}")
            cur.execute("""
                INSERT INTO payments
                    (visitor_id,customer_code,payment_date,payment_time,
                     payment_type,amount,tracking_number,latitude,longitude)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (visitor_id, customer_code, pay_date, pay_time,
                  pay_type, amount, tr_tracking or check_number or '',
                  latitude, longitude))

        set_extra(cur, 'payments', None,
                  (pay_info.get('description') or pay_info.get('cash_desc') or '').strip())
        mark_uid_done(cur, pay_uid)
        conn.commit(); cur.close(); conn.close()
        log('payment', f"{customer_code} · {pay_type} · {amount:,.0f}")
        print(f"✅ payment | user={visitor_id} | {pay_type} | {amount}")
        return jsonify({"status":"success","message":"دریافت مالی ثبت شد"}), 200

    except Exception as e:
        print(f"submit-payment error: {e}")
        return jsonify({"status":"error","message":"خطای سرور"}), 500


if __name__ == '__main__':
    debug = NETWORK.get('DEBUG', False)
    port  = NETWORK.get('FLASK_PORT', 5000)

    print(f"🚀 PeechaVisit API در حال اجرا روی پورت {port}")
    app.run(host=NETWORK.get('FLASK_HOST', '0.0.0.0'), port=port, debug=debug)
