# run_client.py - سرور PWA پیچا ویزیت
import http.server, socketserver, os

try:
    from config import NETWORK
    PORT = NETWORK["PWA_PORT"]
    HOST = "0.0.0.0"
    IP   = NETWORK["SERVER_IP"]
except ImportError:
    PORT = 8000
    HOST = "0.0.0.0"
    IP   = "10.165.254.180"

DIRECTORY = "pwa_client"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    def log_message(self, fmt, *args):
        pass  # لاگ خاموش

print(f"╔══════════════════════════════════════════╗")
print(f"║   پیچا ویزیت | سرور PWA موبایل          ║")
print(f"╚══════════════════════════════════════════╝")
print(f"  📱 آدرس: http://{IP}:{PORT}")
print(f"  📁 پوشه: {DIRECTORY}")
print(f"  ⏹  Ctrl+C برای توقف")
print()

with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
    httpd.serve_forever()
