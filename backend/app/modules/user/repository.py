from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.model import Permission, Role, User, UserPermissionOverride


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int):
        return await self.session.get(User, user_id)

    async def get_by_identifier(self, value: str):
        stmt = select(User).where(
            or_(User.username == value, User.email == value, User.phone == value)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, value: str):
        return (
            await self.session.execute(select(User).where(User.username == value))
        ).scalar_one_or_none()

    async def get_by_email(self, value: str):
        return (
            await self.session.execute(select(User).where(User.email == value))
        ).scalar_one_or_none()

    async def get_by_phone(self, value: str):
        return (
            await self.session.execute(select(User).where(User.phone == value))
        ).scalar_one_or_none()

    async def list(
        self, offset: int = 0, limit: int = 100, user_type: str | None = None
    ):
        stmt = select(User)
        if user_type:
            stmt = stmt.where(User.user_type == user_type)
        stmt = stmt.order_by(User.full_name, User.id).offset(offset).limit(limit)
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def count_users(self):
        return int(
            (await self.session.execute(select(func.count(User.id)))).scalar_one()
        )

    async def add(self, obj):
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def list_roles(self):
        stmt = select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def get_role(self, role_id: int):
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.id == role_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_role_by_code(self, code: str):
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.code == code)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_permissions(self):
        return list(
            (await self.session.execute(select(Permission).order_by(Permission.code)))
            .scalars()
            .all()
        )

    async def get_permission_by_code(self, code: str):
        return (
            await self.session.execute(
                select(Permission).where(Permission.code == code)
            )
        ).scalar_one_or_none()

    async def permissions_by_ids(self, ids: list[int]):
        if not ids:
            return []
        return list(
            (
                await self.session.execute(
                    select(Permission).where(Permission.id.in_(ids))
                )
            )
            .scalars()
            .all()
        )

    async def replace_overrides(self, user_id: int, overrides: list[tuple[int, bool]]):
        await self.session.execute(
            delete(UserPermissionOverride).where(
                UserPermissionOverride.user_id == user_id
            )
        )
        for permission_id, is_allowed in overrides:
            self.session.add(
                UserPermissionOverride(
                    user_id=user_id, permission_id=permission_id, is_allowed=is_allowed
                )
            )
        await self.session.flush()
