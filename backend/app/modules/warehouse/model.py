from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.modules.warehouse.constants import LocationType


class Warehouse(Base):
    __tablename__ = "warehouses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    manager_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    locations: Mapped[list[Location]] = relationship(
        back_populates="warehouse", cascade="all, delete-orphan", passive_deletes=True
    )


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_locations_warehouse_code"),
        CheckConstraint("level >= 0", name="ck_locations_level_nonnegative"),
        CheckConstraint(
            "max_items IS NULL OR max_items >= 0",
            name="ck_locations_max_items_nonnegative",
        ),
        CheckConstraint(
            "max_weight_kg IS NULL OR max_weight_kg >= 0",
            name="ck_locations_max_weight_nonnegative",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[LocationType] = mapped_column(
        Enum(
            LocationType,
            name="location_type_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    path: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_pickable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_receivable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    max_items: Mapped[int | None] = mapped_column(Integer)
    max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    warehouse: Mapped[Warehouse] = relationship(back_populates="locations")
    parent: Mapped[Location | None] = relationship(
        "Location", remote_side=[id], back_populates="children"
    )
    children: Mapped[list[Location]] = relationship("Location", back_populates="parent")
