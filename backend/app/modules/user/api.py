from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_admin, require_permission
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import PermissionRead, RoleCreate, RoleRead, RoleUpdate, UserCreate, UserRead, UserUpdate
from app.modules.user.service import UserService

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_permission("users.view"))])
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await UserService(db).list(offset=offset, limit=limit, user_type=user_type)


@router.get("/permissions", response_model=list[PermissionRead], dependencies=[Depends(require_permission("users.view"))])
async def permissions(db: AsyncSession = Depends(get_db)):
    return await UserRepository(db).list_permissions()


@router.get("/roles", response_model=list[RoleRead], dependencies=[Depends(require_permission("users.view"))])
async def roles(db: AsyncSession = Depends(get_db)):
    return await UserRepository(db).list_roles()


@router.post("/roles", response_model=RoleRead, status_code=201, dependencies=[Depends(require_admin)])
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)):
    return await UserService(db).create_role(payload)


@router.patch("/roles/{role_id}", response_model=RoleRead, dependencies=[Depends(require_admin)])
async def patch_role(role_id: int, payload: RoleUpdate, db: AsyncSession = Depends(get_db)):
    return await UserService(db).update_role(role_id, payload)


@router.get("/{user_id}", response_model=UserRead, dependencies=[Depends(require_permission("users.view"))])
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await UserService(db).read(user_id)


@router.post("", response_model=UserRead, status_code=201, dependencies=[Depends(require_admin)])
async def create_user(payload: UserCreate, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if payload.is_superuser and not admin.is_superuser:
        raise HTTPException(403, "Only a superuser can create another superuser")
    return await UserService(db).create(payload)


@router.patch("/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
async def update_user(user_id: int, payload: UserUpdate, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if payload.is_superuser is True and not admin.is_superuser:
        raise HTTPException(403, "Only a superuser can grant superuser access")
    if user_id == admin.id and (payload.status == "inactive" or payload.is_superuser is False or payload.panel_access is False):
        raise HTTPException(409, "نمی‌توانید دسترسی مدیریتی حساب خودتان را غیرفعال کنید")
    return await UserService(db).update(user_id, payload)


@router.delete("/{user_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_user(user_id: int, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(409, "نمی‌توانید حساب خودتان را غیرفعال کنید")
    await UserService(db).delete(user_id)
    return Response(status_code=204)
