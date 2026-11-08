# mobile_rules.py - پیچا ویزیت | تنظیمات اپ موبایل (سراسری + اختصاصی هر کاربر)
# ════════════════════════════════════════════════
# تنظیم سراسری: config.py / settings.json  (بخش MOBILE)
# تنظیم اختصاصی: ستون visitors.app_settings (JSON فقط با کلیدهای تغییرکرده)
# ════════════════════════════════════════════════
import json
import config

LABELS = {
    "REQUIRE_SELFIE": "📸 سلفی برای ثبت ویزیت اجباری باشد",
    "SHOW_PRICE":     "💰 قیمت کالا نمایش داده شود",
    "SHOW_STOCK":     "📦 موجودی کالا نمایش داده شود",
    "ONLY_IN_STOCK":  "✅ فقط کالاهای دارای موجودی در لیست بیایند",
    "ALLOW_OVERSELL": "⚠️ سفارش بیشتر از موجودی (یا بدون موجودی) مجاز باشد",
}


def global_rules() -> dict:
    """تنظیم سراسری (هر بار تازه از settings.json)"""
    return dict(config.current_settings().get("MOBILE") or {})


def user_overrides(raw) -> dict:
    """JSON ذخیره‌شده برای کاربر → فقط کلیدهای شناخته‌شده با مقدار بله/خیر"""
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k in LABELS and isinstance(v, bool)} if isinstance(data, dict) else {}


def effective_rules(raw) -> dict:
    return {**global_rules(), **user_overrides(raw)}


def dump_overrides(overrides: dict) -> str | None:
    clean = {k: bool(v) for k, v in overrides.items() if k in LABELS}
    return json.dumps(clean) if clean else None
