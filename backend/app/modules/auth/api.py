from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_password_hash,
    new_csrf_token,
    verify_password,
)
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, permission_codes
from app.modules.auth.schemas import AuthMe, BootstrapRequest, LoginRequest
from app.modules.user.constants import (
    DEFAULT_PERMISSION_DEFINITIONS,
    DEFAULT_ROLE_TEMPLATES,
)
from app.modules.user.model import Permission, Role, User
from app.modules.user.repository import UserRepository
from app.modules.user.service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def set_cookies(response: Response, user_id: int):
    response.set_cookie(
        "dario_access",
        create_access_token(user_id),
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )
    csrf = new_csrf_token()
    response.set_cookie(
        "dario_csrf",
        csrf,
        httponly=False,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )


async def seed_rbac(db: AsyncSession):
    repo = UserRepository(db)

    permissions = {
        permission.code: permission for permission in await repo.list_permissions()
    }

    # Create missing permissions first
    for code, name in DEFAULT_PERMISSION_DEFINITIONS:
        if code not in permissions:
            permission = Permission(
                code=code,
                name=name,
            )
            db.add(permission)
            permissions[code] = permission

    # We need permission IDs before populating role_permissions
    await db.flush()

    for code, template in DEFAULT_ROLE_TEMPLATES.items():
        wanted = template["permissions"]

        selected_permissions = (
            list(permissions.values())
            if "*" in wanted
            else [
                permissions[permission_code]
                for permission_code in wanted
                if permission_code in permissions
            ]
        )

        role = await repo.get_role_by_code(code)

        if role is None:
            # Assign permissions while the role is still transient/new.
            # This avoids an async lazy-load.
            role = Role(
                code=code,
                name=template["name"],
                is_system=True,
                permissions=selected_permissions,
            )
            db.add(role)
        else:
            # Existing role was loaded with selectinload(Role.permissions)
            # by get_role_by_code(), so replacing the collection is safe.
            role.name = template["name"]
            role.is_system = True
            role.permissions = selected_permissions

    await db.flush()


@router.get("/bootstrap-status")
async def bootstrap_status(db: AsyncSession = Depends(get_db)):
    return {"required": await UserRepository(db).count_users() == 0}


@router.post("/bootstrap")
async def bootstrap(
    payload: BootstrapRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    repo = UserRepository(db)
    if await repo.count_users() != 0:
        raise HTTPException(409, "Bootstrap already completed")
    await seed_rbac(db)
    role = await repo.get_role_by_code("admin")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=get_password_hash(payload.password),
        user_type="employee",
        panel_access=True,
        role_id=role.id if role else None,
        status="active",
        is_superuser=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    set_cookies(response, user.id)
    return {"ok": True}


@router.post("/login")
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    repo = UserRepository(db)
    user = await repo.get_by_identifier(payload.identifier.strip())
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "نام کاربری/ایمیل/تلفن یا رمز عبور نادرست است")
    if user.status != "active":
        raise HTTPException(403, "حساب کاربری فعال نیست")
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    set_cookies(response, user.id)
    return {"ok": True, "panel_access": user.panel_access or user.is_superuser}


@router.post("/logout")
async def logout(response: Response, user=Depends(get_current_user)):
    response.delete_cookie("dario_access", path="/")
    response.delete_cookie("dario_csrf", path="/")
    return {"ok": True}


@router.get("/me", response_model=AuthMe)
async def me(user=Depends(get_current_user)):
    data = UserService(None)._serialize(user)
    return {"user": data, "permissions": sorted(permission_codes(user))}
