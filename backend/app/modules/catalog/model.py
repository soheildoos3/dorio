from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.catalog.constants import ProductStatus


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    parent: Mapped[Category | None] = relationship("Category", remote_side=[id], back_populates="children")
    children: Mapped[list[Category]] = relationship("Category", back_populates="parent")
    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    is_sellable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_manufacturable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    warranty_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12, server_default="12")
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status_enum", values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=ProductStatus.DRAFT, server_default=ProductStatus.DRAFT.value, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    category: Mapped[Category | None] = relationship(back_populates="products")
    variants: Mapped[list[ProductVariant]] = relationship(back_populates="product", cascade="all, delete-orphan", passive_deletes=True)
    media: Mapped[list[Media]] = relationship(back_populates="product", cascade="all, delete-orphan", passive_deletes=True)
    attribute_selections: Mapped[list[ProductAttribute]] = relationship(back_populates="product", cascade="all, delete-orphan", lazy="selectin")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    # Compatibility/cache field. Canonical attribute data is variant_attribute_values.
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    sale_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    product: Mapped[Product] = relationship(back_populates="variants")
    media: Mapped[list[Media]] = relationship(back_populates="variant", passive_deletes=True, lazy="selectin")
    attribute_values: Mapped[list[VariantAttributeValue]] = relationship(back_populates="variant", cascade="all, delete-orphan", lazy="selectin")


class Media(Base):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("product_variants.id", ondelete="SET NULL"), index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    product: Mapped[Product] = relationship(back_populates="media")
    variant: Mapped[ProductVariant | None] = relationship(back_populates="media")


Index(
    "uq_media_primary_product",
    Media.product_id,
    unique=True,
    postgresql_where=Media.is_primary.is_(True) & Media.variant_id.is_(None),
)
Index(
    "uq_media_primary_variant",
    Media.product_id,
    Media.variant_id,
    unique=True,
    postgresql_where=Media.is_primary.is_(True) & Media.variant_id.is_not(None),
)


class Attribute(Base):
    __tablename__ = "attributes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_variant_axis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    values: Mapped[list[AttributeValue]] = relationship(back_populates="attribute", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")


class AttributeValue(Base):
    __tablename__ = "attribute_values"
    __table_args__ = (UniqueConstraint("attribute_id", "value", name="uq_attribute_values_attribute_value"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attribute_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("attributes.id", ondelete="CASCADE"), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    attribute: Mapped[Attribute] = relationship(back_populates="values", lazy="joined")


class ProductAttribute(Base):
    __tablename__ = "product_attributes"
    __table_args__ = (UniqueConstraint("product_id", "attribute_id", name="uq_product_attribute"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("attributes.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    product: Mapped[Product] = relationship(back_populates="attribute_selections")
    attribute: Mapped[Attribute] = relationship(lazy="joined")
    values: Mapped[list[ProductAttributeValue]] = relationship(back_populates="product_attribute", cascade="all, delete-orphan", lazy="selectin")


class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_values"
    __table_args__ = (UniqueConstraint("product_attribute_id", "attribute_value_id", name="uq_product_attribute_value"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_attribute_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_attributes.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_value_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("attribute_values.id", ondelete="CASCADE"), nullable=False, index=True)
    product_attribute: Mapped[ProductAttribute] = relationship(back_populates="values")
    attribute_value: Mapped[AttributeValue] = relationship(lazy="joined")


class VariantAttributeValue(Base):
    __tablename__ = "variant_attribute_values"
    __table_args__ = (UniqueConstraint("variant_id", "attribute_value_id", name="uq_variant_attribute_value"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_value_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("attribute_values.id", ondelete="RESTRICT"), nullable=False, index=True)
    variant: Mapped[ProductVariant] = relationship(back_populates="attribute_values")
    attribute_value: Mapped[AttributeValue] = relationship(lazy="joined")
