from __future__ import annotations

import base64
import html
import io
from dataclasses import dataclass

import qrcode


@dataclass(frozen=True)
class PrintLayout:
    label_width_mm: float = 45.0
    label_height_mm: float = 50.0
    qr_size_mm: float = 27.0
    columns: int = 4
    gap_x_mm: float = 2.0
    gap_y_mm: float = 2.0
    margin_mm: float = 8.0
    page_size: str = "A4"
    landscape: bool = False
    show_title: bool = True
    show_serial: bool = True


def _qr_data_uri(target_url: str) -> str:
    img = qrcode.make(target_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _label_html(serial: str, target_url: str, layout: PrintLayout, title: str = "DARIO PRODUCT") -> str:
    title_html = f"<h1>{html.escape(title)}</h1>" if layout.show_title else ""
    serial_html = f"<p dir='ltr'>{html.escape(serial)}</p>" if layout.show_serial else ""
    return (
        "<div class='label'>"
        f"<img class='qr' src='{_qr_data_uri(target_url)}' alt='QR {html.escape(serial)}'/>"
        f"{title_html}{serial_html}</div>"
    )


def validate_layout(layout: PrintLayout) -> None:
    if not 20 <= layout.label_width_mm <= 120:
        raise ValueError("عرض لیبل باید بین ۲۰ تا ۱۲۰ میلی‌متر باشد")
    if not 20 <= layout.label_height_mm <= 150:
        raise ValueError("ارتفاع لیبل باید بین ۲۰ تا ۱۵۰ میلی‌متر باشد")
    if not 12 <= layout.qr_size_mm <= min(layout.label_width_mm, layout.label_height_mm) - 4:
        raise ValueError("اندازه QR با ابعاد لیبل سازگار نیست")
    if not 1 <= layout.columns <= 10:
        raise ValueError("تعداد ستون باید بین ۱ تا ۱۰ باشد")
    if not 0 <= layout.gap_x_mm <= 20 or not 0 <= layout.gap_y_mm <= 20:
        raise ValueError("فاصله لیبل‌ها باید بین ۰ تا ۲۰ میلی‌متر باشد")
    if not 0 <= layout.margin_mm <= 30:
        raise ValueError("حاشیه صفحه باید بین ۰ تا ۳۰ میلی‌متر باشد")
    page = layout.page_size.upper()
    dims = {"A4": (210.0, 297.0), "A5": (148.0, 210.0)}
    if page not in dims:
        raise ValueError("اندازه صفحه پشتیبانی نمی‌شود")
    width, height = dims[page]
    if layout.landscape:
        width, height = height, width
    needed = layout.columns * layout.label_width_mm + max(layout.columns - 1, 0) * layout.gap_x_mm
    usable = width - 2 * layout.margin_mm
    if needed > usable + 0.01:
        raise ValueError(f"{layout.columns} ستون با این عرض لیبل در صفحه جا نمی‌شود؛ عرض یا تعداد ستون را کم کنید")


def single_label_page(serial: str, target_url: str, *, label_width_mm: float, label_height_mm: float, qr_size_mm: float, show_title: bool = True, show_serial: bool = True) -> str:
    layout = PrintLayout(
        label_width_mm=label_width_mm,
        label_height_mm=label_height_mm,
        qr_size_mm=qr_size_mm,
        columns=1,
        gap_x_mm=0,
        gap_y_mm=0,
        margin_mm=0,
        page_size="A4",
        show_title=show_title,
        show_serial=show_serial,
    )
    # Single-label printers use a custom physical page size, so only the label/QR limits matter.
    if not 20 <= label_width_mm <= 120 or not 20 <= label_height_mm <= 150:
        raise ValueError("ابعاد لیبل خارج از محدوده مجاز است")
    if not 12 <= qr_size_mm <= min(label_width_mm, label_height_mm) - 4:
        raise ValueError("اندازه QR با ابعاد لیبل سازگار نیست")
    fragment = _label_html(serial, target_url, layout)
    return f"""<!doctype html><html dir='rtl'><head><meta charset='utf-8'><title>Dario QR</title>
<style>
@page{{size:{label_width_mm}mm {label_height_mm}mm;margin:0}}
*{{box-sizing:border-box}}html,body{{margin:0;padding:0;font-family:Arial,Tahoma,sans-serif}}
.label{{width:{label_width_mm}mm;height:{label_height_mm}mm;padding:2mm;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;overflow:hidden}}
.qr{{width:{qr_size_mm}mm;height:{qr_size_mm}mm;object-fit:contain;image-rendering:pixelated}}
h1{{font-size:10pt;margin:1.2mm 0 .5mm}}p{{font-size:7.5pt;margin:.3mm 0;word-break:break-all}}
</style></head><body>{fragment}<script>window.addEventListener('load',()=>window.print())</script></body></html>"""


def batch_label_page(rows: list[tuple[str, str]], layout: PrintLayout) -> str:
    validate_layout(layout)
    fragments = "".join(_label_html(serial, url, layout) for serial, url in rows)
    orientation = " landscape" if layout.landscape else " portrait"
    return f"""<!doctype html><html dir='rtl'><head><meta charset='utf-8'><title>Dario QR Labels</title>
<style>
@page{{size:{layout.page_size.upper()}{orientation};margin:{layout.margin_mm}mm}}
*{{box-sizing:border-box}}html,body{{margin:0;padding:0;font-family:Arial,Tahoma,sans-serif}}
.sheet{{display:grid;grid-template-columns:repeat({layout.columns},{layout.label_width_mm}mm);grid-auto-rows:{layout.label_height_mm}mm;column-gap:{layout.gap_x_mm}mm;row-gap:{layout.gap_y_mm}mm;align-items:start;justify-content:start}}
.label{{width:{layout.label_width_mm}mm;height:{layout.label_height_mm}mm;padding:2mm;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;overflow:hidden;break-inside:avoid;page-break-inside:avoid;border:.15mm dashed #cbd5e1}}
.qr{{width:{layout.qr_size_mm}mm;height:{layout.qr_size_mm}mm;object-fit:contain;image-rendering:pixelated}}
h1{{font-size:9pt;margin:1mm 0 .4mm}}p{{font-size:7pt;margin:.2mm 0;word-break:break-all}}
@media print{{.label{{border-color:transparent}}}}
</style></head><body><div class='sheet'>{fragments}</div><script>window.addEventListener('load',()=>window.print())</script></body></html>"""
