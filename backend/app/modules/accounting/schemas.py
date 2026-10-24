from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    account_type: AccountType
    parent_id: int | None = None
    allow_posting: bool = True
    is_active: bool = True


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    parent_id: int | None = None
    allow_posting: bool | None = None
    is_active: bool | None = None


class AccountRead(ORM):
    id: int
    code: str
    name: str
    account_type: str
    parent_id: int | None
    allow_posting: bool
    is_system: bool
    is_active: bool
    created_at: datetime


class CostCenterCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=120)
    center_type: str = Field(default="other", min_length=1, max_length=30)
    is_active: bool = True


class CostCenterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    center_type: str | None = Field(default=None, min_length=1, max_length=30)
    is_active: bool | None = None


class CostCenterRead(ORM):
    id: int
    code: str
    name: str
    center_type: str
    is_active: bool
    created_at: datetime


class JournalLineCreate(BaseModel):
    account_id: int
    cost_center_id: int | None = None
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    memo: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def one_side(self):
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("هر ردیف باید فقط بدهکار یا فقط بستانکار باشد")
        return self


class JournalCreate(BaseModel):
    entry_date: date = Field(default_factory=date.today)
    description: str = Field(min_length=1, max_length=500)
    source_type: str | None = Field(default=None, max_length=50)
    source_id: int | None = None
    source_ref: str | None = Field(default=None, max_length=100)
    lines: list[JournalLineCreate] = Field(min_length=2)


class JournalLineRead(ORM):
    id: int
    line_no: int
    account_id: int
    cost_center_id: int | None
    debit: Decimal
    credit: Decimal
    memo: str | None
    account: AccountRead
    cost_center: CostCenterRead | None


class JournalRead(ORM):
    id: int
    number: str
    entry_date: date
    description: str
    source_type: str | None
    source_id: int | None
    source_ref: str | None
    status: str
    created_by: int
    posted_by: int | None
    reversed_by_entry_id: int | None
    created_at: datetime
    posted_at: datetime | None
    lines: list[JournalLineRead]


class AuditRead(ORM):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    source_ref: str | None
    before_data: dict | None
    after_data: dict | None
    created_at: datetime


class InventoryImpairmentCreate(BaseModel):
    inventory_account_code: Literal["1300", "1310", "1320", "1330", "1340"] = "1320"
    amount: Decimal = Field(gt=0)
    reference: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class OverheadVarianceCreate(BaseModel):
    actual_overhead: Decimal = Field(ge=0)
    absorbed_overhead: Decimal = Field(ge=0)
    cogs_share_percent: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    reference: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
