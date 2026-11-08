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
