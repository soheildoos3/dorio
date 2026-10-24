from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MaterialCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    unit: str = Field(min_length=1, max_length=30)
    category: str | None = Field(default=None, max_length=80)
    reorder_point: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    category: str | None = Field(default=None, max_length=80)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class MaterialRead(ORM):
    id: int
    code: str
    name: str
    unit: str
    category: str | None
    reorder_point: Decimal
    weighted_average_cost: Decimal
    is_active: bool
    created_at: datetime


class MaterialStockRead(ORM):
    id: int
    material_id: int
    location_id: int
    quantity: Decimal
    updated_at: datetime
    material: MaterialRead


class MaterialPurchase(BaseModel):
    material_id: int
    location_id: int
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    freight_cost: Decimal = Field(default=Decimal("0"), ge=0)
    offset_account_code: str = Field(default="2100", max_length=50)
    reference_ref: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=255)


class MaterialIssue(BaseModel):
    material_id: int
    location_id: int
    quantity: Decimal = Field(gt=0)
    production_order_id: int
    notes: str | None = Field(default=None, max_length=255)


class MaterialAdjustment(BaseModel):
    material_id: int
    location_id: int
    quantity: Decimal = Field(gt=0)
    direction: Literal["increase", "decrease"]
    offset_account_code: str = Field(default="5200", max_length=50)
    notes: str | None = Field(default=None, max_length=255)


class MaterialMovementRead(ORM):
    id: int
    number: str
    material_id: int
    location_id: int
    movement_type: str
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    production_order_id: int | None
    reference_type: str | None
    reference_ref: str | None
    notes: str | None
    created_by: int
    created_at: datetime
    material: MaterialRead


class BOMItemCreate(BaseModel):
    material_id: int
    quantity_per_unit: Decimal = Field(gt=0)
    normal_waste_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class BOMCreate(BaseModel):
    product_id: int
    version: int = Field(ge=1)
    status: Literal["draft", "active", "retired"] = "draft"
    effective_from: date | None = None
    effective_to: date | None = None
    notes: str | None = None
    items: list[BOMItemCreate] = Field(min_length=1)


class BOMUpdate(BaseModel):
    status: Literal["draft", "active", "retired"] | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    notes: str | None = None
    items: list[BOMItemCreate] | None = None


class BOMItemRead(ORM):
    id: int
    material_id: int
    quantity_per_unit: Decimal
    normal_waste_percent: Decimal
    material: MaterialRead


class BOMRead(ORM):
    id: int
    product_id: int
    version: int
    status: str
    effective_from: date | None
    effective_to: date | None
    notes: str | None
    created_by: int
    created_at: datetime
    items: list[BOMItemRead]


class ProductionOrderCreate(BaseModel):
    product_id: int
    variant_id: int | None = None
    quantity: int = Field(gt=0, le=100000)
    tailor_user_id: int | None = None
    bom_id: int
    fg_location_id: int | None = None
    due_at: date | None = None
    notes: str | None = None


class ProductionOrderUpdate(BaseModel):
    product_id: int | None = None
    variant_id: int | None = None
    quantity: int | None = Field(default=None, gt=0, le=100000)
    tailor_user_id: int | None = None
    bom_id: int | None = None
    fg_location_id: int | None = None
    due_at: date | None = None
    notes: str | None = None


class ProductionStatusUpdate(BaseModel):
    status: Literal["draft", "materials_issued", "in_production", "waiting_qc", "completed", "rejected", "cancelled"]


class ProductionOrderRead(ORM):
    id: int
    order_no: str
    product_id: int
    variant_id: int | None
    quantity: int
    tailor_user_id: int | None
    bom_id: int
    fg_location_id: int | None
    status: str
    due_at: date | None
    material_cost: Decimal
    labor_cost: Decimal
    overhead_cost: Decimal
    abnormal_scrap_cost: Decimal
    total_cost_snapshot: Decimal | None
    unit_cost_snapshot: Decimal | None
    prepared_units: int
    qc_passed: int
    qc_failed: int
    notes: str | None
    created_by: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class IssueBOMRequest(BaseModel):
    location_id: int


class LaborCreate(BaseModel):
    production_order_id: int
    tailor_user_id: int
    work_date: date = Field(default_factory=date.today)
    hours: Decimal = Field(default=Decimal("0"), ge=0)
    pieces: int = Field(default=0, ge=0)
    rate: Decimal = Field(ge=0)
    rate_basis: Literal["hour", "piece"] = "piece"
    amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_basis(self):
        if self.hours <= 0 and self.pieces <= 0:
            raise ValueError("ساعت کار یا تعداد قطعه باید بیشتر از صفر باشد")
        return self


class LaborUpdate(BaseModel):
    tailor_user_id: int | None = None
    work_date: date | None = None
    hours: Decimal | None = Field(default=None, ge=0)
    pieces: int | None = Field(default=None, ge=0)
    rate: Decimal | None = Field(default=None, ge=0)
    rate_basis: Literal["hour", "piece"] | None = None
    notes: str | None = Field(default=None, max_length=255)


class LaborRead(ORM):
    id: int
    production_order_id: int
    tailor_user_id: int
    work_date: date
    hours: Decimal
    pieces: int
    rate: Decimal
    rate_basis: str
    amount: Decimal
    status: str
    notes: str | None
    created_by: int
    approved_by: int | None
    approved_at: datetime | None
    created_at: datetime


class OverheadRateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    basis: Literal["piece", "direct_labor_hour"]
    rate: Decimal = Field(ge=0)
    effective_from: date = Field(default_factory=date.today)
    effective_to: date | None = None
    is_active: bool = True


class OverheadRateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    basis: Literal["piece", "direct_labor_hour"] | None = None
    rate: Decimal | None = Field(default=None, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class OverheadRateRead(ORM):
    id: int
    name: str
    basis: str
    rate: Decimal
    effective_from: date
    effective_to: date | None
    is_active: bool
    created_by: int
    created_at: datetime


class PrepareQCRequest(BaseModel):
    location_id: int | None = None
