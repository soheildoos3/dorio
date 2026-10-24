from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.service import AccountingService
from app.modules.inventory.constants import (
    OutboundDisposition,
    ProductItemStatus,
    StockMovementType,
    StockReservationStatus,
)
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.model import ProductItem
from app.modules.catalog.model import ProductVariant
from app.modules.channels.model import ProductChannelPrice, SalesChannel
from app.modules.warehouse.model import Location
from app.modules.warranty.serials import generate_warranty_serial
from app.modules.warranty.service import WarrantyService

from app.modules.inventory.schemas import (
    ProductDefaultLocationCreate,
    ProductItemCreate,
    ProductItemBatchCreate,
    StockMovementCreate,
    StockOutboundCreate,
    StockReservationCreate,
)


class InventoryNotFoundError(LookupError):
    pass


class InventoryConflictError(ValueError):
    pass


class InventoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InventoryRepository(session)

    async def create_item(self, payload: ProductItemCreate):
        # A physical item starts in pending QC. When a location is supplied,
        # warehouse_id must also be supplied so the record is not ambiguous.
        if (payload.location_id is None) != (payload.warehouse_id is None):
            raise InventoryConflictError(
                "location_id and warehouse_id must be provided together"
            )
        if payload.location_id is not None:
            location = await self.session.get(Location, payload.location_id)
            if location is None:
                raise InventoryNotFoundError("Location not found")
            if location.warehouse_id != payload.warehouse_id:
                raise InventoryConflictError("Location does not belong to warehouse_id")
            if not location.is_active:
                raise InventoryConflictError("Location is inactive")
        try:
            data = payload.model_dump()
            data["serial_number"] = (data.get("serial_number") or "").strip() or None
            data["warranty_serial"] = await generate_warranty_serial(self.session)
            obj = await self.repo.create_item(**data)
            await WarrantyService(self.session).ensure_for_item(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as exc:
            await self.session.rollback()
            raise InventoryConflictError(
                "Serial number already exists, warranty generation failed, or referenced data is invalid"
            ) from exc

    async def create_items_batch(self, payload: ProductItemBatchCreate):
        if (payload.location_id is None) != (payload.warehouse_id is None):
            raise InventoryConflictError("location_id and warehouse_id must be provided together")
        if payload.location_id is not None:
            location = await self.session.get(Location, payload.location_id)
            if location is None:
                raise InventoryNotFoundError("Location not found")
            if location.warehouse_id != payload.warehouse_id:
                raise InventoryConflictError("Location does not belong to warehouse_id")
            if not location.is_active:
                raise InventoryConflictError("Location is inactive")
        created = []
        try:
            for _ in range(payload.count):
                obj = await self.repo.create_item(
                    variant_id=payload.variant_id,
                    serial_number=None,
                    warranty_serial=await generate_warranty_serial(self.session),
                    location_id=payload.location_id,
                    warehouse_id=payload.warehouse_id,
                    received_at=payload.received_at,
                )
                await WarrantyService(self.session).ensure_for_item(obj)
                created.append(obj)
            await self.session.commit()
            for obj in created:
                await self.session.refresh(obj)
            return created
        except IntegrityError as exc:
            await self.session.rollback()
            raise InventoryConflictError("Batch item creation failed because a serial/reference conflicted") from exc

    async def apply_stock_movement(self, payload: StockMovementCreate):
        # Manual movements are intentionally narrow. Workflow-specific movement
        # types must only be produced by their dedicated services.
        if payload.type not in {
            StockMovementType.IN,
            StockMovementType.OUT,
            StockMovementType.ADJUST,
        }:
            raise InventoryConflictError(
                "This movement type must be created by its dedicated workflow"
            )
        if payload.item_id is not None:
            raise InventoryConflictError(
                "Serialized items must use dedicated outbound/QC/transfer workflows"
            )
        if payload.location_id is None:
            raise InventoryConflictError(
                "location_id is required for a stock-affecting movement"
            )
        if payload.quantity == 0:
            raise InventoryConflictError("Movement quantity cannot be zero")
        if payload.type == StockMovementType.IN and payload.quantity < 0:
            raise InventoryConflictError("IN movement quantity must be positive")
        if payload.type == StockMovementType.OUT and payload.quantity > 0:
            raise InventoryConflictError("OUT movement quantity must be negative")

        stock = await self.repo.get_stock(
            payload.variant_id, payload.location_id, for_update=True
        )
        if stock is None:
            if payload.quantity < 0:
                raise InventoryConflictError("Insufficient stock")
            stock = await self.repo.create_stock(
                payload.variant_id, payload.location_id
            )
        before = stock.quantity
        after = before + payload.quantity
        if after < 0:
            raise InventoryConflictError("Insufficient stock")
        stock.quantity = after
        movement = await self.repo.add_movement(
            **payload.model_dump(), qty_before=before, qty_after=after
        )
        await self.session.commit()
        await self.session.refresh(movement)
        return movement

    async def reserve(self, payload: StockReservationCreate, *, commit: bool = True):
        stock = await self.repo.get_stock(
            payload.variant_id, payload.location_id, for_update=True
        )
        if not stock:
            raise InventoryNotFoundError("Stock row not found")
        if stock.quantity < payload.quantity:
            raise InventoryConflictError("Insufficient available stock")

        item = None
        if payload.item_id is not None:
            if payload.quantity != 1:
                raise InventoryConflictError(
                    "Serialized item reservation quantity must be 1"
                )
            item = await self.repo.get_item(payload.item_id)
            if not item:
                raise InventoryNotFoundError("Product item not found")
            if (
                item.variant_id != payload.variant_id
                or item.location_id != payload.location_id
            ):
                raise InventoryConflictError(
                    "Reserved item does not match variant/location"
                )
            if item.status != ProductItemStatus.IN_STOCK:
                raise InventoryConflictError("Product item is not available")

        before = stock.quantity
        stock.quantity -= payload.quantity
        stock.reserved += payload.quantity
        if item is not None:
            item.status = ProductItemStatus.RESERVED

        reservation = await self.repo.create_reservation(**payload.model_dump())
        await self.repo.add_movement(
            item_id=payload.item_id,
            variant_id=payload.variant_id,
            location_id=payload.location_id,
            type=StockMovementType.RESERVE,
            quantity=-payload.quantity,
            qty_before=before,
            qty_after=stock.quantity,
            reference_type=payload.reference_type,
            reference_id=payload.reference_id,
            external_reference=payload.reference_code,
            reason=f"reserved:{payload.quantity}",
            created_by=payload.created_by,
        )
        if commit:
            await self.session.commit()
            await self.session.refresh(reservation)
        else:
            await self.session.flush()
        return reservation

    async def release_reservation(
        self, reservation_id: int, created_by: int | None = None, *, commit: bool = True
    ):
        reservation = await self.repo.get_reservation(
            reservation_id, for_update=True
        )
        if not reservation:
            raise InventoryNotFoundError("Reservation not found")
        if reservation.status != StockReservationStatus.ACTIVE:
            raise InventoryConflictError("Reservation is not active")
        stock = await self.repo.get_stock(
            reservation.variant_id, reservation.location_id, for_update=True
        )
        if not stock or stock.reserved < reservation.quantity:
            raise InventoryConflictError(
                "Stock reservation counters are inconsistent"
            )

        before = stock.quantity
        stock.quantity += reservation.quantity
        stock.reserved -= reservation.quantity
        reservation.status = StockReservationStatus.RELEASED
        if reservation.item_id is not None:
            item = await self.repo.get_item(reservation.item_id)
            if item is not None and item.status == ProductItemStatus.RESERVED:
                item.status = ProductItemStatus.IN_STOCK

        await self.repo.add_movement(
            item_id=reservation.item_id,
            variant_id=reservation.variant_id,
            location_id=reservation.location_id,
            type=StockMovementType.RELEASE,
            quantity=reservation.quantity,
            qty_before=before,
            qty_after=stock.quantity,
            reference_type=reservation.reference_type,
            reference_id=reservation.reference_id,
            external_reference=reservation.reference_code,
            reason=f"released:{reservation.quantity}",
            created_by=created_by,
        )
        if commit:
            await self.session.commit()
            await self.session.refresh(reservation)
        else:
            await self.session.flush()
        return reservation

    async def _resolve_sale_price(self, variant_id: int, channel_id: int, now: datetime):
        channel = await self.session.get(SalesChannel, channel_id)
        if channel is None or not channel.is_active:
            raise InventoryConflictError("پلتفرم فروش معتبر یا فعال نیست")
        row = await self.session.scalar(
            select(ProductChannelPrice).where(
                ProductChannelPrice.variant_id == variant_id,
                ProductChannelPrice.channel_id == channel_id,
            )
        )
        if row is not None:
            list_price = Decimal(row.list_price)
            active = row.is_active and (row.starts_at is None or now >= row.starts_at) and (row.ends_at is None or now < row.ends_at)
            sale_price = list_price
            if active:
                discount = Decimal(row.discount_value or 0)
                if row.discount_type == "percent":
                    sale_price = list_price - (list_price * discount / Decimal("100"))
                elif row.discount_type == "fixed":
                    sale_price = list_price - discount
            return list_price, max(sale_price, Decimal("0"))
        variant = await self.session.get(ProductVariant, variant_id)
        if variant is None:
            raise InventoryNotFoundError("Product variant not found")
        base = Decimal(variant.sale_price or 0)
        return base, base

    async def outbound(self, payload: StockOutboundCreate, *, commit: bool = True, unit_list_price_override: Decimal | None = None, unit_sale_price_override: Decimal | None = None, skip_sale_accounting: bool = False):
        stock = await self.repo.get_stock(
            payload.variant_id, payload.location_id, for_update=True
        )
        if stock is None:
            raise InventoryNotFoundError("Stock row not found")

        item = None
        reservation = None
        if payload.item_id is None:
            serialized_item_id = await self.session.scalar(
                select(ProductItem.id).where(
                    ProductItem.variant_id == payload.variant_id,
                    ProductItem.location_id == payload.location_id,
                    ProductItem.status.in_([ProductItemStatus.IN_STOCK, ProductItemStatus.RESERVED]),
                ).limit(1)
            )
            if serialized_item_id is not None:
                raise InventoryConflictError(
                    "برای این کالا واحد سریال‌دار در این قفس وجود دارد؛ برای جلوگیری از ناسازگاری موجودی، شماره گارانتی همان واحد را انتخاب کنید"
                )
        if payload.item_id is not None:
            item = await self.repo.get_item(payload.item_id)
            if item is None:
                raise InventoryNotFoundError("Product item not found")
            if (
                item.variant_id != payload.variant_id
                or item.location_id != payload.location_id
            ):
                raise InventoryConflictError(
                    "Product item does not match variant/location"
                )

        # Fulfilled reservation: release it into available quantity first, then
        # perform a normal OUT. This preserves the existing stock semantics and
        # produces a complete append-only audit trail.
        if payload.reservation_id is not None:
            reservation = await self.repo.get_reservation(
                payload.reservation_id, for_update=True
            )
            if reservation is None:
                raise InventoryNotFoundError("Reservation not found")
            if reservation.status != StockReservationStatus.ACTIVE:
                raise InventoryConflictError("Reservation is not active")
            if (
                reservation.variant_id != payload.variant_id
                or reservation.location_id != payload.location_id
                or reservation.quantity != payload.quantity
                or reservation.item_id != payload.item_id
            ):
                raise InventoryConflictError(
                    "Outbound data does not match the reservation"
                )
            if stock.reserved < reservation.quantity:
                raise InventoryConflictError(
                    "Stock reservation counters are inconsistent"
                )
            before_release = stock.quantity
            stock.quantity += reservation.quantity
            stock.reserved -= reservation.quantity
            reservation.status = StockReservationStatus.FULFILLED
            await self.repo.add_movement(
                item_id=reservation.item_id,
                variant_id=reservation.variant_id,
                location_id=reservation.location_id,
                type=StockMovementType.RELEASE,
                quantity=reservation.quantity,
                qty_before=before_release,
                qty_after=stock.quantity,
                reference_type=reservation.reference_type,
                reference_id=reservation.reference_id,
                external_reference=reservation.reference_code,
                reason="reservation_fulfilled",
                created_by=payload.created_by,
            )
        elif item is not None and item.status == ProductItemStatus.RESERVED:
            raise InventoryConflictError(
                "Reserved serialized item requires reservation_id"
            )

        if item is not None and item.status not in {
            ProductItemStatus.IN_STOCK,
            ProductItemStatus.RESERVED,
        }:
            raise InventoryConflictError("Product item is not available for outbound")

        if stock.quantity < payload.quantity:
            raise InventoryConflictError("Insufficient available stock")

        before = stock.quantity
        stock.quantity -= payload.quantity
        now = datetime.now(timezone.utc)

        if item is not None:
            if payload.disposition == OutboundDisposition.SALE:
                item.status = ProductItemStatus.SOLD
                item.sold_at = now
                await WarrantyService(self.session).mark_outbound_sale(item, now)
            elif payload.disposition == OutboundDisposition.DAMAGE:
                item.status = ProductItemStatus.DAMAGED
            elif payload.disposition == OutboundDisposition.LOSS:
                item.status = ProductItemStatus.LOST
            elif payload.disposition == OutboundDisposition.RETURN:
                item.status = ProductItemStatus.RETURNED
            else:
                raise InventoryConflictError(
                    "Serialized item requires sale/damage/loss/return disposition"
                )
            item.moved_out_at = now
            item.location_id = None
            item.warehouse_id = None

        unit_list_price = None
        unit_sale_price = None
        discount_total = None
        line_total = None
        if payload.disposition == OutboundDisposition.SALE:
            if payload.channel_id is None:
                raise InventoryConflictError("برای فروش، انتخاب پلتفرم/کانال فروش الزامی است")
            if unit_sale_price_override is None:
                unit_list_price, unit_sale_price = await self._resolve_sale_price(payload.variant_id, payload.channel_id, now)
            else:
                channel = await self.session.get(SalesChannel, payload.channel_id)
                if channel is None or not channel.is_active:
                    raise InventoryConflictError("پلتفرم فروش معتبر یا فعال نیست")
                unit_sale_price = max(Decimal(unit_sale_price_override), Decimal("0"))
                unit_list_price = max(Decimal(unit_list_price_override if unit_list_price_override is not None else unit_sale_price), unit_sale_price)
            qty = Decimal(payload.quantity)
            discount_total = (unit_list_price - unit_sale_price) * qty
            line_total = unit_sale_price * qty

        unit_cost_snapshot = Decimal(item.unit_cost_snapshot) if item is not None and item.unit_cost_snapshot is not None else None
        movement = await self.repo.add_movement(
            item_id=payload.item_id,
            variant_id=payload.variant_id,
            location_id=payload.location_id,
            type=StockMovementType.OUT,
            quantity=-payload.quantity,
            qty_before=before,
            qty_after=stock.quantity,
            reference_type=payload.reference_type,
            reference_id=payload.reference_id,
            reason=(
                f"{payload.disposition.value}: {payload.reason}"
                if payload.reason
                else payload.disposition.value
            ),
            channel_id=payload.channel_id,
            external_reference=payload.external_reference,
            unit_list_price=unit_list_price,
            unit_sale_price=unit_sale_price,
            discount_total=discount_total,
            line_total=line_total,
            unit_cost_snapshot=unit_cost_snapshot,
            created_by=payload.created_by,
        )

        # Sales create two accounting effects in the same DB transaction:
        # revenue recognition and COGS recognition using the frozen unit cost.
        if payload.disposition == OutboundDisposition.SALE and payload.created_by is not None and not skip_sale_accounting:
            accounting = AccountingService(self.session)
            if line_total is not None:
                await accounting.auto_post(
                    user_id=payload.created_by,
                    description=f"فروش خروج انبار {payload.external_reference or movement.id}",
                    source_type="stock_sale",
                    source_id=movement.id,
                    source_ref=payload.external_reference,
                    debit_code="1200",
                    credit_code="4100",
                    amount=Decimal(line_total),
                    cost_center_code="SALES",
                    commit=False,
                )
            if unit_cost_snapshot is not None:
                await accounting.auto_post(
                    user_id=payload.created_by,
                    description=f"بهای تمام‌شده فروش {payload.external_reference or movement.id}",
                    source_type="stock_cogs",
                    source_id=movement.id,
                    source_ref=payload.external_reference,
                    debit_code="5100",
                    credit_code="1320",
                    amount=unit_cost_snapshot * Decimal(payload.quantity),
                    cost_center_code="FG",
                    commit=False,
                )
        if commit:
            await self.session.commit()
            await self.session.refresh(movement)
        else:
            await self.session.flush()
        return movement

    async def create_default_location(self, payload: ProductDefaultLocationCreate):
        try:
            if payload.is_primary:
                await self.repo.clear_primary_default_location(payload.variant_id)
            obj = await self.repo.create_default_location(**payload.model_dump())
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as exc:
            await self.session.rollback()
            raise InventoryConflictError(
                "Default location already exists, priority is duplicated, or reference is invalid"
            ) from exc
