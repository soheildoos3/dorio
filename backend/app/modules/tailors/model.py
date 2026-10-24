from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TailorWork(Base):
    __tablename__ = "tailor_works"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tailor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    product_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="SET NULL"))
    production_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("production_orders.id", ondelete="CASCADE"), unique=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    delivered_good: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    returned_for_fix: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damaged: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    assigned_at: Mapped[date] = mapped_column(Date, default=date.today)
    due_at: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tailor = relationship("User", foreign_keys=[tailor_user_id], lazy="joined")


class TailorWorkEvent(Base):
    __tablename__ = "tailor_work_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tailor_works.id", ondelete="CASCADE"), index=True)
    delivered_good: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    returned_for_fix: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damaged: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
