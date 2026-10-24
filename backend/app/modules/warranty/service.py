from __future__ import annotations

import calendar
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.catalog.model import Media, Product, ProductVariant
from app.modules.inventory.model import ProductItem
from app.modules.warranty.model import WarrantyRecord, WarrantySetting


class WarrantyNotFoundError(LookupError):
    pass


class WarrantyConflictError(ValueError):
    pass


def add_months(value: datetime, months: int) -> datetime:
    if months < 0:
        raise ValueError("months must be non-negative")
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


class WarrantyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def default_setting(self) -> WarrantySetting | None:
        default = (
            await self.session.execute(
                select(WarrantySetting)
                .where(WarrantySetting.is_default.is_(True))
                .order_by(WarrantySetting.id.desc())
            )
        ).scalars().first()
        if default is not None:
            return default
        # Be tolerant of legacy/admin data where no row is flagged as default.
        return (
            await self.session.execute(
                select(WarrantySetting).order_by(WarrantySetting.id.desc())
            )
        ).scalars().first()

    async def grace_period_months(self) -> int:
        setting = await self.default_setting()
        return max(0, int(setting.grace_period_months if setting else 6))

    async def base_url(self) -> str:
        setting = await self.default_setting()
        return (setting.base_url if setting else settings.WARRANTY_BASE_URL).rstrip("/")

    async def product_warranty_months(self, item: ProductItem) -> int:
        row = await self.session.execute(
            select(Product.warranty_months)
            .join(ProductVariant, ProductVariant.product_id == Product.id)
            .where(ProductVariant.id == item.variant_id)
        )
        value = row.scalar_one_or_none()
        return max(1, int(value or 12))

    async def get_by_serial(self, serial: str, *, for_update: bool = False) -> WarrantyRecord | None:
        stmt = select(WarrantyRecord).where(WarrantyRecord.serial == serial)
        if for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def get_by_item(self, item_id: int, *, for_update: bool = False) -> WarrantyRecord | None:
        stmt = select(WarrantyRecord).where(WarrantyRecord.item_id == item_id)
        if for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def ensure_for_item(self, item: ProductItem) -> WarrantyRecord:
        existing = await self.get_by_item(item.id)
        if existing is not None:
            return existing
        if not item.warranty_serial:
            raise WarrantyConflictError("Warranty serial has not been generated for this item")
        months = await self.product_warranty_months(item)
        record = WarrantyRecord(
            item_id=item.id,
            serial=item.warranty_serial,
            status="inactive",
            warranty_months=months,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def mark_outbound_sale(self, item: ProductItem, when: datetime | None = None) -> WarrantyRecord:
        when = when or datetime.now(timezone.utc)
        record = await self.ensure_for_item(item)
        if record.status == "void":
            return record
        # Do not restart an already-active warranty on duplicate/replayed operations.
        # A returned item can be sold again; an already-activated warranty keeps its
        # original dates and simply resumes active/expired status.
        if record.activated_at is not None:
            await self.refresh_record(record, when)
            return record
        grace_months = await self.grace_period_months()
        record.status = "grace"
        record.outbound_at = when
        record.auto_activate_at = add_months(when, grace_months)
        record.expires_at = None
        record.activation_source = None
        # A zero-month grace period means activation is immediate.
        await self.refresh_record(record, when)
        await self.session.flush()
        return record

    async def refresh_record(self, record: WarrantyRecord, now: datetime | None = None) -> WarrantyRecord:
        now = now or datetime.now(timezone.utc)
        if record.status == "void":
            return record
        if record.activated_at is not None:
            if record.expires_at is None:
                record.expires_at = add_months(record.activated_at, record.warranty_months)
            if record.expires_at <= now:
                record.status = "expired"
            elif record.status != "expired":
                record.status = "active"
            return record
        if record.outbound_at is None:
            record.status = "inactive"
            return record
        if record.auto_activate_at is not None and record.auto_activate_at <= now:
            record.activated_at = record.auto_activate_at
            record.expires_at = add_months(record.activated_at, record.warranty_months)
            record.activation_source = "automatic"
            record.status = "expired" if record.expires_at <= now else "active"
            return record
        record.status = "grace"
        return record

    async def refresh_due(self) -> int:
        now = datetime.now(timezone.utc)
        rows = list(
            (
                await self.session.execute(
                    select(WarrantyRecord).where(
                        WarrantyRecord.activated_at.is_(None),
                        WarrantyRecord.outbound_at.is_not(None),
                        WarrantyRecord.auto_activate_at.is_not(None),
                        WarrantyRecord.auto_activate_at <= now,
                        WarrantyRecord.status != "void",
                    )
                )
            ).scalars().all()
        )
        for record in rows:
            await self.refresh_record(record, now)
        if rows:
            await self.session.commit()
        return len(rows)

    async def activate(
        self,
        record: WarrantyRecord,
        *,
        source: str,
        customer_name: str | None = None,
        customer_phone: str | None = None,
        when: datetime | None = None,
    ) -> WarrantyRecord:
        now = when or datetime.now(timezone.utc)
        await self.refresh_record(record, now)
        if record.status == "void":
            raise WarrantyConflictError("Warranty is void")
        if record.outbound_at is None:
            raise WarrantyConflictError("Warranty cannot be activated while the product is still in warehouse")
        if record.activated_at is not None:
            return record
        if customer_name is not None:
            record.customer_name = customer_name.strip() or None
        if customer_phone is not None:
            record.customer_phone = customer_phone.strip() or None
        record.activated_at = now
        record.expires_at = add_months(now, record.warranty_months)
        record.activation_source = source
        record.status = "active"
        await self.session.flush()
        return record

    async def public_payload(self, record: WarrantyRecord) -> dict:
        await self.refresh_record(record)
        row = (
            await self.session.execute(
                select(Product, ProductVariant)
                .join(ProductVariant, ProductVariant.product_id == Product.id)
                .join(ProductItem, ProductItem.variant_id == ProductVariant.id)
                .where(ProductItem.id == record.item_id)
            )
        ).first()
        product = row[0] if row else None
        variant = row[1] if row else None
        attributes: list[dict[str, str]] = []
        if variant is not None:
            for link in variant.attribute_values:
                value = link.attribute_value
                attributes.append({"name": value.attribute.name, "value": value.value})
        images: list[str] = []
        if product is not None:
            media_rows = list((await self.session.execute(
                select(Media)
                .where(Media.product_id == product.id)
                .where((Media.variant_id == None) | (Media.variant_id == (variant.id if variant else -1)))
                .order_by(Media.is_primary.desc(), Media.sort_order, Media.id)
            )).scalars().all())
            images = [m.url for m in media_rows]
        return {
            "serial": record.serial,
            "status": record.status,
            "product_name": product.name if product else "محصول Dario",
            "product_description": product.description if product else None,
            "product_sku": product.sku if product else None,
            "variant_sku": variant.sku if variant else None,
            "variant_attributes": attributes,
            "images": images,
            "warranty_months": record.warranty_months,
            "outbound_at": record.outbound_at,
            "auto_activate_at": record.auto_activate_at,
            "activated_at": record.activated_at,
            "expires_at": record.expires_at,
            "activation_source": record.activation_source,
            "can_activate": record.status == "grace" and record.activated_at is None,
        }
