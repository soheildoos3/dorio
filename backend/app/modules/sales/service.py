from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.service import AccountingService
from app.modules.catalog.model import ProductVariant
from app.modules.channels.model import SalesChannel
from app.modules.inventory.constants import OutboundDisposition, ProductItemStatus, StockMovementType, StockReservationStatus
from app.modules.inventory.model import ProductItem, Stock, StockReservation
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import StockOutboundCreate, StockReservationCreate
from app.modules.inventory.service import InventoryConflictError, InventoryService
from app.modules.inventory_operations.numbers import next_document_number
from app.modules.sales.model import SalesInvoice, SalesInvoiceLine, SalesReturn, SalesReturnLine
from app.modules.sales.schemas import InvoiceCreate, SalesReturnCreate
from app.modules.warehouse.model import Location
from app.modules.warranty.service import WarrantyService


class SalesError(ValueError):
    pass


class SalesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.inventory = InventoryService(session)
        self.accounting = AccountingService(session)

    async def create_invoice(self, p: InvoiceCreate, user_id: int) -> SalesInvoice:
        channel = await self.session.get(SalesChannel, p.channel_id)
        if channel is None or not channel.is_active:
            raise SalesError("پلتفرم فروش معتبر یا فعال نیست")
        item_ids = [x.item_id for x in p.lines]
        if len(item_ids) != len(set(item_ids)):
            raise SalesError("یک واحد فیزیکی در فاکتور دوبار تکرار شده است")
        items = list((await self.session.scalars(select(ProductItem).where(ProductItem.id.in_(item_ids)))).all())
        item_map = {x.id: x for x in items}
        if len(item_map) != len(item_ids):
            raise SalesError("یکی از واحدهای فاکتور پیدا نشد")

        invoice = SalesInvoice(
            number=await next_document_number(self.session, "INV"),
            channel_id=p.channel_id,
            customer_name=(p.customer_name or "").strip() or None,
            customer_phone=(p.customer_phone or "").strip() or None,
            external_reference=(p.external_reference or "").strip() or None,
            notes=p.notes,
            status="draft",
            created_by=user_id,
            total_amount=Decimal("0"),
        )
        self.session.add(invoice)
        try:
            await self.session.flush()
            total = Decimal("0")
            warranty_service = WarrantyService(self.session)
            for line in p.lines:
                item = item_map[line.item_id]
                if item.status != ProductItemStatus.IN_STOCK or item.location_id is None:
                    raise SalesError(f"واحد {item.warranty_serial or item.id} در موجودی آزاد و قابل فروش نیست")
                list_price, sale_price = await self.inventory._resolve_sale_price(item.variant_id, p.channel_id, datetime.now(timezone.utc))
                warranty = await warranty_service.ensure_for_item(item)
                reservation = await self.inventory.reserve(
                    StockReservationCreate(
                        item_id=item.id, variant_id=item.variant_id, location_id=item.location_id,
                        reference_type="sales_invoice", reference_id=invoice.id, reference_code=invoice.number,
                        quantity=1, created_by=user_id,
                    ),
                    commit=False,
                )
                amount = Decimal(sale_price)
                total += amount
                self.session.add(SalesInvoiceLine(
                    invoice_id=invoice.id,
                    variant_id=item.variant_id,
                    item_id=item.id,
                    location_id=item.location_id,
                    warranty_id=warranty.id,
                    reservation_id=reservation.id,
                    quantity=1,
                    unit_list_price=list_price,
                    unit_sale_price=sale_price,
                    line_total=amount,
                    unit_cost_snapshot=None,
                ))
            invoice.total_amount = total
            await self.accounting.log_audit(user_id=user_id, action="sales.invoice.create", entity_type="sales_invoice", entity_id=invoice.id, source_ref=invoice.number, after_data={"channel_id": p.channel_id, "total": str(total), "external_reference": invoice.external_reference})
            await self.session.commit(); await self.session.refresh(invoice); return invoice
        except IntegrityError as exc:
            await self.session.rollback(); raise SalesError("مرجع سفارش این پلتفرم تکراری است") from exc
        except Exception:
            await self.session.rollback(); raise

    async def confirm(self, invoice_id: int, user_id: int) -> SalesInvoice:
        invoice = await self.session.scalar(select(SalesInvoice).where(SalesInvoice.id == invoice_id).with_for_update())
        if invoice is None: raise SalesError("فاکتور پیدا نشد")
        if invoice.status != "draft": raise SalesError("فقط فاکتور پیش‌نویس قابل تأیید است")
        if invoice.created_by == user_id:
            raise SalesError("ثبت‌کننده فاکتور نمی‌تواند همان فاکتور را تأیید کند")
        await self.session.refresh(invoice, ["lines"])
        # Re-check the invoice-owned reservation at the approval gate.
        for line in invoice.lines:
            item = await self.session.get(ProductItem, line.item_id)
            reservation = await self.session.get(StockReservation, line.reservation_id) if line.reservation_id else None
            if item is None or item.status != ProductItemStatus.RESERVED or reservation is None or reservation.status != StockReservationStatus.ACTIVE:
                raise SalesError(f"رزرو واحد خط {line.id} دیگر معتبر نیست")
            if reservation.reference_type != "sales_invoice" or reservation.reference_id != invoice.id:
                raise SalesError(f"رزرو واحد خط {line.id} متعلق به این فاکتور نیست")
        invoice.status = "confirmed"; invoice.confirmed_by = user_id; invoice.confirmed_at = datetime.now(timezone.utc)
        await self.accounting.log_audit(user_id=user_id, action="sales.invoice.confirm", entity_type="sales_invoice", entity_id=invoice.id, source_ref=invoice.number)
        await self.session.commit(); await self.session.refresh(invoice); return invoice

    async def ship(self, invoice_id: int, user_id: int) -> SalesInvoice:
        invoice = await self.session.scalar(select(SalesInvoice).where(SalesInvoice.id == invoice_id).with_for_update())
        if invoice is None: raise SalesError("فاکتور پیدا نشد")
        if invoice.status != "confirmed": raise SalesError("فقط فاکتور تأییدشده قابل ارسال است")
        if invoice.confirmed_by == user_id:
            # A third gate for larger-company segregation: confirmer is not warehouse releaser.
            raise SalesError("تأییدکننده فاکتور نمی‌تواند همان فاکتور را از انبار ارسال کند")
        await self.session.refresh(invoice, ["lines"])
        revenue = Decimal("0"); cogs = Decimal("0")
        warranty_service = WarrantyService(self.session)
        try:
            for line in invoice.lines:
                item = await self.session.scalar(select(ProductItem).where(ProductItem.id == line.item_id).with_for_update())
                if item is None or item.location_id is None:
                    raise SalesError(f"واحد خط {line.id} در انبار نیست")
                movement = await self.inventory.outbound(
                    StockOutboundCreate(
                        variant_id=line.variant_id,
                        location_id=item.location_id,
                        quantity=1,
                        item_id=item.id,
                        reservation_id=line.reservation_id,
                        disposition=OutboundDisposition.SALE,
                        reference_type="sales_invoice",
                        reference_id=invoice.id,
                        channel_id=invoice.channel_id,
                        external_reference=invoice.number,
                        created_by=user_id,
                    ),
                    commit=False,
                    unit_list_price_override=Decimal(line.unit_list_price),
                    unit_sale_price_override=Decimal(line.unit_sale_price),
                    skip_sale_accounting=True,
                )
                line.unit_cost_snapshot = movement.unit_cost_snapshot
                revenue += Decimal(line.line_total)
                if movement.unit_cost_snapshot is not None:
                    cogs += Decimal(movement.unit_cost_snapshot)
                warranty = await warranty_service.get_by_item(item.id, for_update=True)
                if warranty is not None:
                    warranty.customer_name = invoice.customer_name
                    warranty.customer_phone = invoice.customer_phone
            if revenue > 0:
                await self.accounting.auto_post(user_id=user_id, description=f"فروش فاکتور {invoice.number}", source_type="sales_invoice", source_id=invoice.id, source_ref=invoice.number, debit_code="1200", credit_code="4100", amount=revenue, cost_center_code="SALES", commit=False)
            if cogs > 0:
                await self.accounting.auto_post(user_id=user_id, description=f"بهای تمام‌شده فاکتور {invoice.number}", source_type="sales_invoice_cogs", source_id=invoice.id, source_ref=invoice.number, debit_code="5100", credit_code="1320", amount=cogs, cost_center_code="FG", commit=False)
            invoice.status="shipped"; invoice.shipped_by=user_id; invoice.shipped_at=datetime.now(timezone.utc)
            await self.accounting.log_audit(user_id=user_id, action="sales.invoice.ship", entity_type="sales_invoice", entity_id=invoice.id, source_ref=invoice.number, after_data={"revenue":str(revenue),"cogs":str(cogs)})
            await self.session.commit(); await self.session.refresh(invoice); return invoice
        except (InventoryConflictError, ValueError) as exc:
            await self.session.rollback(); raise SalesError(str(exc)) from exc
        except Exception:
            await self.session.rollback(); raise

    async def cancel(self, invoice_id: int, user_id: int) -> SalesInvoice:
        invoice = await self.session.scalar(select(SalesInvoice).where(SalesInvoice.id == invoice_id).with_for_update())
        if invoice is None: raise SalesError("فاکتور پیدا نشد")
        if invoice.status not in {"draft", "confirmed"}: raise SalesError("فاکتور ارسال‌شده فقط از مسیر برگشت از فروش قابل اصلاح است")
        await self.session.refresh(invoice, ["lines"])
        for line in invoice.lines:
            if line.reservation_id is None:
                continue
            reservation = await self.session.get(StockReservation, line.reservation_id)
            if reservation is not None and reservation.status == StockReservationStatus.ACTIVE:
                await self.inventory.release_reservation(line.reservation_id, created_by=user_id, commit=False)
        invoice.status="cancelled"
        await self.accounting.log_audit(user_id=user_id, action="sales.invoice.cancel", entity_type="sales_invoice", entity_id=invoice.id, source_ref=invoice.number)
        await self.session.commit(); await self.session.refresh(invoice); return invoice

    async def create_return(self, invoice_id: int, p: SalesReturnCreate, user_id: int) -> SalesReturn:
        invoice = await self.session.scalar(select(SalesInvoice).where(SalesInvoice.id == invoice_id).with_for_update())
        if invoice is None: raise SalesError("فاکتور پیدا نشد")
        if invoice.status not in {"shipped", "partially_returned"}: raise SalesError("فقط فاکتور ارسال‌شده قابل برگشت است")
        await self.session.refresh(invoice, ["lines"])
        line_map={x.id:x for x in invoice.lines}
        if len({x.invoice_line_id for x in p.lines}) != len(p.lines): raise SalesError("ردیف برگشت تکراری است")
        ret=SalesReturn(number=await next_document_number(self.session,"RET"),invoice_id=invoice.id,reason=p.reason,total_refund=Decimal("0"),created_by=user_id)
        self.session.add(ret); await self.session.flush()
        total_refund=Decimal("0"); total_cogs=Decimal("0")
        repo=InventoryRepository(self.session); warranty_service=WarrantyService(self.session)
        for req in p.lines:
            line=line_map.get(req.invoice_line_id)
            if line is None: raise SalesError("ردیف انتخاب‌شده متعلق به این فاکتور نیست")
            already=await self.session.scalar(select(SalesReturnLine.id).where(SalesReturnLine.invoice_line_id==line.id))
            if already is not None: raise SalesError(f"ردیف {line.id} قبلاً برگشت شده است")
            item=await self.session.scalar(select(ProductItem).where(ProductItem.id==line.item_id).with_for_update())
            if item is None or item.status != ProductItemStatus.SOLD: raise SalesError("واحد کالا در وضعیت فروخته‌شده نیست")
            location=await self.session.get(Location,req.location_id)
            if location is None or not location.is_active: raise SalesError("قفسه برگشت معتبر نیست")
            stock=await repo.get_stock(line.variant_id,req.location_id,for_update=True)
            if stock is None: stock=await repo.create_stock(line.variant_id,req.location_id)
            before=stock.quantity; stock.quantity+=1
            item.status=ProductItemStatus.IN_STOCK; item.location_id=req.location_id; item.warehouse_id=location.warehouse_id; item.moved_out_at=None; item.sold_at=None
            await repo.add_movement(
                item_id=item.id,
                variant_id=line.variant_id,
                location_id=req.location_id,
                type=StockMovementType.IN,
                quantity=1,
                qty_before=before,
                qty_after=stock.quantity,
                reference_type="sales_return",
                reference_id=ret.id,
                external_reference=ret.number,
                reason=p.reason or "sales_return",
                channel_id=invoice.channel_id,
                unit_list_price=line.unit_list_price,
                unit_sale_price=line.unit_sale_price,
                discount_total=-(Decimal(line.unit_list_price) - Decimal(line.unit_sale_price)),
                line_total=-Decimal(line.line_total),
                unit_cost_snapshot=line.unit_cost_snapshot,
                created_by=user_id,
            )
            warranty=await warranty_service.get_by_item(item.id,for_update=True)
            if warranty is not None: warranty.status="returned"
            cost=Decimal(line.unit_cost_snapshot or 0); refund=Decimal(line.line_total)
            self.session.add(SalesReturnLine(return_id=ret.id,invoice_line_id=line.id,item_id=item.id,location_id=req.location_id,refund_amount=refund,unit_cost_snapshot=cost))
            total_refund+=refund; total_cogs+=cost
        ret.total_refund=total_refund
        if total_refund>0:
            await self.accounting.auto_post(user_id=user_id,description=f"برگشت از فروش {ret.number}",source_type="sales_return",source_id=ret.id,source_ref=ret.number,debit_code="4100",credit_code="1200",amount=total_refund,cost_center_code="SALES",commit=False)
        if total_cogs>0:
            await self.accounting.auto_post(user_id=user_id,description=f"برگشت بهای تمام‌شده {ret.number}",source_type="sales_return_cogs",source_id=ret.id,source_ref=ret.number,debit_code="1320",credit_code="5100",amount=total_cogs,cost_center_code="FG",commit=False)
        # Flush return lines first, then count from the database.  The old implementation
        # added len(p.lines) after an autoflush and could mark a partial return as complete.
        await self.session.flush()
        returned_count = int(
            await self.session.scalar(
                select(func.count(SalesReturnLine.id))
                .join(SalesReturn, SalesReturn.id == SalesReturnLine.return_id)
                .where(SalesReturn.invoice_id == invoice.id)
            )
            or 0
        )
        invoice.status = "returned" if returned_count >= len(invoice.lines) else "partially_returned"
        await self.accounting.log_audit(user_id=user_id,action="sales.return",entity_type="sales_return",entity_id=ret.id,source_ref=ret.number,after_data={"invoice":invoice.number,"refund":str(total_refund),"cogs":str(total_cogs)})
        try:
            await self.session.commit(); await self.session.refresh(ret); return ret
        except IntegrityError as exc:
            await self.session.rollback(); raise SalesError("یکی از ردیف‌های انتخاب‌شده قبلاً برگشت شده است") from exc

    async def catalog_feed(self, channel_id: int):
        channel=await self.session.get(SalesChannel,channel_id)
        if channel is None or not channel.is_active: raise SalesError("کانال فروش معتبر نیست")
        variants=list((await self.session.scalars(select(ProductVariant).where(ProductVariant.is_active.is_(True)).order_by(ProductVariant.id))).all())
        rows=[]; now=datetime.now(timezone.utc)
        for variant in variants:
            available=int(await self.session.scalar(select(func.coalesce(func.sum(Stock.quantity),0)).where(Stock.variant_id==variant.id)) or 0)
            list_price,sale_price=await self.inventory._resolve_sale_price(variant.id,channel_id,now)
            rows.append({"variant_id":variant.id,"sku":variant.sku,"available_quantity":available,"list_price":list_price,"sale_price":sale_price})
        return rows
