from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.warehouse.repository import WarehouseRepository
from app.modules.warehouse.schemas import *
from app.modules.inventory.model import ProductDefaultLocation, ProductItem, Stock, StockMovement
from app.modules.inventory_operations.model import CycleCount
from app.modules.manufacturing.model import MaterialStock

class WarehouseNotFoundError(LookupError):
    pass

class WarehouseConflictError(ValueError):
    pass

class WarehouseService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = WarehouseRepository(session)

    async def _refresh_location_descendants(self, location):
        children = await self.repo.list_location_children(location.id)
        for child in children:
            child.level = location.level + 1
            child.path = f"{location.path}/{child.code}"
            await self._refresh_location_descendants(child)

    async def create_warehouse(self, payload: WarehouseCreate):
        try:
            obj = await self.repo.create_warehouse(**payload.model_dump())
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as exc:
            await self.session.rollback()
            raise WarehouseConflictError('Warehouse code already exists or manager is invalid') from exc

    async def update_warehouse(self, id: int, payload: WarehouseUpdate):
        obj = await self.repo.get_warehouse(id)
        if not obj:
            raise WarehouseNotFoundError('Warehouse not found')
        data = payload.model_dump(exclude_unset=True)
        try:
            await self.repo.update(obj, **data)
            if 'code' in data:
                roots = [loc for loc in await self.repo.list_locations(id) if loc.parent_id is None]
                for root in roots:
                    root.path = f'{obj.code}/{root.code}'
                    root.level = 0
                    await self._refresh_location_descendants(root)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as exc:
            await self.session.rollback()
            raise WarehouseConflictError('Warehouse code already exists or manager is invalid') from exc

    async def delete_warehouse(self, id: int):
        obj = await self.repo.get_warehouse(id)
        if not obj:
            raise WarehouseNotFoundError('Warehouse not found')
        if await self.repo.list_locations(id):
            raise WarehouseConflictError('انبار دارای مکان است؛ ابتدا اطلاعات را انتقال دهید یا انبار را غیرفعال کنید')
        try:
            await self.session.delete(obj)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise WarehouseConflictError('این انبار سابقه عملیاتی دارد و حذف آن امن نیست؛ آن را غیرفعال کنید') from exc

    async def create_location(self, payload: LocationCreate):
        wh = await self.repo.get_warehouse(payload.warehouse_id)
        if not wh:
            raise WarehouseNotFoundError('Warehouse not found')
        parent = None
        level = 0
        path = f'{wh.code}/{payload.code}'
        if payload.parent_id:
            parent = await self.repo.get_location(payload.parent_id)
            if not parent or parent.warehouse_id != payload.warehouse_id:
                raise WarehouseConflictError('Parent location must belong to same warehouse')
            level = parent.level + 1
            path = f'{parent.path}/{payload.code}'
        try:
            obj = await self.repo.create_location(**payload.model_dump(), level=level, path=path)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as exc:
            await self.session.rollback()
            raise WarehouseConflictError('Location code already exists in warehouse') from exc

    async def delete_location(self, id: int):
        obj = await self.repo.get_location(id)
        if not obj:
            raise WarehouseNotFoundError('Location not found')
        if await self.repo.list_location_children(id):
            raise WarehouseConflictError('این مکان زیرمجموعه دارد و قابل حذف نیست؛ ابتدا زیرمکان‌ها را جابه‌جا یا حذف کنید')
        protected_checks = [
            select(ProductItem.id).where(ProductItem.location_id == id).limit(1),
            select(Stock.id).where(Stock.location_id == id).limit(1),
            select(StockMovement.id).where(StockMovement.location_id == id).limit(1),
            select(ProductDefaultLocation.id).where(ProductDefaultLocation.location_id == id).limit(1),
            select(MaterialStock.id).where(MaterialStock.location_id == id).limit(1),
            select(CycleCount.id).where(CycleCount.location_id == id).limit(1),
        ]
        for stmt in protected_checks:
            if await self.session.scalar(stmt) is not None:
                raise WarehouseConflictError('این مکان موجودی، تنظیم یا سابقه عملیاتی دارد و حذف آن امن نیست؛ آن را غیرفعال کنید')
        try:
            await self.session.delete(obj)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise WarehouseConflictError('این مکان در عملیات دیگری استفاده شده و حذف آن امن نیست؛ آن را غیرفعال کنید') from exc

    async def update_location(self, id: int, payload: LocationUpdate):
        obj = await self.repo.get_location(id)
        if not obj:
            raise WarehouseNotFoundError('Location not found')
        data = payload.model_dump(exclude_unset=True)
        new_parent_id = data.get('parent_id', obj.parent_id)
        if new_parent_id == id:
            raise WarehouseConflictError('Location cannot be its own parent')
        parent = None
        if new_parent_id is not None:
            parent = await self.repo.get_location(new_parent_id)
            if not parent:
                raise WarehouseNotFoundError('Parent location not found')
            if parent.warehouse_id != obj.warehouse_id:
                raise WarehouseConflictError('Parent location must belong to same warehouse')
            if parent.path == obj.path or parent.path.startswith(f"{obj.path}/"):
                raise WarehouseConflictError('Location cannot be moved under one of its descendants')
        code = data.get('code', obj.code)
        data['level'] = parent.level + 1 if parent else 0
        if parent:
            data['path'] = f'{parent.path}/{code}'
        else:
            warehouse = await self.repo.get_warehouse(obj.warehouse_id)
            if warehouse is None:
                raise WarehouseNotFoundError('Warehouse not found')
            data['path'] = f'{warehouse.code}/{code}'
        try:
            await self.repo.update(obj, **data)
            await self._refresh_location_descendants(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as exc:
            await self.session.rollback()
            raise WarehouseConflictError('Location code conflicts with existing data') from exc

