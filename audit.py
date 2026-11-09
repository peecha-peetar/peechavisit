# audit.py - پیچا ویزیت | جدول‌های پیام و لاگ + ثبت رویدادها
# ════════════════════════════════════════════════
# ensure_schema() ستون‌ها و جدول‌های جدید را (اگر نباشند) می‌سازد.
# log_event()     ورود، همگام‌سازی، ثبت‌ها و ... را با اطلاعات دستگاه ذخیره می‌کند.
# ════════════════════════════════════════════════
from db import get_conn

_SCHEMA = [
    # توضیحات سفارش و دریافت
    ("orders", "description", "NVARCHAR(1000) NULL"),
    ("payments", "description", "NVARCHAR(1000) NULL"),
    # دستگاه ثبت‌کننده (برند، مدل، اندروید)
    ("visits", "device", "NVARCHAR(200) NULL"),
    ("orders", "device", "NVARCHAR(200) NULL"),
    ("payments", "device", "NVARCHAR(200) NULL"),
]

_TABLES = {
    "messages": """
        CREATE TABLE messages (
            id           INT IDENTITY(1,1) PRIMARY KEY,
            sender_id    INT            NOT NULL,
            recipient_id INT            NOT NULL,
            body         NVARCHAR(2000) NOT NULL,
            created_at   DATETIME       NOT NULL DEFAULT GETDATE(),
            read_at      DATETIME       NULL
        );
        CREATE INDEX IX_messages_recipient ON messages (recipient_id, id);
        CREATE INDEX IX_messages_sender ON messages (sender_id, id);""",
    "access_log": """
        CREATE TABLE access_log (
            id          INT IDENTITY(1,1) PRIMARY KEY,
            visitor_id  INT            NULL,
            username    NVARCHAR(50)   NULL,
            source      VARCHAR(20)    NOT NULL,
            event       VARCHAR(30)    NOT NULL,
            ip          VARCHAR(45)    NULL,
            device      NVARCHAR(200)  NULL,
            detail      NVARCHAR(400)  NULL,
            created_at  DATETIME       NOT NULL DEFAULT GETDATE()
        );
        CREATE INDEX IX_access_log_time ON access_log (created_at);""",
    # مشتری جدیدی که ویزیتور در اپ ثبت می‌کند — فقط در tracking (نه در دیتابیس فروش)
    "new_customers": """
        CREATE TABLE new_customers (
            id           INT IDENTITY(1,1) PRIMARY KEY,
            code         VARCHAR(10)    NOT NULL UNIQUE,
            name         NVARCHAR(200)  NOT NULL,
            contact      NVARCHAR(100)  NULL,
            phone        NVARCHAR(40)   NULL,
            mobile       NVARCHAR(40)   NULL,
            city         NVARCHAR(60)   NULL,
            address      NVARCHAR(400)  NULL,
            national_id  NVARCHAR(20)   NULL,
            description  NVARCHAR(400)  NULL,
            latitude     FLOAT          NULL,
            longitude    FLOAT          NULL,
            visitor_id   INT            NOT NULL,
            device       NVARCHAR(200)  NULL,
            status       VARCHAR(12)    NOT NULL DEFAULT 'new',
            sales_code   VARCHAR(50)    NULL,
            created_at   DATETIME       NOT NULL DEFAULT GETDATE()
        );""",
}

EVENT_LABELS = {
    "login": "ورود", "login_failed": "ورود ناموفق", "sync": "دریافت لیست‌ها",
    "visit": "ثبت ویزیت", "order": "ثبت سفارش", "payment": "ثبت دریافت",
    "report": "مشاهدهٔ گزارش", "message": "ارسال پیام", "logout": "خروج",
    "new_customer": "ثبت مشتری جدید",
}
SOURCE_LABELS = {"app": "اپ موبایل", "dashboard": "داشبورد", "admin": "پنل مدیریت"}


def ensure_schema():
    conn = get_conn(autocommit=True); cur = conn.cursor()
    try:
        for table, col, ddl in _SCHEMA:
            cur.execute(f"""IF NOT EXISTS (SELECT 1 FROM sys.columns
                            WHERE object_id=OBJECT_ID('{table}') AND name='{col}')
                            ALTER TABLE {table} ADD {col} {ddl}""")
        for name, ddl in _TABLES.items():
            cur.execute(f"IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='{name}') BEGIN {ddl} END")
    finally:
        cur.close(); conn.close()


def log_event(source, event, visitor_id=None, username=None, ip=None, device=None, detail=None):
    """ثبت یک رویداد؛ خطای لاگ هرگز نباید کار اصلی را متوقف کند"""
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""INSERT INTO access_log (visitor_id, username, source, event, ip, device, detail)
                       VALUES (?,?,?,?,?,?,?)""",
                    (visitor_id, (username or "")[:50] or None, source[:20], event[:30],
                     (ip or "")[:45] or None, (device or "")[:200] or None, (detail or "")[:400] or None))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"⚠️ log_event: {e}")
