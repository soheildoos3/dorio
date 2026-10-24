from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash
from app.modules.user.model import Role, User
from app.modules.user.repository import UserRepository


class UserService:
    def __init__(self, session):
        self.session = session
        self.repository = UserRepository(session)

    @staticmethod
    def effective_permissions(user: User) -> list[str]:
        if user.is_superuser:
            return ["*"]
        permissions = {p.code for p in (user.role.permissions if user.role else [])}
        for override in user.permission_overrides:
            code = override.permission.code
            if override.is_allowed:
                permissions.add(code)
            else:
                permissions.discard(code)
        return sorted(permissions)

    async def get(self, user_id: int):
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise HTTPException(404, "کاربر پیدا نشد")
        return user

    async def read(self, user_id: int):
        user = await self.get(user_id)
        return self._serialize(user)

    async def list(self, offset=0, limit=100, user_type: str | None = None):
        users = await self.repository.list(offset, limit, user_type=user_type)
        return [self._serialize(user) for user in users]

    def _serialize(self, user: User):
        from app.modules.user.schemas import UserRead
        data = UserRead.model_validate(user).model_dump()
        data["effective_permissions"] = self.effective_permissions(user)
        return data

    async def _validate_role(self, role_id: int | None):
        if role_id is None:
            return None
        role = await self.repository.get_role(role_id)
        if not role:
            raise HTTPException(400, "نقش انتخاب‌شده وجود ندارد")
        return role

    async def _validate_permission_ids(self, ids: list[int]):
        existing = await self.repository.permissions_by_ids(ids)
        if len({p.id for p in existing}) != len(set(ids)):
            raise HTTPException(400, "یکی از دسترسی‌های انتخاب‌شده معتبر نیست")
        return existing

    async def _validate_overrides(self, overrides):
        ids = [x.permission_id for x in overrides]
        existing = await self.repository.permissions_by_ids(ids)
        if len({p.id for p in existing}) != len(set(ids)):
            raise HTTPException(400, "یکی از دسترسی‌های انتخاب‌شده معتبر نیست")

    async def create(self, data):
        if data.username and await self.repository.get_by_username(data.username):
            raise HTTPException(409, "نام کاربری قبلاً ثبت شده است")
        if data.email and await self.repository.get_by_email(str(data.email)):
            raise HTTPException(409, "ایمیل قبلاً ثبت شده است")
        if data.phone and await self.repository.get_by_phone(data.phone):
            raise HTTPException(409, "شماره تلفن قبلاً ثبت شده است")
        await self._validate_role(data.role_id)
        await self._validate_overrides(data.permission_overrides)
        if data.panel_access and not (data.role_id or data.is_superuser):
            raise HTTPException(400, "برای دسترسی پنل باید نقش انتخاب شود")
        user = User(
            username=data.username or None,
            full_name=data.full_name,
            phone=data.phone or None,
            email=str(data.email) if data.email else None,
            password_hash=get_password_hash(data.password),
            user_type=data.user_type,
            panel_access=data.panel_access,
            role_id=data.role_id,
            status=data.status,
            is_superuser=data.is_superuser,
        )
        try:
            await self.repository.add(user)
            await self.repository.replace_overrides(
                user.id, [(x.permission_id, x.is_allowed) for x in data.permission_overrides]
            )
            await self.session.commit()
            return await self.read(user.id)
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "اطلاعات کاربر با رکورد موجود تداخل دارد") from exc

    async def update(self, user_id: int, data):
        user = await self.get(user_id)
        values = data.model_dump(exclude_unset=True)
        password = values.pop("password", None)
        overrides = values.pop("permission_overrides", None)
        if password:
            user.password_hash = get_password_hash(password)
        if "role_id" in values:
            await self._validate_role(values["role_id"])
        if overrides is not None:
            await self._validate_overrides(overrides)
            await self.repository.replace_overrides(
                user.id, [(x.permission_id, x.is_allowed) for x in overrides]
            )
        for key, value in values.items():
            if key == "email" and value:
                value = str(value)
            if key in {"username", "phone", "email"} and value == "":
                value = None
            setattr(user, key, value)
        if not user.username and not user.email and not user.phone:
            raise HTTPException(400, "حداقل یکی از نام کاربری، ایمیل یا تلفن باید باقی بماند")
        if user.panel_access and not (user.role_id or user.is_superuser):
            raise HTTPException(400, "کاربر دارای دسترسی پنل باید نقش داشته باشد")
        try:
            await self.session.commit()
            return await self.read(user.id)
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "اطلاعات کاربر با رکورد موجود تداخل دارد") from exc

    async def delete(self, user_id: int):
        user = await self.get(user_id)
        user.status = "inactive"
        user.panel_access = False
        await self.session.commit()

    async def create_role(self, data):
        if await self.repository.get_role_by_code(data.code):
            raise HTTPException(409, "کد نقش قبلاً ثبت شده است")
        role = Role(code=data.code, name=data.name)
        role.permissions = await self._validate_permission_ids(data.permission_ids)
        self.session.add(role)
        await self.session.commit()
        await self.session.refresh(role)
        return role

    async def update_role(self, role_id: int, data):
        role = await self.repository.get_role(role_id)
        if not role:
            raise HTTPException(404, "نقش پیدا نشد")
        values = data.model_dump(exclude_unset=True)
        if "name" in values:
            role.name = values["name"]
        if "permission_ids" in values:
            role.permissions = await self._validate_permission_ids(values["permission_ids"])
        await self.session.commit()
        await self.session.refresh(role)
        return role
