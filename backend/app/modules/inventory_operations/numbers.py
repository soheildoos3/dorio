from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.modules.inventory_operations.model import DocumentCounter

async def next_document_number(session: AsyncSession, prefix: str) -> str:
    tz = ZoneInfo(settings.WARRANTY_TIMEZONE)
    now = datetime.now(tz)
    day = now.strftime("%Y%m%d")
    key = f"{prefix}:{day}"
    stmt = (
        insert(DocumentCounter)
        .values(key=key, last_value=1)
        .on_conflict_do_update(index_elements=[DocumentCounter.key], set_={"last_value": DocumentCounter.last_value + 1})
        .returning(DocumentCounter.last_value)
    )
    seq = int((await session.execute(stmt)).scalar_one())
    if seq > 999999:
        raise RuntimeError(f"Daily {prefix} sequence exhausted")
    return f"{prefix}-{day}-{seq:06d}"
