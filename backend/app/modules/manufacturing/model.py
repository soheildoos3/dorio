from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, event, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Material(Base):
    __tablename__ = "materials"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    reorder_point: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    weighted_average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MaterialStock(Base):
    __tablename__ = "material_stock"
    __table_args__ = (
        UniqueConstraint("material_id", "location_id", name="uq_material_stock_material_location"),
        CheckConstraint("quantity >= 0", name="ck_material_stock_nonnegative"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    material: Mapped[Material] = relationship(lazy="joined")


class BOM(Base):
    __tablename__ = "boms"
    __table_args__ = (UniqueConstraint("product_id", "version", name="uq_bom_product_version"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft", index=True)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    items: Mapped[list["BOMItem"]] = relationship(back_populates="bom", lazy="selectin", cascade="all, delete-orphan")


class BOMItem(Base):
    __tablename__ = "bom_items"
    __table_args__ = (
        UniqueConstraint("bom_id", "material_id", name="uq_bom_item_material"),
        CheckConstraint("quantity_per_unit > 0", name="ck_bom_item_qty_positive"),
        CheckConstraint("normal_waste_percent >= 0", name="ck_bom_item_waste_nonnegative"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("boms.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    normal_waste_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("0"), server_default="0")
    bom: Mapped[BOM] = relationship(back_populates="items")
    material: Mapped[Material] = relationship(lazy="joined")


class ProductionOrder(Base):
    __tablename__ = "production_orders"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_production_order_quantity_positive"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("product_variants.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    tailor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    bom_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("boms.id", ondelete="RESTRICT"), nullable=False, index=True)
    fg_location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft", index=True)
    due_at: Mapped[date | None] = mapped_column(Date, index=True)
    material_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    overhead_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    abnormal_scrap_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    total_cost_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    unit_cost_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    prepared_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    qc_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    qc_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bom: Mapped[BOM] = relationship(lazy="joined")


class MaterialMovement(Base):
    __tablename__ = "material_movements"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_material_movement_quantity_positive"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    material_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    production_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("production_orders.id", ondelete="RESTRICT"), index=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), index=True)
    reference_ref: Mapped[str | None] = mapped_column(String(100), index=True)
    notes: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    material: Mapped[Material] = relationship(lazy="joined")


@event.listens_for(MaterialMovement, "before_update", propagate=True)
def _no_material_movement_update(*_: object) -> None:
    raise ValueError("material_movements is append-only")


@event.listens_for(MaterialMovement, "before_delete", propagate=True)
def _no_material_movement_delete(*_: object) -> None:
    raise ValueError("material_movements is append-only")


class LaborEntry(Base):
    __tablename__ = "labor_entries"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_labor_amount_nonnegative"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    production_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    tailor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today, index=True)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"), server_default="0")
    pieces: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    rate_basis: Mapped[str] = mapped_column(String(20), nullable=False, default="piece", server_default="piece")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending", index=True)
    notes: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OverheadRate(Base):
    __tablename__ = "overhead_rates"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    basis: Mapped[str] = mapped_column(String(30), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
