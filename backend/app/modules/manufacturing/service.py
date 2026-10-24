from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.model import JournalEntry
from app.modules.accounting.service import AccountingService
from app.modules.catalog.model import Product, ProductVariant
from app.modules.inventory.constants import ProductItemStatus
from app.modules.inventory.model import ProductItem
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory_operations.numbers import next_document_number
from app.modules.manufacturing.model import BOM, BOMItem, LaborEntry, Material, MaterialMovement, MaterialStock, OverheadRate, ProductionOrder
from app.modules.manufacturing.schemas import BOMCreate, BOMUpdate, LaborCreate, LaborUpdate, MaterialAdjustment, MaterialIssue, MaterialPurchase, MaterialUpdate, OverheadRateCreate, OverheadRateUpdate, ProductionOrderCreate, ProductionOrderUpdate
from app.modules.tailors.model import TailorWork, TailorWorkEvent
from app.modules.user.model import User
from app.modules.warehouse.model import Location
from app.modules.warranty.serials import generate_warranty_serial
from app.modules.warranty.service import WarrantyService

MONEY = Decimal("0.01")
QTY = Decimal("0.0001")


class ManufacturingError(ValueError):
    pass


class ManufacturingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.accounting = AccountingService(session)

    async def _material(self, material_id: int, *, for_update: bool = False) -> Material:
        q = select(Material).where(Material.id == material_id)
        if for_update:
            q = q.with_for_update()
        obj = await self.session.scalar(q)
        if not obj:
            raise ManufacturingError("ماده اولیه پیدا نشد")
        return obj

    async def _location(self, location_id: int) -> Location:
        obj = await self.session.get(Location, location_id)
        if not obj or not obj.is_active:
            raise ManufacturingError("مکان انبار معتبر یا فعال نیست")
        return obj

    async def _stock(self, material_id: int, location_id: int, *, create: bool = False) -> MaterialStock | None:
        row = await self.session.scalar(select(MaterialStock).where(MaterialStock.material_id == material_id, MaterialStock.location_id == location_id).with_for_update(of=MaterialStock))
        if row is None and create:
            row = MaterialStock(material_id=material_id, location_id=location_id, quantity=Decimal("0"))
            self.session.add(row); await self.session.flush()
        return row

    async def _global_qty(self, material_id: int) -> Decimal:
        value = await self.session.scalar(select(func.coalesce(func.sum(MaterialStock.quantity), 0)).where(MaterialStock.material_id == material_id))
        return Decimal(value or 0)

    async def _linked_tailor_work_no(self, order: ProductionOrder) -> str:
        """Return a unique work number without stealing an unrelated manual work number."""
        preferred = order.order_no[:50]
        existing = await self.session.scalar(
            select(TailorWork.id).where(TailorWork.work_no == preferred).limit(1)
        )
        if existing is None:
            return preferred

        # A legacy/manual tailor work may already use the production order number.
        # Keep that historical row intact and give the linked system work a reserved id.
        base = f"SYS-PO-{order.id}"
        candidate = base[:50]
        suffix = 1
        while await self.session.scalar(
            select(TailorWork.id).where(TailorWork.work_no == candidate).limit(1)
        ) is not None:
            marker = f"-{suffix}"
            candidate = f"{base[:50-len(marker)]}{marker}"
            suffix += 1
        return candidate

    async def _sync_tailor_work(self, order: ProductionOrder) -> TailorWork | None:
        work = await self.session.scalar(select(TailorWork).where(TailorWork.production_order_id == order.id))
        if order.tailor_user_id is None:
            if work is not None:
                has_events = await self.session.scalar(select(TailorWorkEvent.id).where(TailorWorkEvent.work_id == work.id).limit(1))
                if has_events is None:
                    await self.session.delete(work)
                    return None
                work.status = "cancelled"
                work.completed_at = None
            return work
        if work is None:
            work = TailorWork(
                tailor_user_id=order.tailor_user_id,
                work_no=await self._linked_tailor_work_no(order),
                product_id=order.product_id,
                production_order_id=order.id,
                quantity=order.quantity,
                due_at=order.due_at,
                notes=order.notes,
            )
            self.session.add(work)
            await self.session.flush()
        else:
            if order.quantity < work.delivered_good:
                raise ManufacturingError("تعداد دستور از تعداد سالم تحویل‌شده خیاط کمتر نمی‌تواند باشد")
            work.tailor_user_id = order.tailor_user_id
            work.product_id = order.product_id
            work.quantity = order.quantity
            work.due_at = order.due_at
            work.notes = order.notes
        if order.status == "cancelled":
            work.status = "cancelled"
            work.completed_at = None
        elif order.status == "completed":
            work.delivered_good = max(work.delivered_good, work.quantity)
            work.status = "completed"
            work.completed_at = work.completed_at or date.today()
        elif work.delivered_good >= work.quantity:
            work.status = "completed"
            work.completed_at = work.completed_at or date.today()
        else:
            work.status = "open"
            work.completed_at = None
        return work

    async def create_material(self, data, user_id: int) -> Material:
        obj = Material(**data.model_dump()); self.session.add(obj)
        try:
            await self.session.flush()
            await self.accounting.log_audit(user_id=user_id, action="material.create", entity_type="material", entity_id=obj.id, source_ref=obj.code, after_data=data.model_dump(mode="json"))
            await self.session.commit(); await self.session.refresh(obj); return obj
        except IntegrityError as exc:
            await self.session.rollback(); raise ManufacturingError("کد ماده اولیه تکراری است") from exc

    async def update_material(self, material_id: int, data: MaterialUpdate, user_id: int) -> Material:
        obj = await self._material(material_id)
        before = {"name": obj.name, "unit": obj.unit, "category": obj.category, "reorder_point": str(obj.reorder_point), "is_active": obj.is_active}
        values = data.model_dump(exclude_unset=True)
        for key, value in values.items():
            setattr(obj, key, value)
        await self.accounting.log_audit(user_id=user_id, action="material.update", entity_type="material", entity_id=obj.id, source_ref=obj.code, before_data=before, after_data=data.model_dump(mode="json", exclude_unset=True))
        await self.session.commit(); await self.session.refresh(obj); return obj

    async def delete_material(self, material_id: int, user_id: int) -> None:
        obj = await self._material(material_id)
        stock_qty = await self._global_qty(material_id)
        movement = await self.session.scalar(select(MaterialMovement.id).where(MaterialMovement.material_id == material_id).limit(1))
        bom_item = await self.session.scalar(select(BOMItem.id).where(BOMItem.material_id == material_id).limit(1))
        if stock_qty != 0 or movement is not None or bom_item is not None:
            raise ManufacturingError("این ماده سابقه یا موجودی دارد و قابل حذف نیست؛ آن را غیرفعال کنید")
        await self.accounting.log_audit(user_id=user_id, action="material.delete", entity_type="material", entity_id=obj.id, source_ref=obj.code, before_data={"name":obj.name})
        await self.session.delete(obj); await self.session.commit()

    async def purchase(self, p: MaterialPurchase, user_id: int) -> MaterialMovement:
        material = await self._material(p.material_id, for_update=True); await self._location(p.location_id)
        stock = await self._stock(p.material_id, p.location_id, create=True)
        old_global_qty = await self._global_qty(p.material_id)
        purchase_total = (Decimal(p.quantity) * Decimal(p.unit_cost) + Decimal(p.freight_cost)).quantize(MONEY, rounding=ROUND_HALF_UP)
        effective_unit = (purchase_total / Decimal(p.quantity)).quantize(QTY, rounding=ROUND_HALF_UP)
        old_value = old_global_qty * Decimal(material.weighted_average_cost)
        new_qty = old_global_qty + Decimal(p.quantity)
        material.weighted_average_cost = ((old_value + purchase_total) / new_qty).quantize(QTY, rounding=ROUND_HALF_UP) if new_qty > 0 else Decimal("0")
        stock.quantity = Decimal(stock.quantity) + Decimal(p.quantity)
        number = await next_document_number(self.session, "MAT")
        movement = MaterialMovement(number=number, material_id=p.material_id, location_id=p.location_id, movement_type="purchase", quantity=p.quantity, unit_cost=effective_unit, total_cost=purchase_total, reference_type="purchase", reference_ref=p.reference_ref, notes=p.notes, created_by=user_id)
        self.session.add(movement); await self.session.flush()
        await self.accounting.auto_post(user_id=user_id, description=f"خرید مواد اولیه {material.name}", source_type="material_purchase", source_id=movement.id, source_ref=movement.number, debit_code="1300", credit_code=p.offset_account_code, amount=purchase_total, cost_center_code="RAW", commit=False)
        await self.accounting.log_audit(user_id=user_id, action="material.purchase", entity_type="material_movement", entity_id=movement.id, source_ref=movement.number, after_data={"material_id": p.material_id, "qty": str(p.quantity), "unit_cost": str(effective_unit), "average_cost": str(material.weighted_average_cost)})
        await self.session.commit(); await self.session.refresh(movement); return movement

    async def _issue_or_return(self, p: MaterialIssue, user_id: int, *, is_return: bool) -> MaterialMovement:
        material = await self._material(p.material_id, for_update=True); await self._location(p.location_id)
        order = await self.session.get(ProductionOrder, p.production_order_id)
        if not order:
            raise ManufacturingError("دستور تولید پیدا نشد")
        if order.status in {"completed", "cancelled"}:
            raise ManufacturingError("برای دستور بسته‌شده گردش مواد مجاز نیست")
        stock = await self._stock(p.material_id, p.location_id, create=is_return)
        if stock is None:
            raise ManufacturingError("برای این ماده در قفس انتخاب‌شده موجودی وجود ندارد")
        qty = Decimal(p.quantity)
        if is_return:
            # Return at the actual weighted cost that is still outstanding on this order,
            # not at today's material WAC. This prevents purchases after the issue from
            # changing the historic production cost.
            issued_qty = Decimal(await self.session.scalar(
                select(func.coalesce(func.sum(MaterialMovement.quantity), 0)).where(
                    MaterialMovement.production_order_id == order.id,
                    MaterialMovement.material_id == p.material_id,
                    MaterialMovement.movement_type == "issue_to_production",
                )
            ) or 0)
            returned_qty = Decimal(await self.session.scalar(
                select(func.coalesce(func.sum(MaterialMovement.quantity), 0)).where(
                    MaterialMovement.production_order_id == order.id,
                    MaterialMovement.material_id == p.material_id,
                    MaterialMovement.movement_type == "return_from_production",
                )
            ) or 0)
            issued_value = Decimal(await self.session.scalar(
                select(func.coalesce(func.sum(MaterialMovement.total_cost), 0)).where(
                    MaterialMovement.production_order_id == order.id,
                    MaterialMovement.material_id == p.material_id,
                    MaterialMovement.movement_type == "issue_to_production",
                )
            ) or 0)
            returned_value = Decimal(await self.session.scalar(
                select(func.coalesce(func.sum(MaterialMovement.total_cost), 0)).where(
                    MaterialMovement.production_order_id == order.id,
                    MaterialMovement.material_id == p.material_id,
                    MaterialMovement.movement_type == "return_from_production",
                )
            ) or 0)
            outstanding_qty = issued_qty - returned_qty
            outstanding_value = issued_value - returned_value
            if outstanding_qty <= 0 or qty > outstanding_qty:
                raise ManufacturingError("مقدار برگشت از مقدار خالص حواله‌شده به این دستور بیشتر است")
            unit = (outstanding_value / outstanding_qty).quantize(QTY, rounding=ROUND_HALF_UP)
            total = (qty * unit).quantize(MONEY, rounding=ROUND_HALF_UP)

            old_global_qty = await self._global_qty(p.material_id)
            old_global_value = old_global_qty * Decimal(material.weighted_average_cost)
            stock.quantity = Decimal(stock.quantity) + qty
            new_global_qty = old_global_qty + qty
            if new_global_qty > 0:
                material.weighted_average_cost = ((old_global_value + total) / new_global_qty).quantize(QTY, rounding=ROUND_HALF_UP)
            order.material_cost = max(Decimal(order.material_cost) - total, Decimal("0"))
            debit_code, credit_code, movement_type = "1300", "1310", "return_from_production"
        else:
            unit = Decimal(material.weighted_average_cost)
            total = (qty * unit).quantize(MONEY, rounding=ROUND_HALF_UP)
            if Decimal(stock.quantity) < qty:
                raise ManufacturingError(f"موجودی ماده «{material.name}» در این قفس کافی نیست")
            stock.quantity = Decimal(stock.quantity) - qty
            order.material_cost = Decimal(order.material_cost) + total
            debit_code, credit_code, movement_type = "1310", "1300", "issue_to_production"
            if order.status == "draft":
                order.status = "materials_issued"
        number = await next_document_number(self.session, "MAT")
        movement = MaterialMovement(number=number, material_id=p.material_id, location_id=p.location_id, movement_type=movement_type, quantity=qty, unit_cost=unit, total_cost=total, production_order_id=order.id, reference_type="production_order", reference_ref=order.order_no, notes=p.notes, created_by=user_id)
        self.session.add(movement); await self.session.flush()
        await self.accounting.auto_post(user_id=user_id, description=("برگشت مواد از تولید" if is_return else "حواله مواد به تولید") + f" - {material.name}", source_type=movement_type, source_id=movement.id, source_ref=order.order_no, debit_code=debit_code, credit_code=credit_code, amount=total, cost_center_code="PROD", commit=False)
        await self.accounting.log_audit(user_id=user_id, action=f"material.{movement_type}", entity_type="material_movement", entity_id=movement.id, source_ref=movement.number, after_data={"order": order.order_no, "qty": str(qty), "cost": str(total)})
        return movement

    async def issue(self, p: MaterialIssue, user_id: int, *, commit: bool = True) -> MaterialMovement:
        obj = await self._issue_or_return(p, user_id, is_return=False)
        if commit: await self.session.commit(); await self.session.refresh(obj)
        return obj

    async def return_material(self, p: MaterialIssue, user_id: int) -> MaterialMovement:
        obj = await self._issue_or_return(p, user_id, is_return=True)
        await self.session.commit(); await self.session.refresh(obj); return obj

    async def adjust(self, p: MaterialAdjustment, user_id: int) -> MaterialMovement:
        material = await self._material(p.material_id); await self._location(p.location_id)
        stock = await self._stock(p.material_id, p.location_id, create=p.direction == "increase")
        if stock is None: raise ManufacturingError("موجودی این ماده در قفس وجود ندارد")
        qty = Decimal(p.quantity); unit = Decimal(material.weighted_average_cost); total = (qty * unit).quantize(MONEY, rounding=ROUND_HALF_UP)
        if p.direction == "decrease":
            if Decimal(stock.quantity) < qty: raise ManufacturingError("تعدیل باعث موجودی منفی می‌شود")
            stock.quantity = Decimal(stock.quantity) - qty; debit_code, credit_code = p.offset_account_code, "1300"
        else:
            stock.quantity = Decimal(stock.quantity) + qty; debit_code, credit_code = "1300", p.offset_account_code
        number = await next_document_number(self.session, "MAT")
        obj = MaterialMovement(number=number, material_id=p.material_id, location_id=p.location_id, movement_type=f"adjust_{p.direction}", quantity=qty, unit_cost=unit, total_cost=total, reference_type="adjustment", notes=p.notes, created_by=user_id)
        self.session.add(obj); await self.session.flush()
        await self.accounting.auto_post(user_id=user_id, description=f"تعدیل موجودی مواد - {material.name}", source_type="material_adjustment", source_id=obj.id, source_ref=obj.number, debit_code=debit_code, credit_code=credit_code, amount=total, cost_center_code="RAW", commit=False)
        await self.accounting.log_audit(user_id=user_id, action="material.adjust", entity_type="material_movement", entity_id=obj.id, source_ref=obj.number, after_data={"direction": p.direction, "qty": str(qty)})
        await self.session.commit(); await self.session.refresh(obj); return obj

    async def create_bom(self, p: BOMCreate, user_id: int) -> BOM:
        product = await self.session.get(Product, p.product_id)
        if not product: raise ManufacturingError("محصول پیدا نشد")
        material_ids = {x.material_id for x in p.items}
        found = {x.id for x in (await self.session.scalars(select(Material).where(Material.id.in_(material_ids)))).all()}
        if found != material_ids: raise ManufacturingError("یکی از مواد BOM معتبر نیست")
        bom = BOM(product_id=p.product_id, version=p.version, status=p.status, effective_from=p.effective_from, effective_to=p.effective_to, notes=p.notes, created_by=user_id)
        self.session.add(bom)
        try:
            await self.session.flush()
            for item in p.items: self.session.add(BOMItem(bom_id=bom.id, **item.model_dump()))
            if p.status == "active":
                rows = list((await self.session.scalars(select(BOM).where(BOM.product_id == p.product_id, BOM.id != bom.id, BOM.status == "active"))).all())
                for row in rows: row.status = "retired"
            await self.accounting.log_audit(user_id=user_id, action="bom.create", entity_type="bom", entity_id=bom.id, source_ref=f"{p.product_id}/v{p.version}", after_data=p.model_dump(mode="json"))
            await self.session.commit(); await self.session.refresh(bom); return bom
        except IntegrityError as exc:
            await self.session.rollback(); raise ManufacturingError("نسخه BOM برای این محصول تکراری است") from exc

    async def update_bom(self, bom_id: int, p: BOMUpdate, user_id: int) -> BOM:
        bom = await self.session.get(BOM, bom_id)
        if not bom: raise ManufacturingError("BOM پیدا نشد")
        used = await self.session.scalar(select(ProductionOrder.id).where(ProductionOrder.bom_id == bom.id).limit(1))
        values = p.model_dump(exclude_unset=True)
        if used is not None and "items" in values:
            raise ManufacturingError("مواد BOM استفاده‌شده قابل تغییر نیستند؛ نسخه جدید بسازید")
        items = values.pop("items", None)
        if items is not None:
            material_ids = {x.material_id for x in items}
            found = {x.id for x in (await self.session.scalars(select(Material).where(Material.id.in_(material_ids)))).all()}
            if found != material_ids: raise ManufacturingError("یکی از مواد BOM معتبر نیست")
            bom.items.clear()
            for item in items: bom.items.append(BOMItem(**item.model_dump()))
        for key, value in values.items(): setattr(bom,key,value)
        if bom.status == "active":
            rows = list((await self.session.scalars(select(BOM).where(BOM.product_id == bom.product_id, BOM.id != bom.id, BOM.status == "active"))).all())
            for row in rows: row.status = "retired"
        await self.accounting.log_audit(user_id=user_id, action="bom.update", entity_type="bom", entity_id=bom.id, source_ref=f"{bom.product_id}/v{bom.version}", after_data=p.model_dump(mode="json", exclude_unset=True))
        await self.session.commit(); await self.session.refresh(bom); return bom

    async def delete_bom(self, bom_id: int, user_id: int) -> None:
        bom = await self.session.get(BOM, bom_id)
        if not bom: raise ManufacturingError("BOM پیدا نشد")
        used = await self.session.scalar(select(ProductionOrder.id).where(ProductionOrder.bom_id == bom.id).limit(1))
        if used is not None: raise ManufacturingError("این BOM در دستور تولید استفاده شده و قابل حذف نیست؛ آن را بازنشسته کنید")
        await self.accounting.log_audit(user_id=user_id, action="bom.delete", entity_type="bom", entity_id=bom.id, source_ref=f"{bom.product_id}/v{bom.version}")
        await self.session.delete(bom); await self.session.commit()

    async def create_order(self, p: ProductionOrderCreate, user_id: int) -> ProductionOrder:
        product = await self.session.get(Product, p.product_id); bom = await self.session.get(BOM, p.bom_id)
        if not product: raise ManufacturingError("محصول پیدا نشد")
        if not bom or bom.product_id != p.product_id: raise ManufacturingError("BOM با محصول دستور تولید تطابق ندارد")
        if bom.status != "active": raise ManufacturingError("برای دستور تولید باید یک نسخه فعال BOM انتخاب شود")
        if p.variant_id is not None:
            variant = await self.session.get(ProductVariant, p.variant_id)
            if not variant or variant.product_id != p.product_id: raise ManufacturingError("تنوع با محصول تطابق ندارد")
        if p.tailor_user_id is not None:
            tailor = await self.session.get(User, p.tailor_user_id)
            if not tailor or tailor.user_type != "tailor" or tailor.status != "active": raise ManufacturingError("خیاط انتخاب‌شده معتبر یا فعال نیست")
        if p.fg_location_id is not None: await self._location(p.fg_location_id)
        order = ProductionOrder(order_no=await next_document_number(self.session, "PO"), **p.model_dump(), created_by=user_id)
        self.session.add(order); await self.session.flush()
        await self._sync_tailor_work(order)
        await self.accounting.log_audit(user_id=user_id, action="production.create", entity_type="production_order", entity_id=order.id, source_ref=order.order_no, after_data=p.model_dump(mode="json"))
        await self.session.commit(); await self.session.refresh(order); return order

    async def update_order(self, order_id: int, p: ProductionOrderUpdate, user_id: int) -> ProductionOrder:
        order = await self.session.get(ProductionOrder, order_id)
        if not order: raise ManufacturingError("دستور تولید پیدا نشد")
        if order.status in {"completed", "cancelled"}: raise ManufacturingError("دستور بسته‌شده قابل ویرایش نیست")
        values = p.model_dump(exclude_unset=True)
        structural = {"product_id", "variant_id", "quantity", "bom_id"}
        if order.status != "draft" and structural.intersection(values):
            raise ManufacturingError("محصول، تنوع، تعداد و BOM فقط تا قبل از حواله مواد قابل ویرایش‌اند")
        product_id = values.get("product_id", order.product_id)
        bom_id = values.get("bom_id", order.bom_id)
        bom = await self.session.get(BOM, bom_id)
        if not bom or bom.product_id != product_id or bom.status not in {"active", "draft"}:
            raise ManufacturingError("BOM انتخاب‌شده با محصول معتبر نیست")
        variant_id = values.get("variant_id", order.variant_id)
        if variant_id is not None:
            variant = await self.session.get(ProductVariant, variant_id)
            if not variant or variant.product_id != product_id: raise ManufacturingError("تنوع با محصول تطابق ندارد")
        if "tailor_user_id" in values and values["tailor_user_id"] != order.tailor_user_id:
            linked_work = await self.session.scalar(select(TailorWork).where(TailorWork.production_order_id == order.id))
            if linked_work is not None:
                has_event = await self.session.scalar(select(TailorWorkEvent.id).where(TailorWorkEvent.work_id == linked_work.id).limit(1))
                if has_event is not None or linked_work.delivered_good or linked_work.returned_for_fix or linked_work.damaged:
                    raise ManufacturingError("بعد از ثبت تحویل یا نتیجه QC، خیاط این دستور قابل تغییر نیست؛ برای مانده کار دستور جدید بسازید")
            if values["tailor_user_id"] is not None:
                tailor = await self.session.get(User, values["tailor_user_id"])
                if not tailor or tailor.user_type != "tailor" or tailor.status != "active": raise ManufacturingError("خیاط انتخاب‌شده معتبر یا فعال نیست")
        if "fg_location_id" in values and values["fg_location_id"] is not None:
            if order.prepared_units > 0: raise ManufacturingError("بعد از ساخت واحدهای فیزیکی، قفس مقصد را از عملیات انبار مدیریت کنید")
            await self._location(values["fg_location_id"])
        if "quantity" in values and values["quantity"] < max(order.prepared_units, order.qc_passed):
            raise ManufacturingError("تعداد دستور از واحدهای ساخته‌شده یا تأییدشده کمتر نمی‌تواند باشد")
        before = {k:getattr(order,k) for k in values}
        for key, value in values.items(): setattr(order, key, value)
        await self._sync_tailor_work(order)
        await self.accounting.log_audit(user_id=user_id, action="production.update", entity_type="production_order", entity_id=order.id, source_ref=order.order_no, before_data={k:(str(v) if v is not None else None) for k,v in before.items()}, after_data=p.model_dump(mode="json", exclude_unset=True))
        await self.session.commit(); await self.session.refresh(order); return order

    async def delete_order(self, order_id: int, user_id: int) -> None:
        order = await self.session.get(ProductionOrder, order_id)
        if not order: raise ManufacturingError("دستور تولید پیدا نشد")
        if order.status != "draft": raise ManufacturingError("فقط دستور پیش‌نویس قابل حذف است؛ دستور شروع‌شده را لغو کنید")
        movement = await self.session.scalar(select(MaterialMovement.id).where(MaterialMovement.production_order_id == order.id).limit(1))
        labor = await self.session.scalar(select(LaborEntry.id).where(LaborEntry.production_order_id == order.id).limit(1))
        item = await self.session.scalar(select(ProductItem.id).where(ProductItem.production_order_id == order.id).limit(1))
        linked_work = await self.session.scalar(select(TailorWork).where(TailorWork.production_order_id == order.id))
        event = None if linked_work is None else await self.session.scalar(select(TailorWorkEvent.id).where(TailorWorkEvent.work_id == linked_work.id).limit(1))
        if movement is not None or labor is not None or item is not None or event is not None:
            raise ManufacturingError("این دستور سابقه عملیاتی دارد و برای حفظ تاریخچه قابل حذف نیست")
        await self.accounting.log_audit(user_id=user_id, action="production.delete", entity_type="production_order", entity_id=order.id, source_ref=order.order_no, before_data={"status":order.status,"quantity":order.quantity})
        await self.session.delete(order); await self.session.commit()

    async def issue_bom(self, order_id: int, location_id: int, user_id: int) -> ProductionOrder:
        order = await self.session.get(ProductionOrder, order_id)
        if not order: raise ManufacturingError("دستور تولید پیدا نشد")
        if order.status != "draft": raise ManufacturingError("BOM این دستور قبلاً حواله شده یا تولید شروع شده است")
        bom = await self.session.get(BOM, order.bom_id); await self.session.refresh(bom, ["items"])
        # Lock and pre-check every stock row before mutating any of them.
        requirements=[]
        for item in bom.items:
            qty=(Decimal(item.quantity_per_unit)*Decimal(order.quantity)*(Decimal("1")+Decimal(item.normal_waste_percent)/Decimal("100"))).quantize(QTY, rounding=ROUND_HALF_UP)
            stock=await self._stock(item.material_id, location_id)
            if stock is None or Decimal(stock.quantity)<qty:
                raise ManufacturingError(f"موجودی ماده «{item.material.name}» برای حواله BOM کافی نیست")
            requirements.append((item,qty))
        for item,qty in requirements:
            await self.issue(MaterialIssue(material_id=item.material_id, location_id=location_id, quantity=qty, production_order_id=order.id, notes=f"مصرف BOM v{bom.version}"), user_id, commit=False)
        order.status="materials_issued"
        await self.accounting.log_audit(user_id=user_id, action="production.issue_bom", entity_type="production_order", entity_id=order.id, source_ref=order.order_no, after_data={"location_id": location_id, "material_cost": str(order.material_cost)})
        await self.session.commit(); await self.session.refresh(order); return order

    async def update_status(self, order_id: int, status: str, user_id: int) -> ProductionOrder:
        order=await self.session.get(ProductionOrder,order_id)
        if not order: raise ManufacturingError("دستور تولید پیدا نشد")
        allowed={
            "draft":{"materials_issued","cancelled"},
            "materials_issued":{"in_production","cancelled"},
            "in_production":{"waiting_qc","cancelled"},
            "waiting_qc":{"completed","rejected","in_production"},
            "rejected":{"in_production","cancelled"},
            "completed":set(),"cancelled":set(),
        }
        if status!=order.status and status not in allowed.get(order.status,set()): raise ManufacturingError(f"تغییر وضعیت از {order.status} به {status} مجاز نیست")
        if status == "completed" and order.qc_passed < order.quantity:
            raise ManufacturingError("تکمیل دستور فقط بعد از تأیید QC همه واحدهای سالم انجام می‌شود")
        before=order.status; order.status=status; now=datetime.now(timezone.utc)
        if status=="in_production" and order.started_at is None: order.started_at=now
        if status=="completed": order.completed_at=now
        await self._sync_tailor_work(order)
        await self.accounting.log_audit(user_id=user_id, action="production.status", entity_type="production_order", entity_id=order.id, source_ref=order.order_no, before_data={"status":before}, after_data={"status":status})
        await self.session.commit(); await self.session.refresh(order); return order

    async def create_labor(self, p: LaborCreate, user_id: int) -> LaborEntry:
        order=await self.session.get(ProductionOrder,p.production_order_id)
        if not order: raise ManufacturingError("دستور تولید پیدا نشد")
        if order.status not in {"in_production", "waiting_qc", "rejected"}: raise ManufacturingError("کارکرد خیاط فقط بعد از شروع تولید و قبل از بسته‌شدن دستور قابل ثبت است")
        tailor=await self.session.get(User,p.tailor_user_id)
        if not tailor or tailor.user_type!="tailor" or tailor.status!="active": raise ManufacturingError("خیاط معتبر یا فعال نیست")
        if order.tailor_user_id is not None and order.tailor_user_id != p.tailor_user_id:
            raise ManufacturingError("کارکرد این دستور فقط برای خیاط تعیین‌شده در خود دستور قابل ثبت است")
        basis=Decimal(p.pieces) if p.rate_basis=="piece" else Decimal(p.hours)
        amount=Decimal(p.amount) if p.amount is not None else (basis*Decimal(p.rate)).quantize(MONEY,rounding=ROUND_HALF_UP)
        entry=LaborEntry(production_order_id=p.production_order_id,tailor_user_id=p.tailor_user_id,work_date=p.work_date,hours=p.hours,pieces=p.pieces,rate=p.rate,rate_basis=p.rate_basis,amount=amount,notes=p.notes,status="pending",created_by=user_id)
        self.session.add(entry);await self.session.flush();await self.accounting.log_audit(user_id=user_id,action="labor.create",entity_type="labor_entry",entity_id=entry.id,source_ref=order.order_no,after_data={"amount":str(amount),"tailor_user_id":p.tailor_user_id});await self.session.commit();await self.session.refresh(entry);return entry

    async def update_labor(self, labor_id: int, p: LaborUpdate, user_id: int) -> LaborEntry:
        entry = await self.session.get(LaborEntry, labor_id)
        if not entry: raise ManufacturingError("کارکرد پیدا نشد")
        if entry.status != "pending": raise ManufacturingError("فقط کارکرد در انتظار تأیید قابل ویرایش است")
        values = p.model_dump(exclude_unset=True)
        order=await self.session.get(ProductionOrder,entry.production_order_id)
        if not order or order.status not in {"in_production", "waiting_qc", "rejected"}: raise ManufacturingError("ویرایش کارکرد فقط برای دستور در جریان تولید مجاز است")
        if "tailor_user_id" in values:
            tailor = await self.session.get(User, values["tailor_user_id"])
            if not tailor or tailor.user_type != "tailor" or tailor.status != "active": raise ManufacturingError("خیاط معتبر نیست")
            if order.tailor_user_id is not None and order.tailor_user_id != values["tailor_user_id"]:
                raise ManufacturingError("خیاط کارکرد باید با خیاط تعیین‌شده در دستور تولید یکسان باشد")
        for key,value in values.items(): setattr(entry,key,value)
        basis=Decimal(entry.pieces) if entry.rate_basis=="piece" else Decimal(entry.hours)
        if basis <= 0: raise ManufacturingError("مبنای کارکرد باید بیشتر از صفر باشد")
        entry.amount=(basis*Decimal(entry.rate)).quantize(MONEY,rounding=ROUND_HALF_UP)
        await self.accounting.log_audit(user_id=user_id,action="labor.update",entity_type="labor_entry",entity_id=entry.id,source_ref=order.order_no if order else None,after_data={"amount":str(entry.amount)})
        await self.session.commit();await self.session.refresh(entry);return entry

    async def delete_labor(self, labor_id: int, user_id: int) -> None:
        entry=await self.session.get(LaborEntry,labor_id)
        if not entry: raise ManufacturingError("کارکرد پیدا نشد")
        if entry.status!="pending": raise ManufacturingError("کارکرد تأییدشده بخشی از حسابداری است و قابل حذف نیست")
        order=await self.session.get(ProductionOrder,entry.production_order_id)
        await self.accounting.log_audit(user_id=user_id,action="labor.delete",entity_type="labor_entry",entity_id=entry.id,source_ref=order.order_no if order else None,before_data={"amount":str(entry.amount)})
        await self.session.delete(entry);await self.session.commit()

    async def approve_labor(self, labor_id:int, approver_id:int)->LaborEntry:
        entry=await self.session.get(LaborEntry,labor_id)
        if not entry: raise ManufacturingError("کارکرد پیدا نشد")
        if entry.status!="pending": raise ManufacturingError("این کارکرد قبلاً تعیین تکلیف شده است")
        if entry.created_by==approver_id: raise ManufacturingError("ثبت‌کننده کارکرد نمی‌تواند همان کارکرد را تأیید کند")
        tailor=await self.session.get(User,entry.tailor_user_id); order=await self.session.get(ProductionOrder,entry.production_order_id)
        if order is None or order.status not in {"in_production", "waiting_qc", "rejected"}: raise ManufacturingError("تأیید کارکرد فقط برای دستور در جریان تولید مجاز است")
        if tailor is None or tailor.user_type != "tailor": raise ManufacturingError("خیاط کارکرد معتبر نیست")
        if order.tailor_user_id is not None and order.tailor_user_id != entry.tailor_user_id:
            raise ManufacturingError("خیاط کارکرد با خیاط تعیین‌شده در دستور تولید یکسان نیست؛ ابتدا کارکرد در انتظار را اصلاح کنید")
        payable=await self.accounting.tailor_payable(tailor.id,tailor.full_name)
        wip=await self.accounting.account_by_code("1310"); center=await self.accounting.cost_center_by_code("PROD")
        from app.modules.accounting.schemas import JournalCreate, JournalLineCreate
        await self.accounting.post(JournalCreate(description=f"تأیید دستمزد مستقیم {tailor.full_name}",source_type="labor_entry",source_id=entry.id,source_ref=order.order_no,lines=[JournalLineCreate(account_id=wip.id,cost_center_id=center.id if center else None,debit=entry.amount),JournalLineCreate(account_id=payable.id,cost_center_id=center.id if center else None,credit=entry.amount)]),approver_id,commit=False)
        entry.status="approved";entry.approved_by=approver_id;entry.approved_at=datetime.now(timezone.utc);order.labor_cost=Decimal(order.labor_cost)+Decimal(entry.amount)
        await self.accounting.log_audit(user_id=approver_id,action="labor.approve",entity_type="labor_entry",entity_id=entry.id,source_ref=order.order_no,after_data={"amount":str(entry.amount)})
        await self.session.commit();await self.session.refresh(entry);return entry

    async def create_overhead_rate(self,p:OverheadRateCreate,user_id:int)->OverheadRate:
        obj=OverheadRate(**p.model_dump(),created_by=user_id);self.session.add(obj);await self.session.flush();await self.accounting.log_audit(user_id=user_id,action="overhead_rate.create",entity_type="overhead_rate",entity_id=obj.id,after_data=p.model_dump(mode="json"));await self.session.commit();await self.session.refresh(obj);return obj

    async def update_overhead_rate(self,rate_id:int,p:OverheadRateUpdate,user_id:int)->OverheadRate:
        obj=await self.session.get(OverheadRate,rate_id)
        if not obj: raise ManufacturingError("نرخ سربار پیدا نشد")
        used=await self.session.scalar(select(JournalEntry.id).where(JournalEntry.source_type=="overhead_absorption",JournalEntry.source_ref.like(f"%:OH-{rate_id}")).limit(1))
        values=p.model_dump(exclude_unset=True)
        if used is not None and {"basis","rate","effective_from"}.intersection(values):
            raise ManufacturingError("نرخ استفاده‌شده را نمی‌توان از نظر مبلغ یا مبنا تغییر داد؛ آن را غیرفعال و نرخ جدید بسازید")
        for key,value in values.items():setattr(obj,key,value)
        await self.accounting.log_audit(user_id=user_id,action="overhead_rate.update",entity_type="overhead_rate",entity_id=obj.id,after_data=p.model_dump(mode="json",exclude_unset=True));await self.session.commit();await self.session.refresh(obj);return obj

    async def delete_overhead_rate(self,rate_id:int,user_id:int)->None:
        obj=await self.session.get(OverheadRate,rate_id)
        if not obj: raise ManufacturingError("نرخ سربار پیدا نشد")
        used=await self.session.scalar(select(JournalEntry.id).where(JournalEntry.source_type=="overhead_absorption",JournalEntry.source_ref.like(f"%:OH-{rate_id}")).limit(1))
        if used is not None: raise ManufacturingError("این نرخ استفاده شده و قابل حذف نیست؛ آن را غیرفعال کنید")
        await self.accounting.log_audit(user_id=user_id,action="overhead_rate.delete",entity_type="overhead_rate",entity_id=obj.id,before_data={"name":obj.name,"rate":str(obj.rate)});await self.session.delete(obj);await self.session.commit()

    async def absorb_overhead(self,order_id:int,rate_id:int,user_id:int)->ProductionOrder:
        order=await self.session.get(ProductionOrder,order_id);rate=await self.session.get(OverheadRate,rate_id)
        if not order or not rate or not rate.is_active: raise ManufacturingError("دستور تولید یا نرخ سربار معتبر نیست")
        if rate.basis=="piece": basis=Decimal(order.quantity)
        else:
            hours=await self.session.scalar(select(func.coalesce(func.sum(LaborEntry.hours),0)).where(LaborEntry.production_order_id==order.id,LaborEntry.status=="approved"));basis=Decimal(hours or 0)
        amount=(basis*Decimal(rate.rate)).quantize(MONEY,rounding=ROUND_HALF_UP)
        if amount<=0: raise ManufacturingError("مبنای جذب سربار صفر است")
        absorption_ref=f"{order.order_no}:OH-{rate.id}"
        duplicate=await self.session.scalar(select(JournalEntry.id).where(JournalEntry.source_type=="overhead_absorption",JournalEntry.source_ref==absorption_ref))
        if duplicate is not None: raise ManufacturingError("این نرخ سربار قبلاً برای این دستور جذب شده است")
        await self.accounting.auto_post(user_id=user_id,description=f"جذب سربار دستور {order.order_no}",source_type="overhead_absorption",source_id=order.id,source_ref=absorption_ref,debit_code="1310",credit_code="5310",amount=amount,cost_center_code="PROD",commit=False)
        order.overhead_cost=Decimal(order.overhead_cost)+amount;await self.accounting.log_audit(user_id=user_id,action="overhead.absorb",entity_type="production_order",entity_id=order.id,source_ref=order.order_no,after_data={"rate_id":rate_id,"amount":str(amount)});await self.session.commit();await self.session.refresh(order);return order

    async def prepare_qc(self,order_id:int,location_id:int|None,user_id:int)->ProductionOrder:
        order=await self.session.get(ProductionOrder,order_id)
        if not order: raise ManufacturingError("دستور تولید پیدا نشد")
        if order.status not in {"in_production","waiting_qc"}: raise ManufacturingError("دستور باید در حال تولید یا در انتظار QC باشد")
        if order.variant_id is None: raise ManufacturingError("برای ساخت واحد فیزیکی، تنوع محصول باید در دستور تولید مشخص باشد")
        target_location=location_id or order.fg_location_id
        if target_location is None: raise ManufacturingError("قفس مقصد محصول نهایی مشخص نشده است")
        loc=await self._location(target_location)
        pending_count=int(await self.session.scalar(select(func.count(ProductItem.id)).where(
            ProductItem.production_order_id==order.id,
            ProductItem.status==ProductItemStatus.PENDING_QC,
        )) or 0)
        tailor_work = await self._sync_tailor_work(order) if order.tailor_user_id is not None else None
        available_for_qc = min(order.quantity, tailor_work.delivered_good) if tailor_work is not None else order.quantity
        needed=available_for_qc-order.qc_passed-pending_count
        if needed<=0:
            if tailor_work is not None and available_for_qc < order.quantity:
                raise ManufacturingError("تحویل سالم جدیدی از خیاط برای ارسال به QC وجود ندارد")
            raise ManufacturingError("به تعداد تحویل‌شده، واحد در انتظار QC یا تأییدشده وجود دارد")
        # Cost is deliberately NOT frozen here. The item becomes a physical unit and receives
        # a warranty/QR now, but its cost snapshot is locked only at QC pass / warehouse entry.
        order.fg_location_id=target_location
        repo=InventoryRepository(self.session); warranty=WarrantyService(self.session)
        for _ in range(needed):
            item=await repo.create_item(variant_id=order.variant_id,serial_number=None,warranty_serial=await generate_warranty_serial(self.session),location_id=target_location,warehouse_id=loc.warehouse_id,production_order_id=order.id,unit_cost_snapshot=None)
            await warranty.ensure_for_item(item)
        order.prepared_units+=needed;order.status="waiting_qc"
        await self.accounting.log_audit(user_id=user_id,action="production.prepare_qc",entity_type="production_order",entity_id=order.id,source_ref=order.order_no,after_data={"prepared_units":order.prepared_units,"new_pending_units":needed})
        await self.session.commit();await self.session.refresh(order);return order
