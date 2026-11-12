# make_icons.py - ساخت آیکون‌های ویندوز پیچا ویزیت از لوگو (packaging/peecha_logo_src.png)
# اجرا از ریشهٔ پروژه:  python packaging/make_icons.py
# خروجی: peecha.ico (برنامه، شورت‌کات‌ها، نصب‌کننده)، peecha_logo.png (آیکون کنار ساعت)
#        و تصویرهای صفحه‌های نصب (wizard_*.bmp)
import os
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
NAVY = (0, 44, 100)


def mask(size: int, bold: bool = False) -> Image.Image:
    """شکل گربهٔ لوگو (سفید روی شفاف) در اندازهٔ مربع size"""
    src = Image.open(os.path.join(HERE, "peecha_logo_src.png")).convert("RGBA")
    a = src.getchannel("A").crop(src.getchannel("A").getbbox())
    side = max(a.size)
    sq = Image.new("L", (side, side), 0)
    sq.paste(a, ((side - a.width) // 2, (side - a.height) // 2))
    if bold:                                        # اندازهٔ خیلی کوچک: خط ضخیم‌تر تا دیده شود
        sq = sq.filter(ImageFilter.MaxFilter(9))
    return sq.resize((size, size), Image.LANCZOS)


def tile(size: int, color=NAVY) -> Image.Image:
    """کاشی گرد رنگی با گربهٔ سفید — برای آیکون برنامه و کنار ساعت"""
    s4 = size * 4
    im = Image.new("RGBA", (s4, s4), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, s4 - 1, s4 - 1), radius=int(s4 * 0.22), fill=color + (255,))
    inner = int(s4 * (0.70 if size > 32 else 0.78))
    m = mask(inner, bold=size <= 32)
    white = Image.new("RGBA", (inner, inner), (255, 255, 255, 255))
    im.paste(white, ((s4 - inner) // 2, (s4 - inner) // 2 + int(s4 * 0.01)), m)
    return im.resize((size, size), Image.LANCZOS)


def on_white(w: int, h: int, logo: int, bg=(255, 255, 255), fg=NAVY) -> Image.Image:
    im = Image.new("RGB", (w, h), bg)
    m = mask(logo)
    im.paste(Image.new("RGB", (logo, logo), fg), ((w - logo) // 2, (h - logo) // 2), m)
    return im


def main():
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    big = tile(256)
    big.save(os.path.join(HERE, "peecha.ico"), sizes=[(s, s) for s in sizes],
             append_images=[tile(s) for s in sizes[:-1]])
    logo = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
    logo.putalpha(mask(256))                       # گربهٔ سفید روی زمینهٔ شفاف
    logo.save(os.path.join(HERE, "peecha_logo.png"))
    # صفحه‌های نصب: تصویر کوچک بالای صفحه و تصویر بلند صفحهٔ خوش‌آمد/پایان
    for s in (58, 87, 116):
        on_white(s, s, int(s * 0.86)).save(os.path.join(HERE, f"wizard_small_{s}.bmp"))
    for w, h in ((164, 314), (246, 471), (328, 628)):
        on_white(w, h, int(w * 0.62), bg=NAVY, fg=(255, 255, 255)).save(os.path.join(HERE, f"wizard_large_{w}.bmp"))
    print("ok")


if __name__ == "__main__":
    main()
