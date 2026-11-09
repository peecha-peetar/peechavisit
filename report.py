# report.py - پیچا ویزیت | خروجی گزارش داشبورد (Excel / PDF / چاپ)
# ════════════════════════════════════════════════
# ورودی هر سه خروجی یکی است:
#   meta     : [(عنوان, مقدار), ...]          — بازه، فیلترها، جمع‌ها
#   sections : [(عنوان, [ستون‌ها], [ردیف‌ها])]  — ستون اول = راست‌ترین ستون
# ردیف‌ها dict هستند؛ عددها عدد می‌مانند تا در اکسل قابل محاسبه باشند.
# ════════════════════════════════════════════════
import io
import os
from datetime import datetime

import jdatetime
import pandas as pd

from paths import RES_DIR
FONT_DIR = os.path.join(RES_DIR, "fonts")
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _is_num_col(col: str) -> bool:
    return "ریال" in col or col in ("تعداد",)


def fmt(v, col="") -> str:
    """نمایش فارسی: ارقام فارسی و جداکنندهٔ هزارگان"""
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return "—"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        s = f"{v:g}" if col == "تعداد" else f"{v:,.0f}"
        return s.replace(",", "٬").translate(_FA)
    return str(v).translate(_FA)


def stamp() -> str:
    return jdatetime.datetime.now().strftime("%Y/%m/%d %H:%M").translate(_FA)


# ══════════════════════════════════════════════
# Excel
# ══════════════════════════════════════════════
def to_excel(meta, sections) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        wb = w.book
        head = wb.add_format({"bold": True, "bg_color": "#020025", "font_color": "white", "border": 1,
                              "align": "right", "valign": "vcenter", "font_name": "Tahoma"})
        cell = wb.add_format({"border": 1, "align": "right", "font_name": "Tahoma"})
        num = wb.add_format({"border": 1, "align": "right", "font_name": "Tahoma", "num_format": "#,##0"})
        qty = wb.add_format({"border": 1, "align": "right", "font_name": "Tahoma", "num_format": "#,##0.##"})
        title = wb.add_format({"bold": True, "font_size": 14, "font_name": "Tahoma"})

        ws = wb.add_worksheet("خلاصه")
        ws.right_to_left()
        ws.write(0, 0, "گزارش پیچا ویزیت", title)
        for i, (k, v) in enumerate(meta + [("تاریخ تهیه", stamp())], 2):
            ws.write(i, 0, k, head)
            ws.write(i, 1, str(v), cell)
        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 60)

        for name, cols, rows in sections:
            ws = wb.add_worksheet(name[:31])
            ws.right_to_left()
            for c, col in enumerate(cols):
                ws.write(0, c, col, head)
                width = max([len(col)] + [len(str(r.get(col, ""))) for r in rows[:300]]) + 4
                ws.set_column(c, c, min(max(width, 10), 50))
            for r_i, r in enumerate(rows, 1):
                for c, col in enumerate(cols):
                    v = r.get(col, "")
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and not pd.isna(v):
                        ws.write_number(r_i, c, float(v), qty if col == "تعداد" else num)
                    else:
                        ws.write(r_i, c, "" if v is None else str(v), cell)
            if not rows:
                ws.write(1, 0, "موردی نیست", cell)
            ws.freeze_panes(1, 0)
    return out.getvalue()


