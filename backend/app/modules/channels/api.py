from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.catalog.model import ProductVariant
from app.modules.channels.model import ProductChannelPrice, SalesChannel
from app.modules.channels.schemas import ChannelCreate, ChannelPriceCreate, ChannelPriceRead, ChannelPriceUpdate, ChannelRead, ChannelUpdate

router = APIRouter(prefix="/channels", tags=["channels"], dependencies=[Depends(get_current_user)])


def _effective(row: ProductChannelPrice, now: datetime | None = None) -> Decimal:
    now = now or datetime.now(timezone.utc)
    price = Decimal(row.list_price)
    if not row.is_active or (row.starts_at and now < row.starts_at) or (row.ends_at and now >= row.ends_at):
        return price
    discount = Decimal(row.discount_value or 0)
    if row.discount_type == "percent":
        price -= price * discount / Decimal("100")
    elif row.discount_type == "fixed":
        price -= discount
    return max(price, Decimal("0"))


def _price_read(row: ProductChannelPrice) -> dict:
    return {
        "id": row.id, "variant_id": row.variant_id, "channel_id": row.channel_id,
        "list_price": row.list_price, "discount_type": row.discount_type, "discount_value": row.discount_value,
        "starts_at": row.starts_at, "ends_at": row.ends_at, "is_active": row.is_active,
        "created_at": row.created_at, "updated_at": row.updated_at, "effective_price": _effective(row),
    }


@router.get("", response_model=list[ChannelRead])
async def list_channels(db: AsyncSession = Depends(get_db)):
    return list((await db.execute(select(SalesChannel).order_by(SalesChannel.name))).scalars().all())


@router.post("", response_model=ChannelRead, status_code=201, dependencies=[Depends(require_permission("channels.manage"))])
async def create_channel(payload: ChannelCreate, db: AsyncSession = Depends(get_db)):
    obj = SalesChannel(**payload.model_dump())
    db.add(obj)
    try:
        await db.commit(); await db.refresh(obj); return obj
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "کد پلتفرم قبلاً ثبت شده است") from exc


@router.patch("/{channel_id}", response_model=ChannelRead, dependencies=[Depends(require_permission("channels.manage"))])
async def update_channel(channel_id: int, payload: ChannelUpdate, db: AsyncSession = Depends(get_db)):
    obj = await db.get(SalesChannel, channel_id)
    if obj is None: raise HTTPException(404, "پلتفرم پیدا نشد")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(obj, key, value)
    try:
        await db.commit(); await db.refresh(obj); return obj
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "اطلاعات پلتفرم با رکورد دیگری تداخل دارد") from exc


@router.get("/prices", response_model=list[ChannelPriceRead], dependencies=[Depends(require_permission("pricing.view"))])
async def list_prices(variant_id: int | None = Query(None), channel_id: int | None = Query(None), db: AsyncSession = Depends(get_db)):
    q = select(ProductChannelPrice).order_by(ProductChannelPrice.variant_id, ProductChannelPrice.channel_id)
    if variant_id is not None: q = q.where(ProductChannelPrice.variant_id == variant_id)
    if channel_id is not None: q = q.where(ProductChannelPrice.channel_id == channel_id)
    rows = list((await db.execute(q)).scalars().all())
    return [_price_read(x) for x in rows]


@router.post("/prices", response_model=ChannelPriceRead, status_code=201, dependencies=[Depends(require_permission("pricing.manage"))])
async def create_price(payload: ChannelPriceCreate, db: AsyncSession = Depends(get_db)):
    if await db.get(ProductVariant, payload.variant_id) is None: raise HTTPException(404, "تنوع محصول پیدا نشد")
    if await db.get(SalesChannel, payload.channel_id) is None: raise HTTPException(404, "پلتفرم پیدا نشد")
    obj = ProductChannelPrice(**payload.model_dump())
    db.add(obj)
    try:
        await db.commit(); await db.refresh(obj); return _price_read(obj)
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "برای این تنوع و پلتفرم قبلاً قیمت ثبت شده است") from exc


@router.patch("/prices/{price_id}", response_model=ChannelPriceRead, dependencies=[Depends(require_permission("pricing.manage"))])
async def update_price(price_id: int, payload: ChannelPriceUpdate, db: AsyncSession = Depends(get_db)):
    obj = await db.get(ProductChannelPrice, price_id)
    if obj is None: raise HTTPException(404, "قیمت پلتفرم پیدا نشد")
    values = payload.model_dump(exclude_unset=True)
    for k, v in values.items(): setattr(obj, k, v)
    if obj.discount_type == "percent" and Decimal(obj.discount_value or 0) > 100: raise HTTPException(422, "درصد تخفیف نمی‌تواند بیشتر از ۱۰۰ باشد")
    if obj.starts_at and obj.ends_at and obj.ends_at <= obj.starts_at: raise HTTPException(422, "پایان تخفیف باید بعد از شروع باشد")
    await db.commit(); await db.refresh(obj); return _price_read(obj)


@router.delete("/prices/{price_id}", status_code=204, dependencies=[Depends(require_permission("pricing.manage"))])
async def delete_price(price_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(ProductChannelPrice, price_id)
    if obj is None: raise HTTPException(404, "قیمت پلتفرم پیدا نشد")
    await db.delete(obj); await db.commit(); return Response(status_code=204)
