from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WarrantyDailyCounter(Base):
    __tablename__ = "warranty_daily_counters"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WarrantySetting(Base):
    __tablename__ = "warranty_settings"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))
    qr_base_url: Mapped[str | None] = mapped_column(String(500))
    qr_destination_template: Mapped[str | None] = mapped_column(String(1000))
    grace_period_months: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default="6")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WarrantyRecord(Base):
    __tablename__ = "warranties"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_items.id", ondelete="CASCADE"), unique=True, index=True)
    serial: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="inactive", server_default="inactive", index=True)
    warranty_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12, server_default="12")
    customer_name: Mapped[str | None] = mapped_column(String(150))
    customer_phone: Mapped[str | None] = mapped_column(String(20))
    outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    auto_activate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    activation_source: Mapped[str | None] = mapped_column(String(20))
    qr_redirect_url: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
