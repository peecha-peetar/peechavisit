# perms.py - پیچا ویزیت | دسترسی کاربران به داشبورد
# ════════════════════════════════════════════════
# مدیر (role=admin) همیشه دسترسی کامل دارد.
# برای بقیه، ستون visitors.dash_perms (JSON) تعیین می‌کند:
#   access   : اجازهٔ ورود به داشبورد
#   visitors : شناسهٔ ویزیتورهایی که می‌بیند ([] = همه)
#   money    : دیدن مبلغ‌ها و قیمت‌ها
#   photos   : دیدن عکس‌ها (سلفی، چک، حواله)
#   export   : خروجی Excel / PDF / چاپ
# ════════════════════════════════════════════════
import json

FULL = {"access": True, "visitors": [], "money": True, "photos": True, "export": True}
NONE = {"access": False, "visitors": [], "money": True, "photos": True, "export": True}

LABELS = {
    "money":  "💰 دیدن مبلغ‌ها و قیمت‌ها",
    "photos": "🖼️ دیدن عکس‌ها (سلفی، چک، حواله)",
    "export": "📥 خروجی Excel / PDF / چاپ",
}


def parse(raw) -> dict:
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    out = dict(NONE)
    for k in ("access", "money", "photos", "export"):
        if isinstance(data.get(k), bool):
            out[k] = data[k]
    vis = data.get("visitors")
    if isinstance(vis, list):
        out["visitors"] = [int(v) for v in vis if isinstance(v, int) or str(v).isdigit()]
    return out


def effective(role: str, raw) -> dict:
    return dict(FULL) if role == "admin" else parse(raw)


def dump(p: dict) -> str:
    return json.dumps({"access": bool(p.get("access")), "visitors": [int(v) for v in p.get("visitors", [])],
                       "money": bool(p.get("money")), "photos": bool(p.get("photos")),
                       "export": bool(p.get("export"))})
