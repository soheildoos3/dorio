from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

UserStatus = Literal["active", "inactive", "suspended"]
UserType = Literal["customer", "employee", "tailor"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PermissionRead(ORMModel):
    id: int
    code: str
    name: str
    description: str | None


class PermissionOverrideInput(BaseModel):
    permission_id: int
    is_allowed: bool


class PermissionOverrideRead(ORMModel):
    id: int
    permission_id: int
    is_allowed: bool
    permission: PermissionRead


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=100)
    permission_ids: list[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    permission_ids: list[int] | None = None


class RoleRead(ORMModel):
    id: int
    code: str
    name: str
    is_system: bool
    created_at: datetime
    permissions: list[PermissionRead] = Field(default_factory=list)


class UserCreate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    user_type: UserType = "customer"
    panel_access: bool = False
    role_id: int | None = None
    status: UserStatus = "active"
    is_superuser: bool = False
    password: str = Field(min_length=8, max_length=128)
    permission_overrides: list[PermissionOverrideInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity(self):
        if not self.username and not self.email and not self.phone:
            raise ValueError("حداقل یکی از نام کاربری، ایمیل یا تلفن لازم است")
        if self.panel_access and self.role_id is None and not self.is_superuser:
            raise ValueError("برای دسترسی پنل باید نقش انتخاب شود")
        return self


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    user_type: UserType | None = None
    panel_access: bool | None = None
    role_id: int | None = None
    status: UserStatus | None = None
    is_superuser: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    permission_overrides: list[PermissionOverrideInput] | None = None


class UserRead(ORMModel):
    id: int
    username: str | None
    full_name: str
    phone: str | None
    email: str | None
    user_type: str
    panel_access: bool
    role_id: int | None
    status: str
    is_superuser: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    role: RoleRead | None = None
    permission_overrides: list[PermissionOverrideRead] = Field(default_factory=list)
    effective_permissions: list[str] = Field(default_factory=list)
