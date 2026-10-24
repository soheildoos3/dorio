from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.inventory_operations.model import (
    StockTransfer,
    StockAdjustment,
    CycleCount,
    CycleCountLine,
    StockOpening,
)


class InventoryOperationsRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_transfer(self, id: int, for_update=False):
        q = select(StockTransfer).where(StockTransfer.id == id)
        if for_update:
            q = q.with_for_update()
        return await self.session.scalar(q)

    async def list_transfers(self):
        return list(
            (
                await self.session.scalars(
                    select(StockTransfer).order_by(StockTransfer.id.desc())
                )
            ).all()
        )

    async def create_transfer(self, **data):
        o = StockTransfer(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def create_adjustment(self, **data):
        o = StockAdjustment(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def list_adjustments(self, *, offset: int = 0, limit: int = 500):
        q = select(StockAdjustment).order_by(StockAdjustment.created_at.desc(), StockAdjustment.id.desc()).offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())

    async def create_cycle_count(self, **data):
        o = CycleCount(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def list_cycle_counts(self, *, offset: int = 0, limit: int = 500):
        q = select(CycleCount).order_by(CycleCount.id.desc()).offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())

    async def get_cycle_count(self, id: int, for_update=False):
        q = select(CycleCount).where(CycleCount.id == id)
        if for_update:
            q = q.with_for_update()
        return await self.session.scalar(q)

    async def create_cycle_line(self, **data):
        o = CycleCountLine(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def list_cycle_lines(self, cycle_count_id: int):
        return list(
            (
                await self.session.scalars(
                    select(CycleCountLine)
                    .where(CycleCountLine.cycle_count_id == cycle_count_id)
                    .order_by(CycleCountLine.id)
                )
            ).all()
        )

    async def create_opening(self, **data):
        o = StockOpening(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def list_openings(self, *, offset: int = 0, limit: int = 500):
        q = select(StockOpening).order_by(StockOpening.recorded_at.desc(), StockOpening.id.desc()).offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())

    async def opening_exists(self, variant_id: int, location_id: int) -> bool:
        q = select(StockOpening.id).where(StockOpening.variant_id == variant_id, StockOpening.location_id == location_id).limit(1)
        return (await self.session.scalar(q)) is not None
