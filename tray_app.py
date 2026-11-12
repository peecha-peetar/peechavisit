# tray_app.py - پیچا ویزیت | آیکون کنار ساعت ویندوز (System Tray) + صفحهٔ وضعیت و آدرس‌ها
# ════════════════════════════════════════════════
# PeechaVisitTray.exe (بدون پنجرهٔ سیاه) با ورود به ویندوز اجرا می‌شود:
#   آیکون سبز = همهٔ سرویس‌ها روشن · نارنجی = بعضی · قرمز = سرویس خاموش
#   منو: وضعیت و آدرس‌ها، داشبورد، پنل مدیریت، ری‌استارت سرویس، پوشهٔ لاگ‌ها
# صفحهٔ «وضعیت و آدرس‌ها» در مرورگر باز می‌شود (فارسی و راست‌به‌چپ درست نمایش داده می‌شود):
#   http://127.0.0.1:8599
# ════════════════════════════════════════════════
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TRAY_PORT = 8599
DEFAULT_PORTS = {"api": 5000, "pwa": 8000, "dashboard": 8501, "admin": 8502}
APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
DATA_DIR = os.environ.get("PEECHA_HOME") or os.path.join(os.environ.get("PROGRAMDATA") or APP_DIR, "PeechaVisit")

state = {"ports": dict(DEFAULT_PORTS), "up": {}, "info": None, "checked": 0}


# ══════════════════════════════════════════
# وضعیت سرویس‌ها و آدرس‌های این کامپیوتر
# ══════════════════════════════════════════
def _get(url, timeout=1.5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def check():
    ports = dict(state["ports"])
    info = None
    try:
        st, body = _get(f"http://127.0.0.1:{ports['api']}/api/server-info")
        info = json.loads(body.decode("utf-8")) if st == 200 else None
        if info and isinstance(info.get("ports"), dict):
            ports.update({k: int(v) for k, v in info["ports"].items() if k in ports})
    except Exception:
        info = None
    up = {}
    for name, path in (("api", "/"), ("pwa", "/"), ("dashboard", "/_stcore/health"), ("admin", "/_stcore/health")):
        try:
            up[name] = _get(f"http://127.0.0.1:{ports[name]}{path}")[0] == 200
        except Exception:
            up[name] = False
    state.update(ports=ports, up=up, info=info, checked=time.time())
    return up


def local_ips():
    """آی‌پی‌های IPv4 این کامپیوتر — اول آی‌پی اصلی شبکه"""
    ips = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))           # بسته‌ای فرستاده نمی‌شود؛ فقط کارت شبکهٔ اصلی پیدا می‌شود
            ips.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for fam, _, _, _, addr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(addr[0])
    except OSError:
        pass
    out = []
    for ip in ips:
        if ip not in out and not ip.startswith(("127.", "169.254.")):
            out.append(ip)
    return out


def ip_label(ip, first):
    if ip.startswith("100.") and 64 <= int(ip.split(".")[1]) <= 127:
        return "Tailscale (اتصال از بیرون شبکه)"
    return "شبکهٔ داخلی (اصلی)" if first else "شبکهٔ داخلی"


def status_json():
    up = state["up"]
    n = sum(1 for v in up.values() if v)
    ips = local_ips()
    return {
        "overall": "ok" if up and n == len(up) else ("part" if n else "down"),
        "up": up, "ports": state["ports"], "info": state["info"], "host": socket.gethostname(),
        "ips": [{"ip": ip, "label": ip_label(ip, i == 0)} for i, ip in enumerate(ips)],
        "checked": time.strftime("%H:%M:%S", time.localtime(state["checked"] or time.time())),
        "data_dir": DATA_DIR,
    }


# ══════════════════════════════════════════
# کارها
# ══════════════════════════════════════════
def open_url(port_key, ip="localhost"):
    webbrowser.open(f"http://{ip}:{state['ports'][port_key]}")


def restart_service():
    """ری‌استارت سرویس ویندوز (پنجرهٔ تأیید ویندوز/UAC باز می‌شود)"""
    exe = os.path.join(APP_DIR, "PeechaVisitService.exe")
    if os.name == "nt" and os.path.exists(exe):
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, "restart", APP_DIR, 0)


def open_logs():
    path = os.path.join(DATA_DIR, "logs")
    if os.name == "nt":
        os.startfile(path if os.path.isdir(path) else DATA_DIR)  # noqa


# ══════════════════════════════════════════
# صفحهٔ «وضعیت و آدرس‌ها»
# ══════════════════════════════════════════
def _font_css():
    try:
        from ui_font import font_css
        return font_css().replace(".stApp *", "body *")
    except Exception:
        return ""


