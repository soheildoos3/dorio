from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InvoiceLineCreate(BaseModel):
    item_id: int


class InvoiceCreate(BaseModel):
    channel_id: int
    customer_name: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=30)
    external_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    lines: list[InvoiceLineCreate] = Field(min_length=1, max_length=200)


class InvoiceLineRead(ORM):
    id: int
    invoice_id: int
    variant_id: int
    item_id: int
    location_id: int
    warranty_id: int | None
    reservation_id: int | None
    quantity: int
    unit_list_price: Decimal
    unit_sale_price: Decimal
    line_total: Decimal
    unit_cost_snapshot: Decimal | None


class InvoiceRead(ORM):
    id: int
    number: str
    channel_id: int
    customer_name: str | None
    customer_phone: str | None
    external_reference: str | None
    status: str
    total_amount: Decimal
    created_by: int
    confirmed_by: int | None
    shipped_by: int | None
    created_at: datetime
    confirmed_at: datetime | None
    shipped_at: datetime | None
    notes: str | None
    lines: list[InvoiceLineRead]


class SalesReturnLineCreate(BaseModel):
    invoice_line_id: int
    location_id: int


class SalesReturnCreate(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
    lines: list[SalesReturnLineCreate] = Field(min_length=1, max_length=200)


class SalesReturnLineRead(ORM):
    id: int
    return_id: int
    invoice_line_id: int
    item_id: int
    location_id: int
    refund_amount: Decimal
    unit_cost_snapshot: Decimal


class SalesReturnRead(ORM):
    id: int
    number: str
    invoice_id: int
    reason: str | None
    total_refund: Decimal
    created_by: int
    created_at: datetime
    lines: list[SalesReturnLineRead]


class CatalogFeedRow(BaseModel):
    variant_id: int
    sku: str | None
    available_quantity: int
    list_price: Decimal
    sale_price: Decimal
