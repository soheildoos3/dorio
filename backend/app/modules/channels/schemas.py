from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChannelCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    is_active: bool = True
    notes: str | None = None


class ChannelUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class ChannelRead(ChannelCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ChannelPriceCreate(BaseModel):
    variant_id: int
    channel_id: int
    list_price: Decimal = Field(ge=0)
    discount_type: str | None = Field(default=None, pattern=r"^(percent|fixed)$")
    discount_value: Decimal = Field(default=Decimal("0"), ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_discount(self):
        if self.discount_type == "percent" and self.discount_value > 100:
            raise ValueError("Percent discount cannot exceed 100")
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class ChannelPriceUpdate(BaseModel):
    list_price: Decimal | None = Field(default=None, ge=0)
    discount_type: str | None = Field(default=None, pattern=r"^(percent|fixed)$")
    discount_value: Decimal | None = Field(default=None, ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None


class ChannelPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    variant_id: int
    channel_id: int
    list_price: Decimal
    discount_type: str | None
    discount_value: Decimal
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    effective_price: Decimal
