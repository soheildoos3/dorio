from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.warranty.model import WarrantyDailyCounter


def luhn_check_digit(body: str) -> int:
    if not body.isdigit():
        raise ValueError("Luhn body must contain digits only")
    digits = [int(ch) for ch in body] + [0]
    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (10 - total % 10) % 10


def validate_warranty_serial(serial: str) -> bool:
    parts = serial.split("-")
    if len(parts) != 5 or [len(x) for x in parts] != [4, 2, 2, 6, 1]:
        return False
    if not all(x.isdigit() for x in parts):
        return False
    try:
        date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return False
    sequence = int(parts[3])
    if sequence < 1 or sequence > 999999:
        return False
    body = "".join(parts[:4])
    return int(parts[4]) == luhn_check_digit(body)


async def generate_warranty_serial(session: AsyncSession) -> str:
    today = datetime.now(ZoneInfo(settings.WARRANTY_TIMEZONE)).date()
    stmt = (
        insert(WarrantyDailyCounter)
        .values(day=today, last_value=1)
        .on_conflict_do_update(
            index_elements=[WarrantyDailyCounter.day],
            set_={"last_value": WarrantyDailyCounter.last_value + 1},
        )
        .returning(WarrantyDailyCounter.last_value)
    )
    sequence = int((await session.execute(stmt)).scalar_one())
    if sequence > 999999:
        raise RuntimeError("Daily warranty serial capacity exceeded")
    seq = f"{sequence:06d}"
    body = f"{today.year:04d}{today.month:02d}{today.day:02d}{seq}"
    check = luhn_check_digit(body)
    return f"{today.year:04d}-{today.month:02d}-{today.day:02d}-{seq}-{check}"
