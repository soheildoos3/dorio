from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.modules.inventory.constants import OutboundDisposition, ProductItemStatus, QCStatus, StockMovementType, StockReservationStatus

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class ProductItemCreate(BaseModel):
    variant_id: int
    serial_number: str | None = Field(default=None, max_length=100)
    location_id: int | None = None
    warehouse_id: int | None = None
    received_at: datetime | None = None


class ProductItemBatchCreate(BaseModel):
    variant_id: int
    count: int = Field(default=1, ge=1, le=500)
    location_id: int | None = None
    warehouse_id: int | None = None
    received_at: datetime | None = None

class ProductItemUpdate(BaseModel):
    # Operational state/location are changed only by QC/transfer/outbound workflows.
    # This endpoint is intentionally limited to the optional human-entered identifier.
    serial_number: str | None = Field(default=None, max_length=100)

class ProductItemRead(ORMModel):
    id: int
    variant_id: int
    serial_number: str | None
    warranty_serial: str | None
    production_order_id: int | None
    unit_cost_snapshot: Decimal | None
    qc_status: QCStatus
    qc_checked_by: int | None
    qc_checked_at: datetime | None
    qc_notes: str | None
    qc_label_printed: bool
    warranty_label_printed: bool
    status: ProductItemStatus
    location_id: int | None
    warehouse_id: int | None
    received_at: datetime | None
    moved_out_at: datetime | None
    sold_at: datetime | None
    created_at: datetime

class StockRead(ORMModel):
    id: int
    variant_id: int
    location_id: int
    quantity: int
    reserved: int
    updated_at: datetime

class StockMovementCreate(BaseModel):
    item_id: int | None = None
    variant_id: int
    location_id: int | None = None
    type: StockMovementType
    quantity: int
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: int | None = None
    reason: str | None = Field(default=None, max_length=255)
    channel_id: int | None = None
    external_reference: str | None = Field(default=None, max_length=100)
    created_by: int | None = None

class StockMovementRead(ORMModel):
    id: int
    item_id: int | None
    variant_id: int
    location_id: int | None
    type: StockMovementType
    quantity: int
    qty_before: int
    qty_after: int
    reference_type: str | None
    reference_id: int | None
    reason: str | None
    channel_id: int | None
    external_reference: str | None
    unit_list_price: Decimal | None
    unit_sale_price: Decimal | None
    discount_total: Decimal | None
    line_total: Decimal | None
    unit_cost_snapshot: Decimal | None
    created_by: int | None
    created_at: datetime

class StockReservationCreate(BaseModel):
    item_id: int | None = None
    variant_id: int
    location_id: int
    reference_type: str = Field(min_length=1, max_length=50)
    reference_id: int | None = None
    reference_code: str | None = Field(default=None, max_length=100)
    quantity: int = Field(default=1, gt=0)
    expires_at: datetime | None = None
    created_by: int | None = None

class StockReservationRead(ORMModel):
    id: int
    item_id: int | None
    variant_id: int
    location_id: int
    reference_type: str
    reference_id: int | None
    reference_code: str | None
    quantity: int
    status: StockReservationStatus
    expires_at: datetime | None
    created_by: int | None
    created_at: datetime

class ProductDefaultLocationCreate(BaseModel):
    variant_id: int
    location_id: int
    priority: int = Field(default=1, gt=0)
    is_primary: bool = False

class ProductDefaultLocationUpdate(BaseModel):
    location_id: int | None = None
    priority: int | None = Field(default=None, gt=0)
    is_primary: bool | None = None

class ProductDefaultLocationRead(ORMModel):
    id: int
    variant_id: int
    location_id: int
    priority: int
    is_primary: bool


class StockOutboundCreate(BaseModel):
    variant_id: int
    location_id: int
    quantity: int = Field(default=1, gt=0)
    item_id: int | None = None
    reservation_id: int | None = None
    disposition: OutboundDisposition = OutboundDisposition.SALE
    reference_type: str = Field(default='outbound', min_length=1, max_length=50)
    reference_id: int | None = None
    reason: str | None = Field(default=None, max_length=255)
    channel_id: int | None = None
    external_reference: str | None = Field(default=None, max_length=100)
    created_by: int | None = None

    @model_validator(mode='after')
    def validate_serialized_outbound(self) -> 'StockOutboundCreate':
        if self.item_id is not None and self.quantity != 1:
            raise ValueError('Serialized item outbound quantity must be 1')
        if self.item_id is not None and self.disposition == OutboundDisposition.OTHER:
            raise ValueError('Serialized item requires a final disposition')
        return self

class SalesChannelSummary(BaseModel):
    channel_id: int | None
    channel_name: str
    quantity: int
    outbound_count: int
    gross_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal


class SalesSummary(BaseModel):
    quantity: int
    outbound_count: int
    gross_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    channels: list[SalesChannelSummary]