# ══════════════════════════════════════════════
# PDF  (fpdf2 + HarfBuzz برای اتصال و راست‌به‌چپ حروف فارسی)
# ══════════════════════════════════════════════
def to_pdf(meta, sections) -> bytes:
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=12)
    pdf.add_font("vz", "", os.path.join(FONT_DIR, "Vazirmatn-Regular.ttf"))
    pdf.add_font("vz", "B", os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf"))
    pdf.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab", language="fas")
    pdf.set_margins(10, 10, 10)
    pdf.add_page()

    pdf.set_font("vz", "B", 16)
    pdf.cell(0, 9, "گزارش پیچا ویزیت", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("vz", "", 10)
    for k, v in meta:
        pdf.cell(0, 6, f"{k}: {fmt(v)}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(110, 118, 134)
    pdf.cell(0, 6, f"تاریخ تهیه: {stamp()}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    for name, cols, rows in sections:
        pdf.ln(4)
        pdf.set_font("vz", "B", 12)
        pdf.cell(0, 8, f"{name} ({fmt(len(rows))})", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("vz", "", 9)
        if not rows:
            pdf.cell(0, 6, "موردی نیست", align="R", new_x="LMARGIN", new_y="NEXT")
            continue
        texts = [[fmt(r.get(c, ""), c) for c in cols] for r in rows]
        weights = [min(max([len(c)] + [len(t[i]) for t in texts[:200]]), 45) + 3 for i, c in enumerate(cols)]
        # جدول fpdf ستون اول را چپ می‌گذارد → ترتیب ستون‌ها برعکس
        head = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=(2, 0, 37))
        with pdf.table(col_widths=tuple(reversed(weights)), text_align="RIGHT", line_height=6,
                       headings_style=head, cell_fill_color=(246, 247, 250), cell_fill_mode="ROWS") as table:
            hr = table.row()
            for c in reversed(cols):
                hr.cell(c)
            for t in texts:
                row = table.row()
                for v in reversed(t):
                    row.cell(v)
    return bytes(pdf.output())


# ══════════════════════════════════════════════
# صفحهٔ چاپ (HTML با دکمهٔ چاپ؛ «ذخیره به PDF» هم از پنجرهٔ چاپ مرورگر)
# ══════════════════════════════════════════════
def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def to_html(meta, sections, font_css: str = "") -> str:
    parts = [f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>گزارش پیچا ویزیت</title>{font_css}
<style>
body {{ font-family: Vazirmatn, Tahoma, sans-serif; color:#17202e; margin:16px; font-size:13px; }}
h1 {{ font-size:20px; margin:0 0 6px; }}
h2 {{ font-size:15px; margin:18px 0 6px; }}
.meta div {{ margin:2px 0; }} .meta b {{ color:#495057; font-weight:600; }}
table {{ width:100%; border-collapse:collapse; margin-bottom:6px; }}
th, td {{ border:1px solid #cfd4dc; padding:4px 6px; text-align:right; vertical-align:top; }}
th {{ background:#020025; color:#fff; font-weight:700; }}
tr:nth-child(even) td {{ background:#f6f7fa; }}
td.n {{ white-space:nowrap; }}
.bar {{ position:sticky; top:0; background:#fff; padding:8px 0; border-bottom:1px solid #e3e7ef; margin-bottom:10px; }}
.bar button {{ font:700 14px Vazirmatn, Tahoma, sans-serif; background:#3b5bdb; color:#fff; border:0;
              border-radius:8px; padding:8px 18px; cursor:pointer; }}
.bar span {{ color:#6b7686; font-size:12px; margin-right:10px; }}
@media print {{ .bar {{ display:none; }} body {{ margin:0; }} th {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }} }}
@page {{ size: A4 landscape; margin: 10mm; }}
</style></head><body>
<div class="bar"><button onclick="window.print()">🖨️ چاپ / ذخیره PDF</button>
<span>در پنجرهٔ چاپ، مقصد «Save as PDF» را برای ذخیرهٔ PDF انتخاب کنید.</span></div>
<h1>گزارش پیچا ویزیت</h1><div class="meta">"""]
    for k, v in meta + [("تاریخ تهیه", stamp())]:
        parts.append(f"<div><b>{_esc(k)}:</b> {_esc(fmt(v))}</div>")
    parts.append("</div>")
    for name, cols, rows in sections:
        parts.append(f"<h2>{_esc(name)} ({fmt(len(rows))})</h2>")
        if not rows:
            parts.append("<div>موردی نیست</div>")
            continue
        parts.append("<table><thead><tr>" + "".join(f"<th>{_esc(c)}</th>" for c in cols) + "</tr></thead><tbody>")
        for r in rows:
            parts.append("<tr>" + "".join(
                f"<td{' class=n' if _is_num_col(c) else ''}>{_esc(fmt(r.get(c, ''), c))}</td>" for c in cols) + "</tr>")
        parts.append("</tbody></table>")
    parts.append("</body></html>")
    return "".join(parts)


# ════════════════════════════════════════════════
# برگهٔ چاپی سفارش (هر سفارش یک صفحهٔ A4)
# ════════════════════════════════════════════════
def _fa(v) -> str:
    return str(v if v is not None else "").translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _num(v) -> str:
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return _esc(v)
    return _fa(f"{v:,.0f}" if v == int(v) else f"{v:,.2f}").replace(",", "٬")


def orders_html(orders, show_money: bool, font_css: str = "", company: str = "پیچا ویزیت") -> str:
    """orders: [{id, date, weekday, time, visitor, customer, customer_code, lines:[{code,name,qty,price}],
    total, description}] — خروجی: صفحهٔ HTML آمادهٔ چاپ با سربرگ"""
    css = f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>برگهٔ سفارش</title>{font_css}
<style>
body {{ font-family: Vazirmatn, Tahoma, sans-serif; color:#17202e; margin:14px; font-size:13px; background:#eef1f6; }}
.page {{ background:#fff; max-width:190mm; margin:0 auto 14px; padding:12mm 12mm 10mm; border-radius:8px;
         box-shadow:0 2px 10px rgba(16,24,40,.08); }}
.head {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom:3px solid #020025;
         padding-bottom:8px; margin-bottom:10px; }}
.head h1 {{ font-size:20px; margin:0; }} .head .co {{ font-size:13px; color:#495057; margin-top:2px; }}
.head .no {{ text-align:left; }} .head .no b {{ display:block; font-size:18px; }}
.head .no small {{ color:#6b7686; }}
.info {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:6px 14px; margin-bottom:12px; }}
.info div {{ border:1px solid #e3e7ef; border-radius:6px; padding:5px 8px; }}
.info small {{ display:block; color:#6b7686; font-size:11px; }} .info b {{ font-size:13px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ border:1px solid #cfd4dc; padding:5px 6px; text-align:right; vertical-align:top; }}
th {{ background:#020025; color:#fff; font-weight:700; }}
tbody tr:nth-child(even) td {{ background:#f6f7fa; }}
td.n {{ white-space:nowrap; text-align:left; direction:ltr; }} td.c {{ text-align:center; width:28px; }}
tfoot td {{ font-weight:800; background:#eef1f6; }}
.note {{ border:1px dashed #cfd4dc; border-radius:6px; padding:6px 8px; margin-top:10px; }}
.sign {{ display:flex; justify-content:space-between; margin-top:28px; color:#495057; }}
.sign div {{ width:40%; border-top:1px solid #adb5bd; padding-top:4px; text-align:center; }}
.foot {{ margin-top:12px; color:#adb5bd; font-size:10px; text-align:center; }}
.bar {{ position:sticky; top:0; background:#eef1f6; padding:6px 0 10px; z-index:2; }}
.bar button {{ font:700 14px Vazirmatn, Tahoma, sans-serif; background:#3b5bdb; color:#fff; border:0;
              border-radius:8px; padding:8px 18px; cursor:pointer; }}
.bar span {{ color:#6b7686; font-size:12px; margin-right:10px; }}
@media print {{ body {{ background:#fff; margin:0; }} .bar {{ display:none; }}
  .page {{ box-shadow:none; border-radius:0; margin:0; padding:0; max-width:none; page-break-after:always; }}
  .page:last-child {{ page-break-after:auto; }}
  th, tfoot td, tbody tr:nth-child(even) td {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  thead {{ display:table-header-group; }} tr {{ page-break-inside:avoid; }} }}
@page {{ size:A4 portrait; margin:10mm; }}
</style></head><body>
<div class="bar"><button onclick="window.print()">🖨️ چاپ / ذخیره PDF</button>
<span>{_fa(len(orders))} سفارش · هر سفارش در یک صفحه</span></div>"""
    parts = [css]
    for o in orders:
        lines = o.get("lines") or []
        head = "<th class='c'>#</th><th>کد کالا</th><th>شرح کالا</th><th>تعداد</th>" + \
               ("<th>فی (ریال)</th><th>مبلغ (ریال)</th>" if show_money else "")
        rows = "".join(
            f"<tr><td class='c'>{_fa(i + 1)}</td><td class='n'>{_fa(_esc(l['code']))}</td><td>{_esc(l['name'])}</td>"
            f"<td class='n'>{_num(l['qty'])}</td>"
            + (f"<td class='n'>{_num(l['price'])}</td><td class='n'>{_num(float(l['qty'] or 0) * float(l['price'] or 0))}</td>"
               if show_money else "") + "</tr>"
            for i, l in enumerate(lines)) or f"<tr><td colspan='{6 if show_money else 4}'>اقلامی ثبت نشده است.</td></tr>"
        qty = sum(float(l["qty"] or 0) for l in lines)
        foot = (f"<tr><td colspan='3'>جمع {_fa(len(lines))} قلم</td><td class='n'>{_num(qty)}</td>"
                + (f"<td></td><td class='n'>{_num(o.get('total'))}</td>" if show_money else "") + "</tr>")
        note = f"<div class='note'><b>توضیحات:</b> {_esc(o['description'])}</div>" if o.get("description") else ""
        parts.append(f"""<div class="page">
<div class="head"><div><h1>برگهٔ سفارش فروش</h1><div class="co">{_esc(company)}</div></div>
<div class="no"><small>شمارهٔ سفارش</small><b>{_fa(o['id'])}</b><small>{_esc(o.get('weekday', ''))} {_fa(o['date'])} · ساعت {_fa(o['time'])}</small></div></div>
<div class="info">
<div><small>مشتری</small><b>{_esc(o['customer'])}</b></div>
<div><small>کد مشتری</small><b>{_fa(_esc(o['customer_code']))}</b></div>
<div><small>ویزیتور</small><b>{_esc(o['visitor'])}</b></div>
</div>
{f"<div class='note' style='margin:-4px 0 10px'><b>اطلاعات مشتری جدید:</b> {_esc(o['contact_info'])}</div>" if o.get('contact_info') else ""}
<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody><tfoot>{foot}</tfoot></table>
{note}
<div class="sign"><div>امضای ویزیتور</div><div>امضا و مهر مشتری</div></div>
<div class="foot">چاپ‌شده از پیچا ویزیت · {_esc(stamp())}</div>
</div>""")
    parts.append("</body></html>")
    return "".join(parts)

