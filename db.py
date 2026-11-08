# db.py - پیچا ویزیت | اتصال مشترک به SQL Server
# ════════════════════════════════════════════════
# همهٔ سرویس‌ها از همین تابع برای اتصال استفاده می‌کنند
# تنظیمات از config.py / settings.json خوانده می‌شود
# ════════════════════════════════════════════════
import pyodbc
from config import NETWORK, DATABASES

TRACKING_DB = DATABASES["TRACKING_DB"]
SALES_DB    = DATABASES["SALES_DB"]


def conn_str(db: str | None = None) -> str:
    parts = [
        f'DRIVER={{{DATABASES["DRIVER"]}}}',
        f'SERVER={NETWORK["SERVER_NAME"]}',
    ]
    if db:
        parts.append(f"DATABASE={db}")
    if DATABASES.get("USER"):
        pwd = DATABASES.get("PASSWORD", "").replace("}", "}}")
        parts += [f'UID={DATABASES["USER"]}', f"PWD={{{pwd}}}"]
    else:
        parts.append("Trusted_Connection=yes")
    if DATABASES.get("EXTRA"):
        parts.append(DATABASES["EXTRA"].strip(";"))
    return ";".join(parts) + ";"


def get_conn(db: str | None = TRACKING_DB, autocommit: bool = False):
    return pyodbc.connect(conn_str(db), autocommit=autocommit,
                          timeout=int(DATABASES.get("TIMEOUT", 30)))
