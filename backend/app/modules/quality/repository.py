from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.quality.model import QCRecord, Label

class QualityRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_qc_record(self, **data):
        o = QCRecord(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def list_qc_records(self, item_id: int | None = None, *, offset: int = 0, limit: int = 500):
        q = select(QCRecord)
        if item_id is not None:
            q = q.where(QCRecord.item_id == item_id)
        q = q.order_by(QCRecord.checked_at.desc(), QCRecord.id.desc()).offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())

    async def create_label(self, **data):
        o = Label(**data)
        self.session.add(o)
        await self.session.flush()
        return o

    async def list_labels(self, item_id: int | None = None, *, offset: int = 0, limit: int = 500):
        q = select(Label)
        if item_id is not None:
            q = q.where(Label.item_id == item_id)
        q = q.order_by(Label.printed_at.desc(), Label.id.desc()).offset(offset).limit(limit)
        return list((await self.session.scalars(q)).all())
