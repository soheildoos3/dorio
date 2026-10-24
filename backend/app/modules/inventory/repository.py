from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.inventory.model import ProductDefaultLocation, ProductItem, Stock, StockMovement, StockReservation

class InventoryRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_item(self, id: int):
        return await self.session.get(ProductItem, id)

    async def get_item_by_serial(self, serial: str):
        return await self.session.scalar(select(ProductItem).where(ProductItem.serial_number == serial))

    async def list_items(self, variant_id: int | None=None, offset: int=0, limit: int=100):
        q = select(ProductItem).order_by(ProductItem.id.desc()).offset(offset).limit(limit)
        if variant_id is not None:
            q = q.where(ProductItem.variant_id == variant_id)
        return list((await self.session.scalars(q)).all())

    async def create_item(self, **data):
        o = ProductItem(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def get_stock(self, variant_id: int, location_id: int, *, for_update=False):
        q = select(Stock).where(Stock.variant_id == variant_id, Stock.location_id == location_id)
        if for_update:
            q = q.with_for_update()
        return await self.session.scalar(q)

    async def list_stock(self, variant_id: int | None=None):
        q = select(Stock).order_by(Stock.variant_id, Stock.location_id)
        if variant_id is not None:
            q = q.where(Stock.variant_id == variant_id)
        return list((await self.session.scalars(q)).all())

    async def create_stock(self, variant_id: int, location_id: int):
        o = Stock(variant_id=variant_id, location_id=location_id, quantity=0, reserved=0)
        self.session.add(o)
        await self.session.flush()
        return o

    async def add_movement(self, **data):
        o = StockMovement(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def create_reservation(self, **data):
        o = StockReservation(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def get_reservation(self, id: int, *, for_update=False):
        q = select(StockReservation).where(StockReservation.id == id)
        if for_update:
            q = q.with_for_update()
        return await self.session.scalar(q)

    async def list_reservations(self, *, variant_id: int | None = None, offset: int = 0, limit: int = 500):
        q = select(StockReservation).order_by(StockReservation.id.desc())
        if variant_id is not None:
            q = q.where(StockReservation.variant_id == variant_id)
        q = q.offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())

    async def list_default_locations(self, *, variant_id: int | None = None, offset: int = 0, limit: int = 1000):
        q = select(ProductDefaultLocation).order_by(ProductDefaultLocation.variant_id, ProductDefaultLocation.priority, ProductDefaultLocation.id)
        if variant_id is not None:
            q = q.where(ProductDefaultLocation.variant_id == variant_id)
        q = q.offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())


    async def list_movements(self, *, movement_type=None, variant_id: int | None = None, offset: int = 0, limit: int = 500):
        q = select(StockMovement).order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        if movement_type is not None:
            q = q.where(StockMovement.type == movement_type)
        if variant_id is not None:
            q = q.where(StockMovement.variant_id == variant_id)
        q = q.offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())

    async def clear_primary_default_location(self, variant_id: int) -> None:
        await self.session.execute(
            update(ProductDefaultLocation)
            .where(ProductDefaultLocation.variant_id == variant_id, ProductDefaultLocation.is_primary.is_(True))
            .values(is_primary=False)
        )

    async def create_default_location(self, **data):
        o = ProductDefaultLocation(**data)
        self.session.add(o)
        await self.session.flush()
        return o
