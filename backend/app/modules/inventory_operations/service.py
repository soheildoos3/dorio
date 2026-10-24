from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.inventory.constants import ProductItemStatus, StockMovementType
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory_operations.constants import (
    CycleCountLineStatus,
    CycleCountStatus,
    StockAdjustmentType,
    StockTransferStatus,
)
from app.modules.inventory_operations.repository import InventoryOperationsRepository
from app.modules.warehouse.model import Location
from app.modules.inventory_operations.schemas import *
from app.modules.inventory_operations.numbers import next_document_number


class OperationNotFoundError(LookupError):
    pass


class OperationConflictError(ValueError):
    pass


class InventoryOperationsService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InventoryOperationsRepository(session)
        self.inv = InventoryRepository(session)

    async def create_transfer(self, p: StockTransferCreate):
        if not p.transfer_number:
            p = p.model_copy(update={"transfer_number": await next_document_number(self.session, "TRF")})
        if p.from_location_id == p.to_location_id:
            raise OperationConflictError(
                "Source and destination locations must be different"
            )
        source = await self.session.get(Location, p.from_location_id)
        destination = await self.session.get(Location, p.to_location_id)
        if source is None or destination is None:
            raise OperationNotFoundError("Source or destination location not found")
        if not source.is_active or not destination.is_active:
            raise OperationConflictError("Source and destination locations must be active")
        if p.item_id is not None:
            if p.quantity != 1:
                raise OperationConflictError("Serialized transfer quantity must be 1")
            item = await self.inv.get_item(p.item_id)
            if item is None:
                raise OperationNotFoundError("Product item not found")
            if item.variant_id != p.variant_id or item.location_id != p.from_location_id:
                raise OperationConflictError("Item does not match transfer variant/source location")
            if item.status != ProductItemStatus.IN_STOCK:
                raise OperationConflictError("Only in-stock serialized items can be transferred")
        try:
            o = await self.repo.create_transfer(**p.model_dump())
            await self.session.commit()
            await self.session.refresh(o)
            return o
        except IntegrityError as e:
            await self.session.rollback()
            raise OperationConflictError(
                "Transfer number already exists or reference is invalid"
            ) from e

    async def complete_transfer(self, id: int, approved_by: int):
        t = await self.repo.get_transfer(id, for_update=True)
        if not t:
            raise OperationNotFoundError("Transfer not found")
        if t.status in {StockTransferStatus.COMPLETED, StockTransferStatus.CANCELLED}:
            raise OperationConflictError(
                "Transfer cannot be completed in current status"
            )
        src = await self.inv.get_stock(
            t.variant_id, t.from_location_id, for_update=True
        )
        if not src or src.quantity < t.quantity:
            raise OperationConflictError("Insufficient available stock at source")
        dst = await self.inv.get_stock(t.variant_id, t.to_location_id, for_update=True)
        if not dst:
            dst = await self.inv.create_stock(t.variant_id, t.to_location_id)
        src_before = src.quantity
        dst_before = dst.quantity
        src.quantity -= t.quantity
        dst.quantity += t.quantity
        await self.inv.add_movement(
            item_id=t.item_id,
            variant_id=t.variant_id,
            location_id=t.from_location_id,
            type=StockMovementType.TRANSFER,
            quantity=-t.quantity,
            qty_before=src_before,
            qty_after=src.quantity,
            reference_type="transfer",
            reference_id=t.id,
            reason="transfer_out",
            created_by=approved_by,
        )
        await self.inv.add_movement(
            item_id=t.item_id,
            variant_id=t.variant_id,
            location_id=t.to_location_id,
            type=StockMovementType.TRANSFER,
            quantity=t.quantity,
            qty_before=dst_before,
            qty_after=dst.quantity,
            reference_type="transfer",
            reference_id=t.id,
            reason="transfer_in",
            created_by=approved_by,
        )
        t.status = StockTransferStatus.COMPLETED
        t.approved_by = approved_by
        t.completed_at = datetime.now(timezone.utc)
        item = await self.inv.get_item(t.item_id) if t.item_id else None
        if item:
            if item.variant_id != t.variant_id or item.location_id != t.from_location_id:
                raise OperationConflictError("Serialized item no longer matches transfer source")
            destination = await self.session.get(Location, t.to_location_id)
            if destination is None:
                raise OperationNotFoundError("Destination location not found")
            item.location_id = t.to_location_id
            item.warehouse_id = destination.warehouse_id
        await self.session.commit()
        await self.session.refresh(t)
        return t

    async def create_adjustment(self, p: StockAdjustmentCreate):
        if not p.adjustment_number:
            p = p.model_copy(update={"adjustment_number": await next_document_number(self.session, "ADJ")})
        if p.item_id is not None:
            if p.quantity != 1:
                raise OperationConflictError("Serialized adjustment quantity must be 1")
            item = await self.inv.get_item(p.item_id)
            if item is None:
                raise OperationNotFoundError("Product item not found")
            if item.variant_id != p.variant_id or item.location_id != p.location_id:
                raise OperationConflictError("Item does not match adjustment variant/location")
            if p.type == StockAdjustmentType.INCREASE:
                raise OperationConflictError("Serialized increases must use item receipt/QC workflow")
            if item.status != ProductItemStatus.IN_STOCK:
                raise OperationConflictError("Only in-stock serialized items can be decreased")
        stock = await self.inv.get_stock(p.variant_id, p.location_id, for_update=True)
        if not stock:
            stock = await self.inv.create_stock(p.variant_id, p.location_id)
        delta = p.quantity if p.type == StockAdjustmentType.INCREASE else -p.quantity
        before = stock.quantity
        after = before + delta
        if after < 0:
            raise OperationConflictError("Adjustment would create invalid stock")
        stock.quantity = after
        a = await self.repo.create_adjustment(**p.model_dump())
        await self.inv.add_movement(
            item_id=p.item_id,
            variant_id=p.variant_id,
            location_id=p.location_id,
            type=StockMovementType.ADJUST,
            quantity=delta,
            qty_before=before,
            qty_after=after,
            reference_type=p.reference_type or "adjustment",
            reference_id=p.reference_id,
            reason=p.reason.value,
            created_by=p.created_by,
        )
        if p.item_id is not None and p.type == StockAdjustmentType.DECREASE:
            item = await self.inv.get_item(p.item_id)
            if item is not None:
                from app.modules.inventory_operations.constants import StockAdjustmentReason
                if p.reason == StockAdjustmentReason.DAMAGE:
                    item.status = ProductItemStatus.DAMAGED
                elif p.reason == StockAdjustmentReason.LOSS:
                    item.status = ProductItemStatus.LOST
                else:
                    raise OperationConflictError("Serialized decrease reason must be damage or loss")
                item.moved_out_at = datetime.now(timezone.utc)
                item.location_id = None
                item.warehouse_id = None
        await self.session.commit()
        await self.session.refresh(a)
        return a

    async def create_cycle_count(self, p: CycleCountCreate):
        if not p.count_number:
            p = p.model_copy(update={"count_number": await next_document_number(self.session, "CC")})
        try:
            o = await self.repo.create_cycle_count(**p.model_dump())
            await self.session.commit()
            await self.session.refresh(o)
            return o
        except IntegrityError as e:
            await self.session.rollback()
            raise OperationConflictError(
                "Count number already exists or reference is invalid"
            ) from e

    async def add_cycle_line(self, p: CycleCountLineCreate):
        c = await self.repo.get_cycle_count(p.cycle_count_id)
        if not c:
            raise OperationNotFoundError("Cycle count not found")
        if c.status in {CycleCountStatus.COMPLETED, CycleCountStatus.CANCELLED}:
            raise OperationConflictError("Cycle count is closed")
        data = p.model_dump()
        data["difference"] = p.counted_qty - p.system_qty
        data["status"] = CycleCountLineStatus.COUNTED
        o = await self.repo.create_cycle_line(**data)
        await self.session.commit()
        await self.session.refresh(o)
        return o

    async def create_opening(self, p: StockOpeningCreate):
        if await self.repo.opening_exists(p.variant_id, p.location_id):
            raise OperationConflictError("Opening stock was already recorded for this variant/location")
        stock = await self.inv.get_stock(p.variant_id, p.location_id, for_update=True)
        if stock and stock.quantity != 0:
            raise OperationConflictError(
                "Opening stock can only be recorded before operational stock exists"
            )
        if not stock:
            stock = await self.inv.create_stock(p.variant_id, p.location_id)
        before = stock.quantity
        stock.quantity = p.quantity
        o = await self.repo.create_opening(**p.model_dump())
        await self.inv.add_movement(
            item_id=None,
            variant_id=p.variant_id,
            location_id=p.location_id,
            type=StockMovementType.IN,
            quantity=p.quantity - before,
            qty_before=before,
            qty_after=p.quantity,
            reference_type="opening",
            reference_id=o.id,
            reason="opening_stock",
            created_by=p.recorded_by,
        )
        await self.session.commit()
        await self.session.refresh(o)
        return o
