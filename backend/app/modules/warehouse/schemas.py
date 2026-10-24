from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.modules.warehouse.constants import LocationType

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    address: str | None = None
    manager_id: int | None = None
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool = True

class WarehouseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = None
    manager_id: int | None = None
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None

class WarehouseRead(ORMModel):
    id: int
    code: str
    name: str
    address: str | None
    manager_id: int | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class LocationCreate(BaseModel):
    warehouse_id: int
    parent_id: int | None = None
    type: LocationType
    code: str = Field(min_length=1, max_length=50)
    name: str | None = Field(default=None, max_length=100)
    is_pickable: bool = False
    is_receivable: bool = False
    max_items: int | None = Field(default=None, ge=0)
    max_weight_kg: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    sort_order: int = 0
    is_active: bool = True

class LocationUpdate(BaseModel):
    parent_id: int | None = None
    type: LocationType | None = None
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, max_length=100)
    is_pickable: bool | None = None
    is_receivable: bool | None = None
    max_items: int | None = Field(default=None, ge=0)
    max_weight_kg: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    sort_order: int | None = None
    is_active: bool | None = None

class LocationRead(ORMModel):
    id: int
    warehouse_id: int
    parent_id: int | None
    type: LocationType
    code: str
    name: str | None
    path: str
    level: int
    is_pickable: bool
    is_receivable: bool
    max_items: int | None
    max_weight_kg: Decimal | None
    sort_order: int
    is_active: bool
    created_at: datetime
