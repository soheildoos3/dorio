from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.warehouse.model import Warehouse, Location

class WarehouseRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_warehouse(self, id: int):
        return await self.session.get(Warehouse, id)

    async def list_warehouses(self):
        return list((await self.session.scalars(select(Warehouse).order_by(Warehouse.id))).all())

    async def create_warehouse(self, **data):
        obj = Warehouse(**data)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_location(self, id: int):
        return await self.session.get(Location, id)

    async def list_locations(self, warehouse_id: int):
        return list((await self.session.scalars(select(Location).where(Location.warehouse_id == warehouse_id).order_by(Location.sort_order, Location.id))).all())

    async def list_location_children(self, parent_id: int):
        return list((await self.session.scalars(select(Location).where(Location.parent_id == parent_id).order_by(Location.sort_order, Location.id))).all())

    async def create_location(self, **data):
        obj = Location(**data)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj, **data):
        for k, v in data.items():
            setattr(obj, k, v)
        await self.session.flush()
        return obj
