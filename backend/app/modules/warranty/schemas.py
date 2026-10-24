from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WarrantyStatus = Literal["inactive", "grace", "active", "expired", "void"]


def _validate_url(value: str | None, field_name: str, *, allow_template: bool = False):
    if value is None:
        return value
    value = value.strip().rstrip("/") if not allow_template else value.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        raise ValueError(f"{field_name} must start with http:// or https://")
    return value


class SettingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=8, max_length=500)
    qr_base_url: str | None = Field(default=None, max_length=500)
    qr_destination_template: str | None = Field(default=None, max_length=1000)
    grace_period_months: int = Field(default=6, ge=0, le=36)
    is_default: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return _validate_url(value, "base_url")

    @field_validator("qr_base_url")
    @classmethod
    def validate_qr_base_url(cls, value: str | None):
        return _validate_url(value, "qr_base_url")

    @field_validator("qr_destination_template")
    @classmethod
    def validate_destination(cls, value: str | None):
        return _validate_url(value, "qr_destination_template", allow_template=True)


class SettingUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    qr_base_url: str | None = Field(default=None, max_length=500)
    qr_destination_template: str | None = Field(default=None, max_length=1000)
    grace_period_months: int | None = Field(default=None, ge=0, le=36)
    is_default: bool | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None):
        return _validate_url(value, "base_url")

    @field_validator("qr_base_url")
    @classmethod
    def validate_qr_base_url(cls, value: str | None):
        return _validate_url(value, "qr_base_url")

    @field_validator("qr_destination_template")
    @classmethod
    def validate_destination(cls, value: str | None):
        return _validate_url(value, "qr_destination_template", allow_template=True)


class SettingRead(SettingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class WarrantyCreate(BaseModel):
    item_id: int
    customer_name: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=20)
    notes: str | None = None


class WarrantyUpdate(BaseModel):
    status: WarrantyStatus | None = None
    warranty_months: int | None = Field(default=None, ge=1, le=120)
    customer_name: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=20)
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    qr_redirect_url: str | None = Field(default=None, max_length=1000)
    notes: str | None = None

    @field_validator("qr_redirect_url")
    @classmethod
    def validate_qr_redirect_url(cls, value: str | None):
        return _validate_url(value, "qr_redirect_url")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.activated_at and self.expires_at and self.expires_at <= self.activated_at:
            raise ValueError("expires_at must be after activated_at")
        return self


class WarrantyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_id: int
    serial: str
    status: str
    warranty_months: int
    customer_name: str | None
    customer_phone: str | None
    outbound_at: datetime | None
    auto_activate_at: datetime | None
    activated_at: datetime | None
    expires_at: datetime | None
    activation_source: str | None
    qr_redirect_url: str | None
    notes: str | None
    created_at: datetime


class PublicWarrantyRead(BaseModel):
    serial: str
    status: str
    product_name: str
    product_description: str | None = None
    product_sku: str | None = None
    variant_sku: str | None = None
    variant_attributes: list[dict[str, str]] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    warranty_months: int
    outbound_at: datetime | None
    auto_activate_at: datetime | None
    activated_at: datetime | None
    expires_at: datetime | None
    activation_source: str | None
    can_activate: bool


class PublicWarrantyActivate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=20)
