from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules.inventory_operations.constants import CycleCountLineStatus, CycleCountStatus, StockAdjustmentReason, StockAdjustmentType, StockTransferStatus

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class StockTransferCreate(BaseModel):
    transfer_number: str | None = Field(default=None, min_length=1, max_length=30)
    item_id: int | None = None
    variant_id: int
    from_location_id: int
    to_location_id: int
    quantity: int = Field(default=1, gt=0)
    requested_by: int | None = None
    notes: str | None = None

class StockTransferRead(ORMModel):
    id: int
    transfer_number: str
    item_id: int | None
    variant_id: int
    from_location_id: int
    to_location_id: int
    quantity: int
    status: StockTransferStatus
    requested_by: int | None = None
    approved_by: int | None
    completed_at: datetime | None
    notes: str | None
    created_at: datetime

class StockAdjustmentCreate(BaseModel):
    adjustment_number: str | None = Field(default=None, min_length=1, max_length=30)
    item_id: int | None = None
    variant_id: int
    location_id: int
    type: StockAdjustmentType
    quantity: int = Field(gt=0)
    reason: StockAdjustmentReason
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: int | None = None
    approved_by: int | None = None
    created_by: int | None = None

class StockAdjustmentRead(ORMModel):
    id: int
    adjustment_number: str
    item_id: int | None
    variant_id: int
    location_id: int
    type: StockAdjustmentType
    quantity: int
    reason: StockAdjustmentReason
    reference_type: str | None
    reference_id: int | None
    approved_by: int | None
    created_by: int | None = None
    created_at: datetime

class CycleCountCreate(BaseModel):
    count_number: str | None = Field(default=None, min_length=1, max_length=30)
    warehouse_id: int
    location_id: int | None = None
    created_by: int | None = None
    notes: str | None = None

class CycleCountRead(ORMModel):
    id: int
    count_number: str
    warehouse_id: int
    location_id: int | None
    status: CycleCountStatus
    started_at: datetime | None
    completed_at: datetime | None
    created_by: int | None = None
    notes: str | None

class CycleCountLineCreate(BaseModel):
    cycle_count_id: int
    item_id: int
    variant_id: int
    location_id: int
    system_qty: int = Field(ge=0)
    counted_qty: int = Field(ge=0)
    notes: str | None = None

class CycleCountLineRead(ORMModel):
    id: int
    cycle_count_id: int
    item_id: int
    variant_id: int
    location_id: int
    system_qty: int
    counted_qty: int
    difference: int
    status: CycleCountLineStatus
    notes: str | None

class StockOpeningCreate(BaseModel):
    variant_id: int
    location_id: int
    quantity: int = Field(ge=0)
    recorded_by: int | None = None

class StockOpeningRead(ORMModel):
    id: int
    variant_id: int
    location_id: int
    quantity: int
    recorded_at: datetime
    recorded_by: int | None = None
