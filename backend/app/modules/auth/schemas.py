from pydantic import BaseModel, Field

from app.modules.user.schemas import UserRead


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str


class BootstrapRequest(BaseModel):
    username: str = Field(min_length=3)
    full_name: str
    password: str = Field(min_length=8)
    email: str | None = None
    phone: str | None = None


class AuthMe(BaseModel):
    user: UserRead
    permissions: list[str]
