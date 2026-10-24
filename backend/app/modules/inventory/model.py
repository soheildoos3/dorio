from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, Index, Numeric, String, Text, UniqueConstraint, event, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.modules.inventory.constants import ProductItemStatus, QCStatus, StockMovementType, StockReservationStatus

class ProductItem(Base):
    __tablename__ = 'product_items'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product_variants.id', ondelete='RESTRICT'), nullable=False, index=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    warranty_serial: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    production_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('production_orders.id', ondelete='SET NULL'), index=True)
    unit_cost_snapshot: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    qc_status: Mapped[QCStatus] = mapped_column(Enum(QCStatus, name='qc_status_enum', values_callable=lambda e: [x.value for x in e]), nullable=False, default=QCStatus.PENDING, server_default=QCStatus.PENDING.value, index=True)
    qc_checked_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), index=True)
    qc_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    qc_notes: Mapped[str | None] = mapped_column(Text)
    qc_label_printed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    warranty_label_printed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    status: Mapped[ProductItemStatus] = mapped_column(Enum(ProductItemStatus, name='product_item_status_enum', values_callable=lambda e: [x.value for x in e]), nullable=False, default=ProductItemStatus.PENDING_QC, server_default=ProductItemStatus.PENDING_QC.value, index=True)
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('locations.id', ondelete='SET NULL'), index=True)
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('warehouses.id', ondelete='SET NULL'), index=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moved_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class Stock(Base):
    __tablename__ = 'stock'
    __table_args__ = (UniqueConstraint('variant_id', 'location_id', name='uq_stock_variant_location'), CheckConstraint('quantity >= 0', name='ck_stock_quantity_nonnegative'), CheckConstraint('reserved >= 0', name='ck_stock_reserved_nonnegative'))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product_variants.id', ondelete='CASCADE'), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class StockMovement(Base):
    __tablename__ = 'stock_movements'
    __table_args__ = (CheckConstraint('qty_after = qty_before + quantity', name='ck_stock_movements_balance'),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('product_items.id', ondelete='SET NULL'), index=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product_variants.id', ondelete='RESTRICT'), nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('locations.id', ondelete='SET NULL'), index=True)
    type: Mapped[StockMovementType] = mapped_column(Enum(StockMovementType, name='stock_movement_type_enum', values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_before: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50), index=True)
    reference_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    reason: Mapped[str | None] = mapped_column(String(255))
    channel_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('sales_channels.id', ondelete='SET NULL'), index=True)
    external_reference: Mapped[str | None] = mapped_column(String(100), index=True)
    unit_list_price: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    unit_sale_price: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    discount_total: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    line_total: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True, index=True)
    unit_cost_snapshot: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

@event.listens_for(StockMovement, 'before_update', propagate=True)
def _prevent_stock_movement_update(*_: object) -> None:
    raise ValueError('stock_movements is append-only; UPDATE is forbidden')

@event.listens_for(StockMovement, 'before_delete', propagate=True)
def _prevent_stock_movement_delete(*_: object) -> None:
    raise ValueError('stock_movements is append-only; DELETE is forbidden')

class StockReservation(Base):
    __tablename__ = 'stock_reservations'
    __table_args__ = (CheckConstraint('quantity > 0', name='ck_stock_reservations_quantity_positive'), CheckConstraint('item_id IS NULL OR quantity = 1', name='ck_stock_reservations_serialized_quantity'))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('product_items.id', ondelete='SET NULL'), index=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product_variants.id', ondelete='RESTRICT'), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('locations.id', ondelete='RESTRICT'), nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    reference_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default='1')
    status: Mapped[StockReservationStatus] = mapped_column(Enum(StockReservationStatus, name='stock_reservation_status_enum', values_callable=lambda e: [x.value for x in e]), nullable=False, default=StockReservationStatus.ACTIVE, server_default=StockReservationStatus.ACTIVE.value, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class ProductDefaultLocation(Base):
    __tablename__ = 'product_default_locations'
    __table_args__ = (UniqueConstraint('variant_id', 'location_id', name='uq_product_default_locations_variant_location'), UniqueConstraint('variant_id', 'priority', name='uq_product_default_locations_variant_priority'), CheckConstraint('priority > 0', name='ck_product_default_locations_priority_positive'))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product_variants.id', ondelete='CASCADE'), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default='1')
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
Index('uq_product_default_locations_primary', ProductDefaultLocation.variant_id, unique=True, postgresql_where=ProductDefaultLocation.is_primary.is_(True))
