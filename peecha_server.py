# peecha_server.py - پیچا ویزیت | اجرای همهٔ سرویس‌ها از یک برنامه
# ════════════════════════════════════════════════
# این فایل نقطهٔ شروع نسخهٔ نصبی (PeechaVisit.exe) است و در حالت توسعه
# هم با «python peecha_server.py» کار می‌کند.
#
#   PeechaVisit.exe                 همهٔ سرویس‌ها (API، وب‌اپ، داشبورد، پنل)
#   PeechaVisit.exe --check         آزمایش اتصال به دیتابیس
#   PeechaVisit.exe --configure ... ذخیرهٔ تنظیمات دیتابیس (برای نصب‌کننده)
#
# سرویس ویندوز (WinSW) همین برنامه را بدون آرگومان اجرا می‌کند؛ اگر یکی از
# سرویس‌ها از کار بیفتد چند ثانیه بعد دوباره اجرا می‌شود.
# ════════════════════════════════════════════════
import sys as _sys
# خروجی همیشه UTF-8: در ویندوز فارسی (cp1256) چاپ ✅/❌ در لاگ، برنامه را از کار می‌انداخت
for _s in (_sys.stdout, _sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import argparse
import os
import secrets
import signal
import subprocess
import sys
import threading
import time

import paths

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

SERVICES = ("api", "pwa", "dashboard", "admin")


def _say(msg):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp}  {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(os.path.join(paths.LOG_DIR, "service.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ══════════════════════════════════════════
# اگر برنامهٔ اصلی بسته شود، سرویس‌های فرزند هم بسته می‌شوند
# ══════════════════════════════════════════
def _parent_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x00100000, False, pid)          # SYNCHRONIZE
        if not h:
            return False
        try:
            return k32.WaitForSingleObject(h, 0) == 0x102    # WAIT_TIMEOUT → هنوز زنده
        finally:
            k32.CloseHandle(h)
    return os.getppid() == pid


def _watch_parent():
    pid = int(os.environ.get("PEECHA_PARENT") or 0)
    if not pid:
        return

    def loop():
        while True:
            time.sleep(3)
            if not _parent_alive(pid):
                os._exit(0)
    threading.Thread(target=loop, daemon=True, name="parent-watch").start()


# ══════════════════════════════════════════
# سرویس‌ها
# ══════════════════════════════════════════
def run_api():
    from config import NETWORK
    import app as api
    port = int(NETWORK.get("FLASK_PORT", 5000))
    host = NETWORK.get("FLASK_HOST", "0.0.0.0")
    _say(f"API روی پورت {port}")
    try:
        from waitress import serve
    except ImportError:                  # setup.bat هنوز اجرا نشده: سرور سادهٔ Flask
        _say("⚠️ waitress نصب نیست (setup.bat را دوباره اجرا کنید) — اجرای API با سرور Flask")
        api.app.run(host=host, port=port, threaded=True)
        return
    serve(api.app, host=host, port=port, threads=16, ident="PeechaVisit", max_request_body_size=64 * 1024 * 1024)


def run_pwa():
    import http.server
    from config import NETWORK
    folder = os.path.join(paths.RES_DIR, "pwa_client")
    port = int(NETWORK.get("PWA_PORT", 8000))

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=folder, **kw)

        def log_message(self, *a):
            pass

    _say(f"وب‌اپ موبایل روی پورت {port}")
    http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


def _streamlit_flags(port: int) -> dict:
    """تنظیمات Streamlit: فایل .streamlit/config.toml همراه برنامه + چند گزینهٔ ثابت"""
    flags = {}
    try:
        import tomllib
        with open(os.path.join(paths.RES_DIR, ".streamlit", "config.toml"), "rb") as f:
            for sec, values in tomllib.load(f).items():
                for k, v in values.items():
                    flags[f"{sec}_{k}"] = v
    except (OSError, ValueError):
        pass
    flags.update({
        "server_port": port,
        "server_headless": True,
        "server_fileWatcherType": "none",
        "server_runOnSave": False,
        "global_developmentMode": False,
        "browser_gatherUsageStats": False,
        "client_toolbarMode": "viewer",
        "client_showErrorDetails": "none" if paths.FROZEN else "full",
    })
    return flags


def run_streamlit(name: str):
    """داشبورد یا پنل مدیریت. Streamlit یک فایل اسکریپت می‌خواهد؛ این فایل کوچک
    فقط ماژول اصلی (که داخل برنامه و به شکل کامپایل‌شده است) را اجرا می‌کند."""
    from config import NETWORK
    port = int(NETWORK.get("DASHBOARD_PORT" if name == "dashboard" else "ADMIN_PORT",
                           8501 if name == "dashboard" else 8502))
    run_dir = os.path.join(paths.DATA_DIR, "run")
    os.makedirs(run_dir, exist_ok=True)
    stub = os.path.join(run_dir, f"{name}_main.py")
    code = ("# فایل خودکار پیچا ویزیت — تغییر ندهید\n"
            "import runpy\n"
            f"runpy.run_module({name!r}, run_name='__main__')\n")
    try:
        with open(stub, encoding="utf-8") as f:
            same = f.read() == code
    except OSError:
        same = False
    if not same:
        with open(stub, "w", encoding="utf-8") as f:
            f.write(code)

    if paths.RES_DIR not in sys.path:
        sys.path.insert(0, paths.RES_DIR)
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.chdir(paths.DATA_DIR)

    from streamlit.web import bootstrap
    flags = _streamlit_flags(port)
    bootstrap.load_config_options(flag_options=flags)
    _say(f"{'داشبورد' if name == 'dashboard' else 'پنل مدیریت'} روی پورت {port}")
    bootstrap.run(stub, False, [], flags)


# ══════════════════════════════════════════
# برنامهٔ اصلی: اجرا و مراقبت از سرویس‌ها
# ══════════════════════════════════════════
def _child_cmd(service):
    if paths.FROZEN:
        return [sys.executable, "--service", service]
    return [sys.executable, os.path.abspath(__file__), "--service", service]


def _ensure_secret():
    """کلید امنیتی پیش‌فرض برای هر نصب به یک کلید تصادفی تبدیل می‌شود"""
    import config
    if config.current_settings()["SECURITY"]["SESSION_SECRET"] == config.DEFAULTS["SECURITY"]["SESSION_SECRET"]:
        config.save_settings({"SECURITY": {"SESSION_SECRET": secrets.token_hex(32)}})
        _say("کلید امنیتی تازه ساخته شد")


def _open_log(service):
    path = os.path.join(paths.LOG_DIR, f"{service}.log")
    try:
        if os.path.getsize(path) > 5 * 1024 * 1024:
            os.replace(path, path + ".1")
    except OSError:
        pass
    return open(path, "ab", buffering=0)


# تنظیماتی که فقط با شروع دوبارهٔ سرویس‌ها اعمال می‌شوند (اپ موبایل و GPS زنده‌اند)
RESTART_SECTIONS = ("NETWORK", "DATABASES", "SECURITY", "APP", "PATHS")


RESTART_FLAG = os.path.join(paths.DATA_DIR, "run", "restart.flag")
_sig_err = [None]


def _restart_signature():
    import json
    import config
    try:
        cur = config.current_settings()
        return json.dumps({k: cur.get(k) for k in RESTART_SECTIONS}, sort_keys=True, ensure_ascii=False)
    except Exception as e:
        if str(e) != _sig_err[0]:
            _sig_err[0] = str(e)
            _say(f"⚠️ خواندن تنظیمات برای ری‌استارت خودکار ممکن نشد: {e}")
        return None


def request_restart():
    """پنل مدیریت با ساختن این فایل، ری‌استارت همهٔ سرویس‌ها را درخواست می‌کند"""
    os.makedirs(os.path.dirname(RESTART_FLAG), exist_ok=True)
    with open(RESTART_FLAG, "w", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S"))


def _check_ports(wanted):
    """اگر پورتی دست برنامهٔ دیگری باشد (مثلاً نسخهٔ قدیمی یا هم‌زمان start.bat و سرویس نصبی)، واضح بگو"""
    import socket
    from config import NETWORK
    ports = {"api": NETWORK.get("FLASK_PORT", 5000), "pwa": NETWORK.get("PWA_PORT", 8000),
             "dashboard": NETWORK.get("DASHBOARD_PORT", 8501), "admin": NETWORK.get("ADMIN_PORT", 8502)}
    for s in wanted:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
            if sk.connect_ex(("127.0.0.1", int(ports[s]))) == 0:
                _say(f"⚠️ پورت {ports[s]} ({s}) را برنامهٔ دیگری گرفته است — احتمالاً یک نسخهٔ دیگر پیچا ویزیت "
                     "(سرویس نصبی یا پنجرهٔ start.bat قدیمی) در حال اجراست. فقط یکی را اجرا کنید.")


def supervise(only=None):
    _ensure_secret()
    wanted = only or SERVICES
    env = dict(os.environ, PEECHA_PARENT=str(os.getpid()), PEECHA_HOME=paths.DATA_DIR,
               PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" and paths.FROZEN else 0
    procs, started, stopping = {}, {}, threading.Event()

    def start(service):
        log = _open_log(service)
        procs[service] = subprocess.Popen(_child_cmd(service), env=env, cwd=paths.DATA_DIR,
                                          stdout=log, stderr=subprocess.STDOUT,
                                          stdin=subprocess.DEVNULL, creationflags=flags)
        started[service] = time.time()
        log.close()

    def stop(*_):
        if stopping.is_set():
            return
        stopping.set()
        _say("توقف سرویس‌ها ...")
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        deadline = time.time() + 10
        for p in procs.values():
            try:
                p.wait(max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                p.kill()

    for sig in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), lambda *a: (stop(), sys.exit(0)))

    _say(f"پیچا ویزیت شروع شد — پوشهٔ داده: {paths.DATA_DIR}")
    _check_ports(wanted)
    for s in wanted:
        start(s)
    sig = _restart_signature()
    try:
        import config
        d = config.current_settings()["DATABASES"]
        _say(f"دیتابیس‌ها: ردیابی={d['TRACKING_DB']} · فروش={d['SALES_DB']} · تنظیمات: {config.SETTINGS_FILE}")
    except Exception:
        pass
    try:
        os.remove(RESTART_FLAG)
    except OSError:
        pass

    def restart_all(reason="تنظیمات دیتابیس/شبکه/امنیت تغییر کرد"):
        _say(f"🔄 {reason} — شروع دوبارهٔ سرویس‌ها")
        time.sleep(2)                    # تا پنل مدیریت پیام ذخیره را نشان دهد
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        for p in procs.values():
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        for s in wanted:
            start(s)

    try:
        while not stopping.is_set():
            time.sleep(2)
            if os.path.exists(RESTART_FLAG):
                try:
                    os.remove(RESTART_FLAG)
                except OSError:
                    pass
                sig = _restart_signature() or sig
                restart_all("درخواست ری‌استارت از پنل مدیریت")
                continue
            now_sig = _restart_signature()
            if now_sig is not None and sig is None:
                sig = now_sig
            if now_sig is not None and sig is not None and now_sig != sig:
                sig = now_sig
                restart_all()
                continue
            for s in wanted:
                p = procs[s]
                if p.poll() is not None and not stopping.is_set():
                    # اگر زود از کار افتاده (مثلاً دیتابیس در دسترس نیست) کمی بیشتر صبر کن
                    wait = 5 if time.time() - started[s] > 60 else 20
                    _say(f"⚠️ سرویس {s} متوقف شد (کد {p.returncode}) — اجرای دوباره پس از {wait} ثانیه")
                    time.sleep(wait)
                    if not stopping.is_set():
                        start(s)
    finally:
        stop()


# ══════════════════════════════════════════
# ابزارهای نصب
# ══════════════════════════════════════════
def check_db() -> int:
    from db import get_conn, TRACKING_DB, SALES_DB
    ok = True
    for db in (TRACKING_DB, SALES_DB):
        try:
            conn = get_conn(db); conn.cursor().execute("SELECT 1"); conn.close()
            print(f"OK   {db}")
        except Exception as e:
            ok = False
            print(f"FAIL {db}: {e}")
    return 0 if ok else 1


def configure(a) -> int:
    import config
    net, dbs = {}, {}
    if a.server is not None:   net["SERVER_NAME"] = a.server
    if a.server_ip is not None: net["SERVER_IP"] = a.server_ip
    if a.tracking is not None: dbs["TRACKING_DB"] = a.tracking
    if a.sales is not None:    dbs["SALES_DB"] = a.sales
    if a.driver is not None:   dbs["DRIVER"] = a.driver
    if a.user is not None:     dbs["USER"] = a.user
    if a.password is not None: dbs["PASSWORD"] = a.password
    changes = {k: v for k, v in (("NETWORK", net), ("DATABASES", dbs)) if v}
    if changes:
        config.save_settings(changes)
    _ensure_secret()
    print(f"settings: {config.SETTINGS_FILE}")
    return 0


def setup_db() -> int:
    """ساخت دیتابیس پیچا ویزیت (اگر نیست) + جدول‌ها؛ تکرارش بی‌خطر است (نصب‌کننده اجرا می‌کند)."""
    import config, db, create_tables as ct, audit
    name = config.DATABASES.get("TRACKING_DB") or "tracking"
    sales = config.DATABASES.get("SALES_DB") or ""
    windows_auth = not (config.DATABASES.get("USER") or "").strip()
    try:
        conn = db.get_conn(None, autocommit=True); cur = conn.cursor()
        cur.execute("DECLARE @n sysname = ?; IF DB_ID(@n) IS NULL BEGIN "
                    "DECLARE @s nvarchar(400) = N'CREATE DATABASE ' + QUOTENAME(@n); EXEC(@s); END", name)
        print(f"database ok: {name}")
        if windows_auth:
            # سرویس ویندوز با حساب SYSTEM اجرا می‌شود: دسترسی آن به دیتابیس‌ها
            grant = ("IF SUSER_ID(N'NT AUTHORITY\\SYSTEM') IS NULL CREATE LOGIN [NT AUTHORITY\\SYSTEM] FROM WINDOWS; "
                     "DECLARE @d sysname = ?, @r sysname = ?, @s nvarchar(800); "
                     "IF DB_ID(@d) IS NOT NULL BEGIN SET @s = N'USE ' + QUOTENAME(@d) + N'; "
                     "IF USER_ID(N''NT AUTHORITY\\SYSTEM'') IS NULL CREATE USER [NT AUTHORITY\\SYSTEM] FOR LOGIN [NT AUTHORITY\\SYSTEM]; "
                     "ALTER ROLE ' + @r + N' ADD MEMBER [NT AUTHORITY\\SYSTEM];'; EXEC(@s); END")
            for d, role in ((name, "db_owner"), (sales, "db_datareader")):
                if not d:
                    continue
                try:
                    cur.execute(grant, d, role); print(f"service access ok: {d}")
                except Exception as e:
                    print(f"service access FAIL {d}: {e}")
        conn.close()
        orig = ct.get_conn
        ct.get_conn = lambda db=None, autocommit=False: orig(name if db == "tracking" else db, autocommit)
        ct.create_tables()
        ct.alter_existing_tables()
        audit.ensure_schema()
        print("tables ok")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="PeechaVisit", description="پیچا ویزیت — سرور")
    ap.add_argument("--service", choices=SERVICES, help=argparse.SUPPRESS)
    ap.add_argument("--only", nargs="+", choices=SERVICES, help="فقط این سرویس‌ها")
    ap.add_argument("--setup-db", action="store_true", help="ساخت دیتابیس و جدول‌ها")
    ap.add_argument("--serve", action="store_true", help="اجرای همهٔ سرویس‌ها (سرویس ویندوز همین را اجرا می‌کند)")
    ap.add_argument("--check", action="store_true", help="آزمایش اتصال به دیتابیس")
    ap.add_argument("--configure", action="store_true", help="ذخیرهٔ تنظیمات دیتابیس")
    for opt in ("server", "server-ip", "tracking", "sales", "driver", "user", "password"):
        ap.add_argument(f"--{opt}")
    a = ap.parse_args(argv)

    if a.service:
        _watch_parent()
        import warnings
        warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")
        {"api": run_api, "pwa": run_pwa,
         "dashboard": lambda: run_streamlit("dashboard"),
         "admin": lambda: run_streamlit("admin")}[a.service]()
        return 0
    if a.configure:
        return configure(a)
    if a.setup_db:
        return setup_db()
    if a.check:
        return check_db()
    if paths.FROZEN and not (a.serve or a.only):
        # دوبار کلیک روی PeechaVisit.exe در نسخهٔ نصبی: سرورها را دوباره اجرا نکن (کار سرویس ویندوز است)؛
        # آیکون کنار ساعت و صفحهٔ «وضعیت و آدرس‌ها» را باز کن
        tray = os.path.join(os.path.dirname(sys.executable), "PeechaVisitTray.exe")
        if os.path.exists(tray):
            subprocess.Popen([tray, "--page"], close_fds=True)
        return 0
    supervise(a.only)
    return 0


if __name__ == "__main__":
    # فرزندهای multiprocessing در exe (برای احتیاط)
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