PAGE = """<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>پیچا ویزیت — وضعیت و آدرس‌ها</title>%FONT%
<style>
body{font-family:Vazirmatn,Tahoma,sans-serif;background:#f3f5fb;color:#17202e;margin:0}
header{background:#020025;color:#fff;padding:16px 22px;display:flex;align-items:center;gap:14px}
header h1{font-size:19px;margin:0} header small{opacity:.75}
.dot{width:14px;height:14px;border-radius:50%;display:inline-block;flex:none}
.ok{background:#2f9e44}.part{background:#f08c00}.down{background:#e03131}
main{max-width:980px;margin:0 auto;padding:18px}
.card{background:#fff;border:1px solid #e3e7ef;border-radius:14px;padding:14px 16px;margin-bottom:14px}
.card h2{font-size:16px;margin:0 0 10px}
.big{display:flex;align-items:center;gap:12px;font-size:18px;font-weight:800}
.svc{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
.svc div{border:1px solid #eef0f4;border-radius:10px;padding:10px;display:flex;gap:8px;align-items:center}
table{width:100%;border-collapse:collapse;font-size:14px} td,th{padding:8px;border-bottom:1px solid #eef0f4;text-align:right}
th{color:#6b7686;font-weight:600}
code{direction:ltr;display:inline-block;background:#f1f3f7;border-radius:6px;padding:2px 8px;font-size:14px}
button{font:700 13px Vazirmatn,Tahoma,sans-serif;border:0;border-radius:8px;padding:6px 12px;cursor:pointer;background:#e7ecff;color:#3b5bdb}
button.main{background:#3b5bdb;color:#fff}
.tag{font-size:11px;border-radius:10px;padding:1px 8px;background:#eef1f6;color:#495057;margin-right:6px}
.hint{color:#6b7686;font-size:13px;line-height:1.9}
</style></head><body>
<header><span class="dot" id="hd"></span><div><h1>پیچا ویزیت — وضعیت و آدرس‌ها</h1><small id="sub"></small></div></header>
<main>
<div class="card"><div class="big"><span class="dot" id="bd"></span><span id="bt">...</span></div>
<div class="hint" id="meta" style="margin-top:6px"></div>
<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
<button class="main" onclick="act('dashboard')">باز کردن داشبورد</button>
<button class="main" onclick="act('admin')">باز کردن پنل مدیریت</button>
<button onclick="act('restart')">ری‌استارت سرویس</button><button onclick="act('logs')">پوشهٔ لاگ‌ها</button></div></div>
<div class="card"><h2>سرویس‌ها</h2><div class="svc" id="svc"></div></div>
<div class="card"><h2>آدرس‌ها برای کامپیوترها و گوشی‌ها</h2>
<table><thead><tr><th>آی‌پی این کامپیوتر</th><th>📱 «آدرس سرور» در اپ موبایل</th><th>📊 داشبورد</th><th>🛠️ پنل مدیریت</th></tr></thead>
<tbody id="ips"></tbody></table>
<div class="hint" style="margin-top:8px">در اپ اندروید، در صفحهٔ ورود ← «⚙️ آدرس سرور» فقط آی‌پی را بنویسید (پورت <span id="ap"></span> خودکار اضافه می‌شود).
گوشی باید در همان شبکهٔ Wi-Fi باشد (یا Tailscale روشن باشد). داشبورد و پنل مدیریت را هر کامپیوتر شبکه با آدرس جدول باز می‌کند.</div></div>
</main>
<script>
const NAMES={api:'API موبایل',pwa:'وب‌اپ موبایل',dashboard:'داشبورد',admin:'پنل مدیریت'};
const fa=s=>String(s).replace(/\\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
function copy(t,b){navigator.clipboard&&navigator.clipboard.writeText(t);b.textContent='کپی شد ✓';setTimeout(()=>b.textContent='کپی',1500)}
function act(a){fetch('/action/'+a,{method:'POST'})}
async function load(){
 let d; try{d=await (await fetch('/status.json')).json()}catch(e){return}
 const cls=d.overall, txt={ok:'همهٔ سرویس‌ها در حال اجرا هستند',part:'بعضی سرویس‌ها اجرا نمی‌شوند',down:'سرویس پیچا ویزیت اجرا نمی‌شود'}[cls];
 for(const id of ['hd','bd']) document.getElementById(id).className='dot '+cls;
 document.getElementById('bt').textContent=txt;
 document.getElementById('sub').textContent='کامپیوتر: '+d.host+' · آخرین بررسی '+fa(d.checked);
 const i=d.info; document.getElementById('meta').innerHTML=i?('نسخهٔ '+fa(i.version)+' · دیتابیس فروش <b>'+i.sales_db+'</b> · ردیابی <b>'+i.tracking_db+'</b> · اجرا از '+fa(i.started)):
   (cls==='down'?'سرویس ویندوز «PeechaVisit Server» را از Services روشن کنید یا «ری‌استارت سرویس» را بزنید.':'');
 document.getElementById('svc').innerHTML=Object.keys(NAMES).map(k=>'<div><span class="dot '+(d.up[k]?'ok':'down')+'"></span><b>'+NAMES[k]+'</b><span class="tag">پورت '+fa(d.ports[k])+'</span><span class="tag">'+(d.up[k]?'روشن':'خاموش')+'</span></div>').join('');
 document.getElementById('ap').textContent=fa(d.ports.api);
 const row=(ip,lab)=>{const db='http://'+ip+':'+d.ports.dashboard, ad='http://'+ip+':'+d.ports.admin;
  return '<tr><td><code>'+ip+'</code><div class="hint">'+lab+'</div></td>'+
  '<td><code>'+ip+'</code> <button onclick="copy(\\''+ip+'\\',this)">کپی</button></td>'+
  '<td><a href="'+db+'" target="_blank"><code>'+db+'</code></a></td><td><a href="'+ad+'" target="_blank"><code>'+ad+'</code></a></td></tr>'};
 document.getElementById('ips').innerHTML=d.ips.map(x=>row(x.ip,x.label)).join('')||'<tr><td colspan="4">آی‌پی شبکه پیدا نشد — کابل یا Wi-Fi را بررسی کنید.</td></tr>';
}
load(); setInterval(load,5000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/status.json"):
            return self._send(200, json.dumps(status_json(), ensure_ascii=False), "application/json; charset=utf-8")
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE.replace("%FONT%", _font_css()), "text/html; charset=utf-8")
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        # فقط از همین کامپیوتر (سرور فقط روی 127.0.0.1 گوش می‌دهد)
        a = self.path.rsplit("/", 1)[-1]
        {"dashboard": lambda: open_url("dashboard"), "admin": lambda: open_url("admin"),
         "restart": restart_service, "logs": open_logs}.get(a, lambda: None)()
        self._send(200, "{}", "application/json")


def open_status():
    webbrowser.open(f"http://127.0.0.1:{TRAY_PORT}/")


# ══════════════════════════════════════════
# آیکون کنار ساعت
# ══════════════════════════════════════════
def make_icon(color):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(2, 0, 37, 255))
    d.ellipse((38, 38, 62, 62), fill=color, outline=(255, 255, 255, 255), width=3)
    d.text((14, 8), "P", fill=(255, 255, 255, 255), font=_big_font())
    return im


def _big_font():
    from PIL import ImageFont
    for f in ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, 40)
        except OSError:
            continue
    return ImageFont.load_default()


COLORS = {"ok": (47, 158, 68, 255), "part": (240, 140, 0, 255), "down": (224, 49, 49, 255)}
TIPS = {"ok": "پیچا ویزیت — همهٔ سرویس‌ها روشن", "part": "پیچا ویزیت — بعضی سرویس‌ها خاموش",
        "down": "پیچا ویزیت — سرویس خاموش است"}


def run_tray():
    import pystray
    icon = pystray.Icon("PeechaVisit", make_icon(COLORS["down"]), "پیچا ویزیت", menu=pystray.Menu(
        pystray.MenuItem("وضعیت و آدرس‌ها", lambda: open_status(), default=True),
        pystray.MenuItem("داشبورد", lambda: open_url("dashboard")),
        pystray.MenuItem("پنل مدیریت", lambda: open_url("admin")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("ری‌استارت سرویس", lambda: restart_service()),
        pystray.MenuItem("پوشهٔ لاگ‌ها", lambda: open_logs()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("بستن این آیکون", lambda i: i.stop()),
    ))

    def watch():
        last = None
        while True:
            check()
            s = status_json()["overall"]
            if s != last:
                icon.icon = make_icon(COLORS[s])
                icon.title = TIPS[s]
                last = s
            time.sleep(5)

    threading.Thread(target=watch, daemon=True).start()
    icon.run()


def main():
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", TRAY_PORT), Handler)
    except OSError:
        open_status()            # یک نسخه از قبل اجراست → فقط صفحهٔ وضعیت را باز کن
        return
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    check()
    if "--page" in sys.argv:
        open_status()
    try:
        run_tray()
    except Exception as e:                      # بدون محیط گرافیکی (مثلاً آزمایش): فقط صفحهٔ وضعیت
        print(f"tray unavailable: {e}")
        while True:
            check()
            time.sleep(5)


if __name__ == "__main__":
    main()
