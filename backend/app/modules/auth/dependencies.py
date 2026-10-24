from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.user.repository import UserRepository
from app.modules.user.service import UserService


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("dario_access")
    if not token:
        raise HTTPException(401, "Authentication required")
    try:
        user_id = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(401, "Invalid or expired session") from exc
    user = await UserRepository(db).get_by_id(user_id)
    if not user or user.status != "active":
        raise HTTPException(401, "User is inactive")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        cookie_token = request.cookies.get("dario_csrf")
        header_token = request.headers.get("X-CSRF-Token")
        if not cookie_token or not header_token or cookie_token != header_token:
            raise HTTPException(403, "CSRF validation failed")
    return user


def permission_codes(user):
    return set(UserService.effective_permissions(user))


def require_panel_user(user=Depends(get_current_user)):
    if not user.panel_access and not user.is_superuser:
        raise HTTPException(403, "این حساب دسترسی به پنل ندارد")
    return user


def require_permission(code: str):
    async def dep(user=Depends(require_panel_user)):
        permissions = permission_codes(user)
        if "*" not in permissions and code not in permissions:
            raise HTTPException(403, "Permission denied")
        return user
    return dep



def require_any_permission(*codes: str):
    async def dep(user=Depends(require_panel_user)):
        permissions = permission_codes(user)
        if "*" not in permissions and not any(code in permissions for code in codes):
            raise HTTPException(403, "Permission denied")
        return user
    return dep

def require_admin(user=Depends(require_panel_user)):
    if not user.is_superuser and (user.role is None or user.role.code != "admin"):
        raise HTTPException(403, "System administrator access required")
    return user
