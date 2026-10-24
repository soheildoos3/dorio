from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.service import AccountingService
from app.modules.inventory.constants import ProductItemStatus, QCStatus, StockMovementType
from app.modules.inventory.model import ProductItem
from app.modules.inventory.repository import InventoryRepository
from app.modules.manufacturing.model import ProductionOrder
from app.modules.tailors.model import TailorWork, TailorWorkEvent
from app.modules.quality.constants import LabelType, QCRecordResult
from app.modules.quality.repository import QualityRepository
from app.modules.quality.schemas import LabelCreate, QCRecordCreate

MONEY = Decimal("0.01")
UNIT_COST = Decimal("0.0001")


class QualityNotFoundError(LookupError):
    pass


class QualityConflictError(ValueError):
    pass


class QualityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = QualityRepository(session)
        self.inv = InventoryRepository(session)
        self.accounting = AccountingService(session)

    async def _locked_order(self, item: ProductItem) -> ProductionOrder | None:
        if item.production_order_id is None:
            return None
        return await self.session.scalar(
            select(ProductionOrder)
            .where(ProductionOrder.id == item.production_order_id)
            .with_for_update()
        )

    async def _passed_cost(self, order_id: int) -> Decimal:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(ProductItem.unit_cost_snapshot), 0)).where(
                ProductItem.production_order_id == order_id,
                ProductItem.qc_status == QCStatus.PASSED,
                ProductItem.unit_cost_snapshot.is_not(None),
            )
        )
        return Decimal(value or 0)

    async def _allocate_pending_unit_cost(self, order: ProductionOrder) -> Decimal:
        """Allocate the still-unassigned normal production cost across remaining good units.

        Normal losses remain in WIP and therefore increase the cost of the healthy output.
        Abnormal losses are explicitly removed from normal production cost through
        ``abnormal_scrap_cost`` and expensed when they occur.
        """
        total_normal_cost = (
            Decimal(order.material_cost)
            + Decimal(order.labor_cost)
            + Decimal(order.overhead_cost)
            - Decimal(order.abnormal_scrap_cost)
        )
        total_normal_cost = max(total_normal_cost, Decimal("0"))
        assigned = await self._passed_cost(order.id)
        remaining_cost = max(total_normal_cost - assigned, Decimal("0"))
        remaining_good_units = order.quantity - order.qc_passed
        if remaining_good_units <= 0:
            return Decimal("0")
        return (remaining_cost / Decimal(remaining_good_units)).quantize(UNIT_COST, rounding=ROUND_HALF_UP)

    async def _post_cost_transfer(
        self,
        *,
        item: ProductItem,
        p: QCRecordCreate,
        record_id: int,
        previous_status: ProductItemStatus,
    ) -> None:
        """Transfer the frozen unit cost between WIP, finished goods and abnormal loss."""
        if p.checked_by is None or item.unit_cost_snapshot is None:
            return
        amount = Decimal(item.unit_cost_snapshot).quantize(MONEY, rounding=ROUND_HALF_UP)
        if amount <= 0:
            return
        source_ref = f"ITEM-{item.id}"

        if p.result == QCRecordResult.PASSED and previous_status != ProductItemStatus.IN_STOCK:
            await self.accounting.auto_post(
                user_id=p.checked_by,
                description=f"تأیید QC و انتقال واحد {item.id} به کالای ساخته‌شده",
                source_type="qc_pass",
                source_id=record_id,
                source_ref=source_ref,
                debit_code="1320",
                credit_code="1310",
                amount=amount,
                cost_center_code="FG",
                commit=False,
            )
            return

        if p.result != QCRecordResult.FAILED:
            return

        if p.failure_action == "rework":
            if previous_status == ProductItemStatus.IN_STOCK:
                await self.accounting.auto_post(
                    user_id=p.checked_by,
                    description=f"برگشت واحد {item.id} از محصول ساخته‌شده به دوباره‌کاری",
                    source_type="qc_rework",
                    source_id=record_id,
                    source_ref=source_ref,
                    debit_code="1310",
                    credit_code="1320",
                    amount=amount,
                    cost_center_code="PROD",
                    commit=False,
                )
            return

        if p.waste_class == "normal":
            # Normal loss must remain in production cost. If the item had already been
            # capitalised as FG, return that cost to WIP so the replacement/good units
            # absorb it. Pending-QC normal scrap needs no journal because it is already WIP.
            if previous_status == ProductItemStatus.IN_STOCK:
                await self.accounting.auto_post(
                    user_id=p.checked_by,
                    description=f"بازگشت بهای ضایعات عادی واحد {item.id} به جریان ساخت",
                    source_type="qc_normal_scrap",
                    source_id=record_id,
                    source_ref=source_ref,
                    debit_code="1310",
                    credit_code="1320",
                    amount=amount,
                    cost_center_code="PROD",
                    commit=False,
                )
            return

        # Abnormal loss is excluded from the cost of healthy production and expensed.
        source_account = "1320" if previous_status == ProductItemStatus.IN_STOCK else "1310"
        await self.accounting.auto_post(
            user_id=p.checked_by,
            description=f"ضایعات غیرعادی واحد {item.id}",
            source_type="qc_abnormal_scrap",
            source_id=record_id,
            source_ref=source_ref,
            debit_code="5200",
            credit_code=source_account,
            amount=amount,
            cost_center_code="PROD",
            commit=False,
        )

    async def _update_production_order(
        self,
        *,
        order: ProductionOrder | None,
        item: ProductItem,
        p: QCRecordCreate,
        previous_status: ProductItemStatus,
    ) -> None:
        if order is None:
            return

        if p.result == QCRecordResult.PASSED:
            if previous_status != ProductItemStatus.IN_STOCK:
                order.qc_passed += 1
            if order.qc_passed >= order.quantity:
                order.status = "completed"
                order.completed_at = datetime.now(timezone.utc)
                tailor_work = await self.session.scalar(select(TailorWork).where(TailorWork.production_order_id == order.id))
                if tailor_work is not None:
                    tailor_work.delivered_good = max(tailor_work.delivered_good, tailor_work.quantity)
                    tailor_work.status = "completed"
                    tailor_work.completed_at = tailor_work.completed_at or date.today()
                # By this point every good physical unit has an immutable cost snapshot.
                # Sum those snapshots instead of recomputing historical unit costs.
                await self.session.flush()
                finished_cost = await self._passed_cost(order.id)
                order.total_cost_snapshot = finished_cost.quantize(MONEY, rounding=ROUND_HALF_UP)
                order.unit_cost_snapshot = (
                    finished_cost / Decimal(order.quantity)
                ).quantize(UNIT_COST, rounding=ROUND_HALF_UP)
            else:
                order.status = "waiting_qc"
            return

        if previous_status == ProductItemStatus.IN_STOCK and order.qc_passed > 0:
            order.qc_passed -= 1
        order.qc_failed += 1
        order.completed_at = None

        if p.failure_action == "scrap" and p.waste_class == "abnormal" and item.unit_cost_snapshot is not None:
            order.abnormal_scrap_cost = (
                Decimal(order.abnormal_scrap_cost) + Decimal(item.unit_cost_snapshot)
            ).quantize(MONEY, rounding=ROUND_HALF_UP)

        # Failed units require repair or replacement before the order can finish.
        order.status = "in_production"
        order.total_cost_snapshot = None
        order.unit_cost_snapshot = None
        tailor_work = await self.session.scalar(select(TailorWork).where(TailorWork.production_order_id == order.id))
        if tailor_work is not None and p.failure_action in {"rework", "scrap"}:
            # A failed piece is no longer part of the tailor's accepted-good delivery.
            # Rework or a replacement must be delivered before QC can receive another unit.
            if tailor_work.delivered_good > 0:
                tailor_work.delivered_good -= 1
            returned = 1 if p.failure_action == "rework" else 0
            damaged = 1 if p.failure_action == "scrap" else 0
            tailor_work.returned_for_fix += returned
            tailor_work.damaged += damaged
            tailor_work.status = "open"
            tailor_work.completed_at = None
            self.session.add(TailorWorkEvent(
                work_id=tailor_work.id,
                delivered_good=0,
                returned_for_fix=returned,
                damaged=damaged,
                notes=f"ثبت خودکار از QC واحد {item.warranty_serial or item.serial_number or item.id}",
                recorded_by=p.checked_by,
            ))

    async def record_qc(self, p: QCRecordCreate):
        item = await self.inv.get_item(p.item_id)
        if not item:
            raise QualityNotFoundError("Product item not found")
        if item.status not in {ProductItemStatus.PENDING_QC, ProductItemStatus.IN_STOCK}:
            raise QualityConflictError("QC is only allowed for pending-QC or in-stock items")

        now = datetime.now(timezone.utc)
        previous_status = item.status
        order = await self._locked_order(item)

        # Snapshot the cost at the true warehouse-entry gate. For an abnormal loss that
        # never entered stock, allocate the same current unit cost so it can be removed
        # from WIP and recognised separately as a period loss.
        if order is not None and previous_status != ProductItemStatus.IN_STOCK:
            if p.result == QCRecordResult.PASSED or (
                p.result == QCRecordResult.FAILED
                and p.failure_action == "scrap"
                and p.waste_class == "abnormal"
            ):
                item.unit_cost_snapshot = await self._allocate_pending_unit_cost(order)

        record = await self.repo.create_qc_record(**p.model_dump(), checked_at=now)
        item.qc_checked_by = p.checked_by
        item.qc_checked_at = now
        item.qc_notes = p.notes
        delta = 0
        movement_type = StockMovementType.QC_FAIL

        if p.result == QCRecordResult.PASSED:
            item.qc_status = QCStatus.PASSED
            movement_type = StockMovementType.QC_PASS
            if item.location_id is not None and item.warehouse_id is not None:
                if previous_status != ProductItemStatus.IN_STOCK:
                    delta = 1
                item.status = ProductItemStatus.IN_STOCK
        else:
            item.qc_status = QCStatus.FAILED
            if previous_status == ProductItemStatus.IN_STOCK:
                delta = -1
            item.status = ProductItemStatus.DAMAGED if p.failure_action == "scrap" else ProductItemStatus.PENDING_QC

        before = after = 0
        if item.location_id is not None and delta != 0:
            stock = await self.inv.get_stock(item.variant_id, item.location_id, for_update=True)
            if stock is None:
                stock = await self.inv.create_stock(item.variant_id, item.location_id)
            before = stock.quantity
            after = before + delta
            if after < 0:
                raise QualityConflictError("QC result would create invalid stock counters")
            stock.quantity = after
        elif item.location_id is not None:
            stock = await self.inv.get_stock(item.variant_id, item.location_id, for_update=True)
            if stock is not None:
                before = after = stock.quantity

        await self.inv.add_movement(
            item_id=item.id,
            variant_id=item.variant_id,
            location_id=item.location_id,
            type=movement_type,
            quantity=delta,
            qty_before=before,
            qty_after=after,
            reference_type="qc",
            reference_id=record.id,
            reason=p.notes,
            unit_cost_snapshot=item.unit_cost_snapshot,
            created_by=p.checked_by,
        )

        await self._post_cost_transfer(
            item=item,
            p=p,
            record_id=record.id,
            previous_status=previous_status,
        )
        await self._update_production_order(
            order=order,
            item=item,
            p=p,
            previous_status=previous_status,
        )

        # A reworked or normally scrapped finished unit returns its cost to WIP; the old
        # unit snapshot must not be reused as the next warehouse-entry cost.
        if (
            p.result == QCRecordResult.FAILED
            and previous_status == ProductItemStatus.IN_STOCK
            and (p.failure_action == "rework" or p.waste_class == "normal")
        ):
            item.unit_cost_snapshot = None

        await self.accounting.log_audit(
            user_id=p.checked_by,
            action="qc.record",
            entity_type="product_item",
            entity_id=item.id,
            source_ref=item.warranty_serial,
            after_data={
                "result": p.result.value,
                "failure_action": p.failure_action,
                "waste_class": p.waste_class,
                "unit_cost_snapshot": str(item.unit_cost_snapshot) if item.unit_cost_snapshot is not None else None,
            },
        )
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def log_label(self, p: LabelCreate):
        item = await self.inv.get_item(p.item_id)
        if not item:
            raise QualityNotFoundError("Product item not found")
        # QR labels are intentionally printable before QC so they can be attached
        # to newly produced units and scanned by the QC operator.
        label = await self.repo.create_label(**p.model_dump())
        if p.label_type == LabelType.QC:
            item.qc_label_printed = True
        elif p.label_type == LabelType.WARRANTY:
            item.warranty_label_printed = True
        await self.session.commit()
        await self.session.refresh(label)
        return label
