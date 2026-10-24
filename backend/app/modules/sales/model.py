from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SalesInvoice(Base):
    __tablename__ = "sales_invoices"
    __table_args__ = (UniqueConstraint("channel_id", "external_reference", name="uq_sales_invoice_channel_external"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sales_channels.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(150))
    customer_phone: Mapped[str | None] = mapped_column(String(30), index=True)
    external_reference: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft", index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    confirmed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    shipped_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    lines: Mapped[list["SalesInvoiceLine"]] = relationship(back_populates="invoice", lazy="selectin", cascade="all, delete-orphan")


class SalesInvoiceLine(Base):
    __tablename__ = "sales_invoice_lines"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    warranty_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("warranties.id", ondelete="SET NULL"), index=True)
    reservation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stock_reservations.id", ondelete="SET NULL"), unique=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    unit_list_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit_sale_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit_cost_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    invoice: Mapped[SalesInvoice] = relationship(back_populates="lines")


class SalesReturn(Base):
    __tablename__ = "sales_returns"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sales_invoices.id", ondelete="RESTRICT"), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255))
    total_refund: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    lines: Mapped[list["SalesReturnLine"]] = relationship(back_populates="sales_return", lazy="selectin", cascade="all, delete-orphan")


class SalesReturnLine(Base):
    __tablename__ = "sales_return_lines"
    __table_args__ = (UniqueConstraint("invoice_line_id", name="uq_sales_return_invoice_line"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sales_returns.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_line_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sales_invoice_lines.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit_cost_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    sales_return: Mapped[SalesReturn] = relationship(back_populates="lines")
