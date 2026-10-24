from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.modules.inventory_operations.constants import (
    CycleCountLineStatus,
    CycleCountStatus,
    StockAdjustmentReason,
    StockAdjustmentType,
    StockTransferStatus,
)


class StockTransfer(Base):
    __tablename__ = "stock_transfers"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_transfers_quantity_positive"),
        CheckConstraint(
            "from_location_id <> to_location_id",
            name="ck_stock_transfers_locations_different",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transfer_number: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True, index=True
    )
    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("product_items.id", ondelete="SET NULL"), index=True
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    from_location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    to_location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    status: Mapped[StockTransferStatus] = mapped_column(
        Enum(
            StockTransferStatus,
            name="stock_transfer_status_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        default=StockTransferStatus.PENDING,
        server_default=StockTransferStatus.PENDING.value,
        index=True,
    )
    requested_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_adjustments_quantity_positive"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    adjustment_number: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True, index=True
    )
    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("product_items.id", ondelete="SET NULL"), index=True
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type: Mapped[StockAdjustmentType] = mapped_column(
        Enum(
            StockAdjustmentType,
            name="stock_adjustment_type_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[StockAdjustmentReason] = mapped_column(
        Enum(
            StockAdjustmentReason,
            name="stock_adjustment_reason_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        index=True,
    )
    reference_type: Mapped[str | None] = mapped_column(String(50), index=True)
    reference_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class CycleCount(Base):
    __tablename__ = "cycle_counts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    count_number: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True, index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[CycleCountStatus] = mapped_column(
        Enum(
            CycleCountStatus,
            name="cycle_count_status_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        default=CycleCountStatus.DRAFT,
        server_default=CycleCountStatus.DRAFT.value,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    lines: Mapped[list[CycleCountLine]] = relationship(
        back_populates="cycle_count", cascade="all, delete-orphan", passive_deletes=True
    )


class CycleCountLine(Base):
    __tablename__ = "cycle_count_lines"
    __table_args__ = (
        UniqueConstraint(
            "cycle_count_id", "item_id", name="uq_cycle_count_lines_count_item"
        ),
        CheckConstraint(
            "system_qty >= 0", name="ck_cycle_count_lines_system_qty_nonnegative"
        ),
        CheckConstraint(
            "counted_qty >= 0", name="ck_cycle_count_lines_counted_qty_nonnegative"
        ),
        CheckConstraint(
            "difference = counted_qty - system_qty",
            name="ck_cycle_count_lines_difference",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cycle_count_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cycle_counts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    system_qty: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    counted_qty: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    difference: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    status: Mapped[CycleCountLineStatus] = mapped_column(
        Enum(
            CycleCountLineStatus,
            name="cycle_count_line_status_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        default=CycleCountLineStatus.PENDING,
        server_default=CycleCountLineStatus.PENDING.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    cycle_count: Mapped[CycleCount] = relationship(back_populates="lines")


class StockOpening(Base):
    __tablename__ = "stock_openings"
    __table_args__ = (
        UniqueConstraint(
            "variant_id", "location_id", name="uq_stock_openings_variant_location"
        ),
        CheckConstraint("quantity >= 0", name="ck_stock_openings_quantity_nonnegative"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    recorded_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class DocumentCounter(Base):
    __tablename__ = "document_counters"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
