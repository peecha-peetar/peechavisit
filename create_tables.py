# create_tables.py - پیچا ویزیت v2.0
# ════════════════════════════════════════════════════════
# این اسکریپت را فقط یک‌بار اجرا کنید
# تمام جداول دیتابیس tracking را می‌سازد
# اگر جدول قبلاً وجود داشته باشد، بدون خطا رد می‌شود
# ════════════════════════════════════════════════════════

import pyodbc
from datetime import datetime

# خواندن از config.py
try:
    from config import NETWORK
    SERVER = NETWORK["SERVER_NAME"]
except ImportError:
    SERVER = 'SERWIN\\RAD'  # fallback


def get_conn(db=None, autocommit=False):
    cs = f'DRIVER={{SQL Server}};SERVER={SERVER};Trusted_Connection=yes;'
    if db:
        cs += f'DATABASE={db};'
    return pyodbc.connect(cs, autocommit=autocommit)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ════════════════════════════════════════
# ۱. ساخت دیتابیس tracking
# ════════════════════════════════════════
def create_database():
    log("بررسی وجود دیتابیس tracking ...")
    conn = get_conn(autocommit=True)
    cur  = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = 'tracking')
        BEGIN
            CREATE DATABASE tracking;
            PRINT 'دیتابیس tracking ساخته شد.';
        END
        ELSE
            PRINT 'دیتابیس tracking از قبل وجود دارد.';
    """)
    cur.close()
    conn.close()
    log("✅ دیتابیس tracking آماده است.")


# ════════════════════════════════════════
# ۲. ساخت جداول
# ════════════════════════════════════════
def create_tables():
    conn = get_conn(db='tracking')
    cur  = conn.cursor()

    # ────────────────────────────────────
    # جدول ویزیتورها (کاربران)
    # ────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'visitors')
        BEGIN
            CREATE TABLE visitors (
                id               INT IDENTITY(1,1) PRIMARY KEY,
                username         VARCHAR(50)       NOT NULL UNIQUE,
                password_hash    VARCHAR(255)      NOT NULL,
                full_name        NVARCHAR(100)     NOT NULL,
                role             VARCHAR(20)       NOT NULL DEFAULT 'visitor',
                phone            VARCHAR(20)       NULL,
                is_active        BIT               NOT NULL DEFAULT 1,
                last_login       DATETIME          NULL,
                failed_attempts  INT               NOT NULL DEFAULT 0,
                locked_until     DATETIME          NULL,
                notes            NVARCHAR(500)     NULL,
                created_at       DATETIME          NOT NULL DEFAULT GETDATE()
            );
            PRINT 'جدول visitors ساخته شد.';
        END
    """)
    log("✅ جدول visitors")

    # ────────────────────────────────────
    # کاربر پیش‌فرض: admin / admin123
    # SHA256("admin123") = 240be518...
    # ────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM visitors WHERE username = 'admin')
        BEGIN
            INSERT INTO visitors
                (username, password_hash, full_name, role, is_active)
            VALUES
                ('admin',
                 '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
                 N'مدیر سیستم',
                 'admin',
                 1);
            PRINT 'کاربر admin پیش‌فرض ساخته شد (رمز: admin123)';
        END
    """)

    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM visitors WHERE username = 'visitor1')
        BEGIN
            INSERT INTO visitors
                (username, password_hash, full_name, role, is_active)
            VALUES
                ('visitor1',
                 '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
                 N'علی علوی',
                 'visitor',
                 1);
            PRINT 'کاربر visitor1 پیش‌فرض ساخته شد (رمز: admin123)';
        END
    """)
    log("✅ کاربران پیش‌فرض")

    # ────────────────────────────────────
    # جدول uid‌های ارسال‌شده (جلوگیری از ثبت تکراری)
    # ────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'submitted_uids')
        BEGIN
            CREATE TABLE submitted_uids (
                uid          VARCHAR(100)  NOT NULL PRIMARY KEY,
                submitted_at DATETIME      NOT NULL DEFAULT GETDATE()
            );
            PRINT 'جدول submitted_uids ساخته شد.';
        END
    """)
    log("✅ جدول submitted_uids")

    # ────────────────────────────────────
    # جدول ویزیت‌ها
    # ────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'visits')
        BEGIN
            CREATE TABLE visits (
                id            INT IDENTITY(1,1) PRIMARY KEY,
                visitor_id    INT            NOT NULL,
                customer_code VARCHAR(10)    NOT NULL,
                visit_date    DATE           NOT NULL,
                visit_time    TIME           NOT NULL,
                latitude      FLOAT          NOT NULL,
                longitude     FLOAT          NOT NULL,
                selfie_path   NVARCHAR(500)  NULL,
                description   NVARCHAR(MAX)  NULL,
                created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
                CONSTRAINT FK_visits_visitor
                    FOREIGN KEY (visitor_id) REFERENCES visitors(id)
            );
            CREATE INDEX IX_visits_visitor_date
                ON visits (visitor_id, visit_date);
            PRINT 'جدول visits ساخته شد.';
        END
    """)
    log("✅ جدول visits")

    # ────────────────────────────────────
    # جدول سفارشات
    # ────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'orders')
        BEGIN
            CREATE TABLE orders (
                id            INT IDENTITY(1,1) PRIMARY KEY,
                visitor_id    INT            NOT NULL,
                customer_code VARCHAR(10)    NOT NULL,
                order_date    DATE           NOT NULL,
                order_time    TIME           NOT NULL,
                latitude      FLOAT          NOT NULL,
                longitude     FLOAT          NOT NULL,
                total_amount  FLOAT          NOT NULL DEFAULT 0,
                created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
                CONSTRAINT FK_orders_visitor
                    FOREIGN KEY (visitor_id) REFERENCES visitors(id)
            );
            CREATE INDEX IX_orders_visitor_date
                ON orders (visitor_id, order_date);
            PRINT 'جدول orders ساخته شد.';
        END
    """)
    log("✅ جدول orders")

    # ────────────────────────────────────
    # جدول اقلام سفارش
    # ────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'order_items')
        BEGIN
            CREATE TABLE order_items (
                id           INT IDENTITY(1,1) PRIMARY KEY,
                order_id     INT            NOT NULL,
                article_code VARCHAR(10)    NOT NULL,
                quantity     FLOAT          NOT NULL,
                price        FLOAT          NOT NULL,
                CONSTRAINT FK_order_items_order
                    FOREIGN KEY (order_id) REFERENCES orders(id)
            );
            PRINT 'جدول order_items ساخته شد.';
        END
    """)
    log("✅ جدول order_items")

    # ────────────────────────────────────
    # جدول دریافت‌های مالی
    # ────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'payments')
        BEGIN
            CREATE TABLE payments (
                id                  INT IDENTITY(1,1) PRIMARY KEY,
                visitor_id          INT             NOT NULL,
                customer_code       VARCHAR(10)     NOT NULL,
                payment_date        DATE            NOT NULL,
                payment_time        TIME            NOT NULL,
                payment_type        NVARCHAR(20)    NOT NULL,
                amount              FLOAT           NOT NULL,
                tracking_number     VARCHAR(60)     NULL,
                latitude            FLOAT           NOT NULL,
                longitude           FLOAT           NOT NULL,
                -- فیلدهای چک
                check_number        VARCHAR(50)     NULL,
                check_sayyadi       VARCHAR(50)     NULL,
                check_due_date      DATE            NULL,
                check_image_path    NVARCHAR(500)   NULL,
                -- فیلدهای حواله
                transfer_account    VARCHAR(100)    NULL,
                transfer_tracking   VARCHAR(100)    NULL,
                transfer_image_path NVARCHAR(500)   NULL,
                created_at          DATETIME        NOT NULL DEFAULT GETDATE(),
                CONSTRAINT FK_payments_visitor
                    FOREIGN KEY (visitor_id) REFERENCES visitors(id)
            );
            CREATE INDEX IX_payments_visitor_date
                ON payments (visitor_id, payment_date);
            PRINT 'جدول payments ساخته شد.';
        END
    """)
    log("✅ جدول payments")

    conn.commit()
    cur.close()
    conn.close()


# ════════════════════════════════════════
# ۳. اضافه کردن ستون‌های جدید به جداول موجود
#    (در صورتی که قبلاً ساخته شده‌اند)
# ════════════════════════════════════════
def alter_existing_tables():
    conn = get_conn(db='tracking', autocommit=True)
    cur  = conn.cursor()

    # ─── visitors: ستون‌های جدید ───
    visitor_cols = [
        ("role",           "VARCHAR(20) NOT NULL DEFAULT 'visitor'"),
        ("phone",          "VARCHAR(20) NULL"),
        ("last_login",     "DATETIME NULL"),
        ("failed_attempts","INT NOT NULL DEFAULT 0"),
        ("locked_until",   "DATETIME NULL"),
        ("notes",          "NVARCHAR(500) NULL"),
        ("created_at",     "DATETIME NOT NULL DEFAULT GETDATE()"),
    ]
    for col, dtype in visitor_cols:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('visitors') AND name = '{col}'
            )
            ALTER TABLE visitors ADD {col} {dtype};
        """)

    # ─── payments: ستون‌های چک و حواله ───
    payment_cols = [
        ("check_number",        "VARCHAR(50) NULL"),
        ("check_sayyadi",       "VARCHAR(50) NULL"),
        ("check_due_date",      "DATE NULL"),
        ("check_image_path",    "NVARCHAR(500) NULL"),
        ("transfer_account",    "VARCHAR(100) NULL"),
        ("transfer_tracking",   "VARCHAR(100) NULL"),
        ("transfer_image_path", "NVARCHAR(500) NULL"),
        ("created_at",          "DATETIME NOT NULL DEFAULT GETDATE()"),
    ]
    for col, dtype in payment_cols:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('payments') AND name = '{col}'
            )
            ALTER TABLE payments ADD {col} {dtype};
        """)

    # ─── visits: created_at ───
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.columns
            WHERE object_id = OBJECT_ID('visits') AND name = 'created_at'
        )
        ALTER TABLE visits ADD created_at DATETIME NOT NULL DEFAULT GETDATE();
    """)

    # ─── orders: created_at ───
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.columns
            WHERE object_id = OBJECT_ID('orders') AND name = 'created_at'
        )
        ALTER TABLE orders ADD created_at DATETIME NOT NULL DEFAULT GETDATE();
    """)

    cur.close()
    conn.close()
    log("✅ ستون‌های جدید اضافه شدند (در صورت نبودن)")


# ════════════════════════════════════════
# ۴. نمایش خلاصه جداول
# ════════════════════════════════════════
def show_summary():
    conn = get_conn(db='tracking')
    cur  = conn.cursor()

    tables = ['visitors', 'visits', 'orders', 'order_items', 'payments', 'submitted_uids']
    print()
    print("=" * 52)
    print("  📊 خلاصه جداول دیتابیس tracking")
    print("=" * 52)
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            cnt = cur.fetchone()[0]
            print(f"  {'✅':<3} {t:<25} {cnt:>6} رکورد")
        except Exception as e:
            print(f"  ❌  {t:<25} خطا: {e}")

    # نمایش کاربران
    try:
        cur.execute("SELECT username, full_name, role, is_active FROM visitors ORDER BY id")
        rows = cur.fetchall()
        if rows:
            print()
            print("  👥 کاربران تعریف‌شده:")
            for r in rows:
                status = "✅ فعال" if r[3] else "❌ غیرفعال"
                print(f"     @{r[0]:<14} {r[1]:<16} [{r[2]}] {status}")
    except: pass

    print("=" * 52)
    print()
    cur.close()
    conn.close()


# ════════════════════════════════════════
# اجرای اصلی
# ════════════════════════════════════════
if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   پیچا ویزیت | راه‌اندازی دیتابیس      ║")
    print("╚══════════════════════════════════════════╝")
    print()

    try:
        create_database()
        create_tables()
        alter_existing_tables()
        show_summary()

        print("🎉 راه‌اندازی با موفقیت انجام شد!")
        print()
        print("📌 اکنون می‌توانید سرویس‌ها را اجرا کنید:")
        print("   python app.py")
        print("   python run_client.py")
        print("   streamlit run dashboard.py --server.port 8501")
        print("   streamlit run admin.py     --server.port 8502")
        print()
        print("🔑 ورود پیش‌فرض:")
        print("   نام کاربری: admin     رمز: admin123")
        print("   نام کاربری: visitor1  رمز: admin123")
        print()

    except Exception as e:
        print(f"\n❌ خطا: {e}")
        raise
