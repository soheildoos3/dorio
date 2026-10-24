from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.constants import ProductStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    parent_id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    parent_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryRead(ORMModel):
    id: int; parent_id: int | None; name: str; path: str; level: int; sort_order: int; is_active: bool; created_at: datetime


class ProductCreate(BaseModel):
    sku: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category_id: int | None = None
    is_sellable: bool = True
    is_manufacturable: bool = False
    warranty_months: int = Field(default=12, ge=1, le=120)
    status: ProductStatus = ProductStatus.DRAFT


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category_id: int | None = None
    is_sellable: bool | None = None
    is_manufacturable: bool | None = None
    warranty_months: int | None = Field(default=None, ge=1, le=120)
    status: ProductStatus | None = None


class ProductRead(ORMModel):
    id: int; sku: str | None; name: str; description: str | None; category_id: int | None
    is_sellable: bool; is_manufacturable: bool; warranty_months: int; status: ProductStatus
    created_at: datetime; updated_at: datetime; deleted_at: datetime | None


class AttributeValueRead(ORMModel):
    id: int; attribute_id: int; value: str; sort_order: int


class AttributeRead(ORMModel):
    id: int; code: str; name: str; is_variant_axis: bool; sort_order: int
    values: list[AttributeValueRead] = Field(default_factory=list)


class VariantAttributeRead(BaseModel):
    attribute_id: int
    attribute_code: str
    attribute_name: str
    value_id: int
    value: str


class ProductVariantCreate(BaseModel):
    product_id: int
    sku: str | None = Field(default=None, max_length=50)
    attribute_value_ids: list[int] = Field(default_factory=list)
    sale_price: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True


class ProductVariantUpdate(BaseModel):
    sku: str | None = Field(default=None, max_length=50)
    attribute_value_ids: list[int] | None = None
    sale_price: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductVariantRead(ORMModel):
    id: int; product_id: int; sku: str | None; attributes: dict; sale_price: Decimal; is_active: bool; created_at: datetime
    resolved_attributes: list[VariantAttributeRead] = Field(default_factory=list)


class MediaCreate(BaseModel):
    product_id: int; variant_id: int | None = None; url: str; is_primary: bool = False; sort_order: int = 0


class MediaUpdate(BaseModel):
    variant_id: int | None = None; is_primary: bool | None = None; sort_order: int | None = None


class MediaRead(ORMModel):
    id: int; product_id: int; variant_id: int | None; url: str; is_primary: bool; sort_order: int; created_at: datetime


class AttributeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=100)
    is_variant_axis: bool = False
    sort_order: int = 0


class AttributeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_variant_axis: bool | None = None
    sort_order: int | None = None


class AttributeValueCreate(BaseModel):
    attribute_id: int; value: str = Field(min_length=1, max_length=100); sort_order: int = 0


class AttributeValueUpdate(BaseModel):
    value: str | None = Field(default=None, min_length=1, max_length=100); sort_order: int | None = None


class ProductAttributeSelectionInput(BaseModel):
    attribute_id: int
    value_ids: list[int] = Field(default_factory=list)
    sort_order: int = 0


class ProductAttributesUpdate(BaseModel):
    selections: list[ProductAttributeSelectionInput] = Field(default_factory=list)


class ProductAttributeSelectionRead(BaseModel):
    id: int
    attribute: AttributeRead
    values: list[AttributeValueRead]
    sort_order: int


class GenerateVariantsRequest(BaseModel):
    default_price: Decimal = Field(default=Decimal("0"), ge=0)
    keep_existing: bool = True


class ProductDetail(ProductRead):
    category: CategoryRead | None = None
    variants: list[ProductVariantRead] = Field(default_factory=list)
    media: list[MediaRead] = Field(default_factory=list)
    attribute_config: list[ProductAttributeSelectionRead] = Field(default_factory=list)
