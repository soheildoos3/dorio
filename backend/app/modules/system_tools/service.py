from __future__ import annotations

import gzip
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import inspect, literal, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
# Import every ORM model so Base.metadata is complete even when this module is used
# outside the normal FastAPI import path (CLI/tests/backup worker).
import app.modules.models  # noqa: F401
from app.db.base import Base
from app.modules.catalog.model import AttributeValue, Product, ProductVariant, VariantAttributeValue
from app.modules.channels.model import SalesChannel
from app.modules.inventory.model import ProductItem, Stock, StockMovement
from app.modules.warehouse.model import Location, Warehouse


REPORT_TYPES = {"inventory", "items", "movements", "sales"}


@dataclass(slots=True)
class ReportData:
    title: str
    columns: list[str]
    rows: list[list[Any]]


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return {"__type__": "bytes", "hex": value.hex()}
    if isinstance(value, (list, tuple)):
        return [_json_value(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    return str(value)


def _display(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") if value.tzinfo else value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    return str(value)


async def _variant_labels(session: AsyncSession) -> dict[int, str]:
    rows = (await session.execute(
        select(VariantAttributeValue.variant_id, AttributeValue.value)
        .join(AttributeValue, AttributeValue.id == VariantAttributeValue.attribute_value_id)
        .order_by(VariantAttributeValue.variant_id, AttributeValue.attribute_id, AttributeValue.sort_order, AttributeValue.id)
    )).all()
    grouped: dict[int, list[str]] = {}
    for variant_id, value in rows:
        grouped.setdefault(int(variant_id), []).append(str(value))
    return {variant_id: " / ".join(values) for variant_id, values in grouped.items()}


async def _table_column_names(session: AsyncSession, table_name: str) -> set[str]:
    """Return live database columns for compatibility with partially migrated installs."""
    connection = await session.connection()
    return set(
        await connection.run_sync(
            lambda sync_conn: {col["name"] for col in inspect(sync_conn).get_columns(table_name)}
        )
    )


async def build_report(session: AsyncSession, report_type: str) -> ReportData:
    if report_type not in REPORT_TYPES:
        raise ValueError("نوع گزارش معتبر نیست")

    labels = await _variant_labels(session)

    if report_type == "inventory":
        rows = (await session.execute(
            select(
                Product.name,
                ProductVariant.id,
                ProductVariant.sku,
                Warehouse.name,
                Location.path,
                Stock.quantity,
                Stock.reserved,
                Stock.updated_at,
            )
            .join(ProductVariant, ProductVariant.id == Stock.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .join(Location, Location.id == Stock.location_id)
            .join(Warehouse, Warehouse.id == Location.warehouse_id)
            .order_by(Product.name, ProductVariant.id, Warehouse.name, Location.path)
        )).all()
        data = [[
            product_name,
            labels.get(int(variant_id)) or sku or "تنوع پایه",
            sku or "—",
            warehouse_name,
            location_path,
            int(quantity),
            int(reserved),
            int(quantity) + int(reserved),
            updated_at,
        ] for product_name, variant_id, sku, warehouse_name, location_path, quantity, reserved, updated_at in rows]
        return ReportData(
            title="گزارش موجودی",
            columns=["محصول", "تنوع", "SKU", "انبار", "مکان", "قابل مصرف", "رزرو", "کل فیزیکی", "به‌روزرسانی"],
            rows=data,
        )

    if report_type == "items":
        rows = (await session.execute(
            select(
                ProductItem.warranty_serial,
                ProductItem.serial_number,
                Product.name,
                ProductVariant.id,
                ProductVariant.sku,
                ProductItem.qc_status,
                ProductItem.status,
                Warehouse.name,
                Location.path,
                ProductItem.created_at,
            )
            .join(ProductVariant, ProductVariant.id == ProductItem.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .outerjoin(Location, Location.id == ProductItem.location_id)
            .outerjoin(Warehouse, Warehouse.id == ProductItem.warehouse_id)
            .order_by(ProductItem.id.desc())
        )).all()
        data = [[
            warranty_serial or "—",
            serial_number or "—",
            product_name,
            labels.get(int(variant_id)) or sku or "تنوع پایه",
            _display(qc_status),
            _display(status),
            warehouse_name or "—",
            location_path or "—",
            created_at,
        ] for warranty_serial, serial_number, product_name, variant_id, sku, qc_status, status, warehouse_name, location_path, created_at in rows]
        return ReportData(
            title="گزارش واحدهای فیزیکی",
            columns=["شماره گارانتی", "سریال داخلی", "محصول", "تنوع", "QC", "وضعیت", "انبار", "مکان", "تاریخ ایجاد"],
            rows=data,
        )

    if report_type == "movements":
        movement_columns = await _table_column_names(session, "stock_movements")
        line_total_expr = (
            StockMovement.line_total
            if "line_total" in movement_columns
            else literal(None).label("line_total")
        )
        rows = (await session.execute(
            select(
                StockMovement.created_at,
                Product.name,
                ProductVariant.id,
                ProductVariant.sku,
                Location.path,
                StockMovement.type,
                StockMovement.quantity,
                StockMovement.qty_before,
                StockMovement.qty_after,
                SalesChannel.name,
                StockMovement.external_reference,
                line_total_expr,
            )
            .join(ProductVariant, ProductVariant.id == StockMovement.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .outerjoin(Location, Location.id == StockMovement.location_id)
            .outerjoin(SalesChannel, SalesChannel.id == StockMovement.channel_id)
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        )).all()
        data = [[
            created_at,
            product_name,
            labels.get(int(variant_id)) or sku or "تنوع پایه",
            location_path or "—",
            _display(movement_type),
            int(quantity),
            int(qty_before),
            int(qty_after),
            channel_name or "—",
            external_reference or "—",
            line_total,
        ] for created_at, product_name, variant_id, sku, location_path, movement_type, quantity, qty_before, qty_after, channel_name, external_reference, line_total in rows]
        return ReportData(
            title="گزارش کاردکس موجودی",
            columns=["زمان", "محصول", "تنوع", "مکان", "نوع", "تغییر", "قبل", "بعد", "کانال", "مرجع", "مبلغ"],
            rows=data,
        )

    movement_columns = await _table_column_names(session, "stock_movements")
    unit_list_price_expr = StockMovement.unit_list_price if "unit_list_price" in movement_columns else literal(None).label("unit_list_price")
    unit_sale_price_expr = StockMovement.unit_sale_price if "unit_sale_price" in movement_columns else literal(None).label("unit_sale_price")
    discount_total_expr = StockMovement.discount_total if "discount_total" in movement_columns else literal(None).label("discount_total")
    line_total_expr = StockMovement.line_total if "line_total" in movement_columns else literal(None).label("line_total")

    sales_query = (
        select(
            StockMovement.created_at,
            Product.name,
            ProductVariant.id,
            ProductVariant.sku,
            SalesChannel.name,
            StockMovement.external_reference,
            StockMovement.quantity,
            unit_list_price_expr,
            unit_sale_price_expr,
            discount_total_expr,
            line_total_expr,
        )
        .join(ProductVariant, ProductVariant.id == StockMovement.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .outerjoin(SalesChannel, SalesChannel.id == StockMovement.channel_id)
    )
    if "line_total" in movement_columns:
        sales_query = sales_query.where(StockMovement.line_total.is_not(None))
    else:
        # Legacy schema fallback: sales price snapshot columns were added later.
        # Channel-linked outbound movements are still exportable with blank price cells.
        sales_query = sales_query.where(StockMovement.channel_id.is_not(None), StockMovement.quantity < 0)

    rows = (await session.execute(
        sales_query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    )).all()
    data = [[
        created_at,
        product_name,
        labels.get(int(variant_id)) or sku or "تنوع پایه",
        channel_name or "—",
        external_reference or "—",
        abs(int(quantity)),
        unit_list_price,
        unit_sale_price,
        discount_total,
        line_total,
    ] for created_at, product_name, variant_id, sku, channel_name, external_reference, quantity, unit_list_price, unit_sale_price, discount_total, line_total in rows]
    return ReportData(
        title="گزارش فروش",
        columns=["زمان", "محصول", "تنوع", "کانال", "مرجع", "تعداد", "قیمت لیست", "قیمت فروش", "تخفیف", "جمع"],
        rows=data,
    )


_ILLEGAL_XLSX_CHARS = {chr(code) for code in range(32)} - {"\t", "\n", "\r"}


def _xlsx_cell_value(value: Any) -> Any:
    value = _display(value) if isinstance(value, (datetime, date, time, Enum, Decimal)) else value
    if isinstance(value, str):
        # Excel rejects C0 control characters and openpyxl raises IllegalCharacterError.
        value = "".join(ch for ch in value if ch not in _ILLEGAL_XLSX_CHARS)
        # Prevent spreadsheet formula injection from user-controlled names/SKUs/references.
        if value.startswith(("=", "+", "-", "@")):
            value = "'" + value
    return value


def _pdf_text(value: Any) -> str:
    # ReportLab Paragraph parses a small HTML-like markup language; escaping keeps
    # product names/references containing &, < or > from breaking the document.
    return escape(_rtl_text(value))


def _xlsx_column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def build_xlsx(report: ReportData) -> bytes:
    """Build a small, standards-compliant XLSX using only the Python stdlib.

    Keeping the writer dependency-free prevents report downloads from failing just
    because openpyxl was not installed after an application update.
    """
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZipFile

    all_rows: list[list[Any]] = [list(report.columns)] + [
        [_xlsx_cell_value(value) for value in row] for row in report.rows
    ]
    column_count = max((len(row) for row in all_rows), default=1)
    row_count = max(len(all_rows), 1)
    last_col = _xlsx_column_letter(column_count)

    widths: list[int] = []
    for col_idx in range(column_count):
        max_len = 8
        for row in all_rows:
            value = row[col_idx] if col_idx < len(row) else ""
            max_len = max(max_len, len(str(value or "")))
        widths.append(min(max(max_len + 2, 10), 42))

    def cell_xml(row_idx: int, col_idx: int, value: Any, style: int) -> str:
        ref = f"{_xlsx_column_letter(col_idx)}{row_idx}"
        if value is None:
            return f'<c r="{ref}" s="{style}"/>'
        if isinstance(value, bool):
            return f'<c r="{ref}" s="{style}" t="b"><v>{1 if value else 0}</v></c>'
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
        text_value = escape(str(value))
        return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text_value}</t></is></c>'

    row_xml: list[str] = []
    for row_idx, row in enumerate(all_rows, start=1):
        style = 1 if row_idx == 1 else 2
        cells = [
            cell_xml(row_idx, col_idx, row[col_idx - 1] if col_idx - 1 < len(row) else None, style)
            for col_idx in range(1, column_count + 1)
        ]
        row_xml.append(f'<row r="{row_idx}">{"".join(cells)}</row>')

    cols_xml = "".join(
        f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
        for i, width in enumerate(widths, start=1)
    )
    dimension = f"A1:{last_col}{row_count}"

    worksheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="{dimension}"/>
  <sheetViews><sheetView workbookViewId="0" rightToLeft="1"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>{cols_xml}</cols>
  <sheetData>{"".join(row_xml)}</sheetData>
  <autoFilter ref="{dimension}"/>
  <pageMargins left="0.3" right="0.3" top="0.4" bottom="0.4" header="0.2" footer="0.2"/>
  <pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"/>
</worksheet>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE2E8F0"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFCBD5E1"/></left><right style="thin"><color rgb="FFCBD5E1"/></right><top style="thin"><color rgb="FFCBD5E1"/></top><bottom style="thin"><color rgb="FFCBD5E1"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews><workbookView/></bookViews>
  <sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets>
  <calcPr calcId="0"/>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''

    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
    return out.getvalue()

def _pdf_font_path() -> str | None:
    configured = str(settings.REPORT_FONT_PATH).strip() if settings.REPORT_FONT_PATH else ""
    candidates = [
        configured,
        # Prefer fonts with both Persian and Latin glyphs so SKU/serial/date text
        # does not disappear from mixed-language report cells.
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        r"C:\\Windows\\Fonts\\Vazirmatn-Regular.ttf",
        r"C:\\Windows\\Fonts\\Vazir.ttf",
        r"C:\\Windows\\Fonts\\tahoma.ttf",
        r"C:\\Windows\\Fonts\\segoeui.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


# Arabic Presentation Forms used as a dependency-free fallback for PDF reports.
# Tuple order: isolated, final, initial, medial. ``None`` means the character
# does not connect on that side (for example Alef, Dal, Reh, Waw).
_ARABIC_FORMS: dict[str, tuple[str, str | None, str | None, str | None]] = {
    "ء": ("\ufe80", None, None, None),
    "آ": ("\ufe81", "\ufe82", None, None),
    "أ": ("\ufe83", "\ufe84", None, None),
    "ؤ": ("\ufe85", "\ufe86", None, None),
    "إ": ("\ufe87", "\ufe88", None, None),
    "ئ": ("\ufe89", "\ufe8a", "\ufe8b", "\ufe8c"),
    "ا": ("\ufe8d", "\ufe8e", None, None),
    "ب": ("\ufe8f", "\ufe90", "\ufe91", "\ufe92"),
    "ة": ("\ufe93", "\ufe94", None, None),
    "ت": ("\ufe95", "\ufe96", "\ufe97", "\ufe98"),
    "ث": ("\ufe99", "\ufe9a", "\ufe9b", "\ufe9c"),
    "ج": ("\ufe9d", "\ufe9e", "\ufe9f", "\ufea0"),
    "ح": ("\ufea1", "\ufea2", "\ufea3", "\ufea4"),
    "خ": ("\ufea5", "\ufea6", "\ufea7", "\ufea8"),
    "د": ("\ufea9", "\ufeaa", None, None),
    "ذ": ("\ufeab", "\ufeac", None, None),
    "ر": ("\ufead", "\ufeae", None, None),
    "ز": ("\ufeaf", "\ufeb0", None, None),
    "س": ("\ufeb1", "\ufeb2", "\ufeb3", "\ufeb4"),
    "ش": ("\ufeb5", "\ufeb6", "\ufeb7", "\ufeb8"),
    "ص": ("\ufeb9", "\ufeba", "\ufebb", "\ufebc"),
    "ض": ("\ufebd", "\ufebe", "\ufebf", "\ufec0"),
    "ط": ("\ufec1", "\ufec2", "\ufec3", "\ufec4"),
    "ظ": ("\ufec5", "\ufec6", "\ufec7", "\ufec8"),
    "ع": ("\ufec9", "\ufeca", "\ufecb", "\ufecc"),
    "غ": ("\ufecd", "\ufece", "\ufecf", "\ufed0"),
    "ف": ("\ufed1", "\ufed2", "\ufed3", "\ufed4"),
    "ق": ("\ufed5", "\ufed6", "\ufed7", "\ufed8"),
    "ك": ("\ufed9", "\ufeda", "\ufedb", "\ufedc"),
    "ل": ("\ufedd", "\ufede", "\ufedf", "\ufee0"),
    "م": ("\ufee1", "\ufee2", "\ufee3", "\ufee4"),
    "ن": ("\ufee5", "\ufee6", "\ufee7", "\ufee8"),
    "ه": ("\ufee9", "\ufeea", "\ufeeb", "\ufeec"),
    "و": ("\ufeed", "\ufeee", None, None),
    "ى": ("\ufeef", "\ufef0", None, None),
    "ي": ("\ufef1", "\ufef2", "\ufef3", "\ufef4"),
    "پ": ("\ufb56", "\ufb57", "\ufb58", "\ufb59"),
    "چ": ("\ufb7a", "\ufb7b", "\ufb7c", "\ufb7d"),
    "ژ": ("\ufb8a", "\ufb8b", None, None),
    "ک": ("\ufb8e", "\ufb8f", "\ufb90", "\ufb91"),
    "گ": ("\ufb92", "\ufb93", "\ufb94", "\ufb95"),
    "ی": ("\ufbfc", "\ufbfd", "\ufbfe", "\ufbff"),
}


def _simple_arabic_reshape(text_value: str) -> str:
    chars = list(text_value)
    shaped: list[str] = []
    for index, char in enumerate(chars):
        forms = _ARABIC_FORMS.get(char)
        if forms is None:
            shaped.append(char)
            continue

        prev_char = chars[index - 1] if index > 0 else ""
        next_char = chars[index + 1] if index + 1 < len(chars) else ""
        prev_forms = _ARABIC_FORMS.get(prev_char)
        next_forms = _ARABIC_FORMS.get(next_char)

        joins_prev = bool(forms[1] and prev_forms and prev_forms[2])
        joins_next = bool(forms[2] and next_forms and next_forms[1])
        if joins_prev and joins_next and forms[3]:
            shaped.append(forms[3])
        elif joins_prev and forms[1]:
            shaped.append(forms[1])
        elif joins_next and forms[2]:
            shaped.append(forms[2])
        else:
            shaped.append(forms[0])
    return "".join(shaped)


def _simple_rtl_display(text_value: str) -> str:
    """Small base-RTL visual-order fallback for Persian business report text.

    It preserves Latin/numeric runs (SKU, serials, dates, prices) in LTR order
    while reversing Arabic runs for PDF engines that do not implement bidi.
    """
    import unicodedata

    shaped = _simple_arabic_reshape(text_value)
    kinds: list[str | None] = []
    for char in shaped:
        code = ord(char)
        bidi = unicodedata.bidirectional(char)
        if 0xFB50 <= code <= 0xFDFF or 0xFE70 <= code <= 0xFEFF or bidi in {"R", "AL"}:
            kinds.append("R")
        elif bidi in {"L", "EN", "AN"}:
            kinds.append("L")
        else:
            kinds.append(None)

    # Attach neutral punctuation/spaces to surrounding runs. This keeps slashes
    # inside Persian labels and spaces inside values such as "SKU D04" natural.
    for i, kind in enumerate(kinds):
        if kind is not None:
            continue
        prev_kind = next((kinds[j] for j in range(i - 1, -1, -1) if kinds[j] is not None), None)
        next_kind = next((kinds[j] for j in range(i + 1, len(kinds)) if kinds[j] is not None), None)
        kinds[i] = prev_kind if prev_kind is not None else (next_kind or "R")
        if prev_kind is not None and next_kind is not None and prev_kind == next_kind:
            kinds[i] = prev_kind

    runs: list[tuple[str, str]] = []
    for char, kind in zip(shaped, kinds):
        resolved = kind or "R"
        if runs and runs[-1][0] == resolved:
            runs[-1] = (resolved, runs[-1][1] + char)
        else:
            runs.append((resolved, char))

    visual_parts: list[str] = []
    for kind, value in reversed(runs):
        visual_parts.append(value if kind == "L" else value[::-1])
    return "".join(visual_parts)


def _rtl_text(value: Any) -> str:
    text_value = _display(value)
    if not any("\u0600" <= char <= "\u06ff" for char in text_value):
        return text_value
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text_value))
    except (ModuleNotFoundError, ImportError):
        # Keep PDF export functional on minimal installations. The optional
        # packages above still provide a fuller Unicode bidi implementation.
        return _simple_rtl_display(text_value)


def build_pdf(report: ReportData) -> bytes:
    from io import BytesIO
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "کتابخانه PDF روی بک‌اند نصب نیست؛ در پوشه backend دستور pip install -r requirements.txt را اجرا کنید"
        ) from exc

    font_path = _pdf_font_path()
    if not font_path:
        raise RuntimeError("برای خروجی PDF یک فونت فارسی روی سرور لازم است؛ REPORT_FONT_PATH را روی فایل فونت Vazirmatn تنظیم کنید")

    font_name = "DarioReportFont"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, font_path))

    out = BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=landscape(A4),
        rightMargin=9 * mm,
        leftMargin=9 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=report.title,
        author="Dario",
    )
    title_style = ParagraphStyle("title", fontName=font_name, fontSize=15, leading=22, alignment=2)
    cell_style = ParagraphStyle("cell", fontName=font_name, fontSize=7.2, leading=10, alignment=2)
    header_style = ParagraphStyle("header", fontName=font_name, fontSize=7.5, leading=10, alignment=2)
    title = Paragraph(_pdf_text(report.title), title_style)
    generated = Paragraph(_pdf_text(f"تاریخ تهیه: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), cell_style)

    # ReportLab tables are LTR by default. Reverse the logical column order so
    # the first Persian column is visually placed on the right, matching Excel.
    table_rows = [[Paragraph(_pdf_text(value), header_style) for value in reversed(report.columns)]]
    table_rows += [[Paragraph(_pdf_text(value), cell_style) for value in reversed(row)] for row in report.rows]
    usable_width = landscape(A4)[0] - 18 * mm
    col_width = usable_width / max(len(report.columns), 1)
    table = Table(table_rows, repeatRows=1, colWidths=[col_width] * len(report.columns), hAlign="RIGHT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    doc.build([title, generated, Spacer(1, 5 * mm), table])
    return out.getvalue()


async def create_database_backup(session: AsyncSession) -> tuple[str, str]:
    """Create an admin-only logical JSON.GZ snapshot and return (path, filename).

    The caller must provide a session that has not already executed a SQL statement.
    This matters on PostgreSQL because the snapshot isolation level must be selected
    before the first query in the transaction.
    """
    dialect_name = session.bind.dialect.name if session.bind else None

    # A repeatable-read, read-only transaction gives PostgreSQL/Neon a consistent
    # logical snapshot.  This MUST be the first SQL statement on this session.
    if dialect_name == "postgresql":
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))

    # Inspect the live database once. This avoids turning a harmless migration gap
    # (a model exists in code but its table is not deployed yet) into a failed backup.
    connection = await session.connection()
    existing_tables = set(
        await connection.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    )

    alembic_revision = None
    if "alembic_version" in existing_tables:
        alembic_revision = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"dario-database-backup-{stamp}.json.gz"
    tmp = tempfile.NamedTemporaryFile(prefix="dario-backup-", suffix=".json.gz", delete=False)
    path = tmp.name
    tmp.close()

    try:
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as fh:
            metadata = {
                "format": "dario-logical-backup-v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "alembic_revision": alembic_revision,
                "database_dialect": dialect_name,
                "tables": {},
                "skipped_model_tables": [],
            }
            fh.write('{"data":{')

            first_table = True
            for table in Base.metadata.sorted_tables:
                if table.name not in existing_tables:
                    metadata["skipped_model_tables"].append(table.name)
                    continue

                if not first_table:
                    fh.write(",")
                first_table = False
                fh.write(json.dumps(table.name, ensure_ascii=False))
                fh.write(":[")
                first_row = True
                count = 0
                stream = await session.stream(select(table))
                async for row in stream.mappings():
                    if not first_row:
                        fh.write(",")
                    first_row = False
                    payload = {str(key): _json_value(value) for key, value in row.items()}
                    fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
                    count += 1
                fh.write("]")
                metadata["tables"][table.name] = count
            fh.write('},"metadata":')
            fh.write(json.dumps(metadata, ensure_ascii=False, default=_json_value, separators=(",", ":")))
            fh.write("}")
        return path, filename
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
