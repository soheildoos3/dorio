from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.inventory.constants import StockMovementType
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.model import ProductItem
from app.modules.inventory.qr_decoder import QRDecodeError, decode_qr_image_bytes
from app.modules.inventory.schemas import (
    ProductDefaultLocationCreate,
    ProductDefaultLocationRead,
    ProductDefaultLocationUpdate,
    ProductItemUpdate,
    ProductItemCreate,
    ProductItemBatchCreate,
    ProductItemRead,
    StockMovementCreate,
    StockMovementRead,
    StockOutboundCreate,
    StockRead,
    StockReservationCreate,
    StockReservationRead,
    SalesSummary,
)
from app.modules.inventory.service import (
    InventoryConflictError,
    InventoryNotFoundError,
    InventoryService,
)

router = APIRouter(prefix="/inventory", tags=["inventory"], dependencies=[Depends(get_current_user), Depends(require_permission("inventory.view"))])


def svc(db: AsyncSession = Depends(get_db)):
    return InventoryService(db)


def h(exc: Exception):
    if isinstance(exc, InventoryNotFoundError):
        raise HTTPException(404, str(exc))
    if isinstance(exc, InventoryConflictError):
        raise HTTPException(409, str(exc))
    raise exc


@router.post("/decode-qr-image")
async def decode_qr_image(file: UploadFile = File(...)):
    content_type = (file.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(415, "فایل ارسالی باید تصویر باشد")

    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "حجم تصویر QR نباید بیشتر از ۱۰ مگابایت باشد")
    try:
        value = decode_qr_image_bytes(data)
    except QRDecodeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, "ماژول خواندن QR روی سرور نصب نیست؛ requirements را دوباره نصب کنید") from exc

    if not value:
        raise HTTPException(422, "QR در تصویر پیدا نشد؛ دوربین را نزدیک‌تر ببرید و تصویر واضح‌تری بگیرید")
    return {"value": value}


@router.get("/scan/{identifier}", response_model=ProductItemRead)
async def scan_item(identifier: str, db: AsyncSession = Depends(get_db)):
    value = identifier.strip()
    if not value:
        raise HTTPException(400, "شناسه کالا خالی است")
    item = await db.scalar(
        select(ProductItem).where(
            or_(ProductItem.warranty_serial == value, ProductItem.serial_number == value)
        )
    )
    if item is None:
        raise HTTPException(404, "واحد کالا با این QR/سریال پیدا نشد")
    return item


@router.get("/items", response_model=list[ProductItemRead])
async def items(
    variant_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryRepository(db).list_items(variant_id, offset, limit)


@router.post("/items", response_model=ProductItemRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def create_item(p: ProductItemCreate, s: InventoryService = Depends(svc)):
    try:
        return await s.create_item(p)
    except Exception as exc:
        h(exc)



@router.post("/items/batch", response_model=list[ProductItemRead], status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def create_items_batch(p: ProductItemBatchCreate, s: InventoryService = Depends(svc)):
    try:
        return await s.create_items_batch(p)
    except Exception as exc:
        h(exc)

@router.get("/stock", response_model=list[StockRead])
async def stock(variant_id: int | None = None, db: AsyncSession = Depends(get_db)):
    return await InventoryRepository(db).list_stock(variant_id)


@router.get("/movements", response_model=list[StockMovementRead])
async def movements(
    variant_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryRepository(db).list_movements(
        variant_id=variant_id, offset=offset, limit=limit
    )


@router.post("/movements", response_model=StockMovementRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def movement(p: StockMovementCreate, user=Depends(get_current_user), s: InventoryService = Depends(svc)):
    try:
        return await s.apply_stock_movement(p.model_copy(update={"created_by": user.id}))
    except Exception as exc:
        h(exc)


@router.get("/outbound", response_model=list[StockMovementRead])
async def outbound_history(
    variant_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryRepository(db).list_movements(
        movement_type=StockMovementType.OUT,
        variant_id=variant_id,
        offset=offset,
        limit=limit,
    )


@router.post("/outbound", response_model=StockMovementRead, status_code=201, dependencies=[Depends(require_permission("inventory.outbound"))])
async def outbound(p: StockOutboundCreate, user=Depends(get_current_user), s: InventoryService = Depends(svc)):
    try:
        return await s.outbound(p.model_copy(update={"created_by": user.id}))
    except Exception as exc:
        h(exc)




@router.get("/sales-summary", response_model=SalesSummary, dependencies=[Depends(require_permission("sales.view"))])
async def sales_summary(db: AsyncSession = Depends(get_db)):
    from app.modules.inventory.model import StockMovement
    from app.modules.channels.model import SalesChannel

    qty_expr = func.coalesce(func.sum(-StockMovement.quantity), 0)
    gross_expr = func.coalesce(func.sum(StockMovement.unit_list_price * (-StockMovement.quantity)), 0)
    discount_expr = func.coalesce(func.sum(StockMovement.discount_total), 0)
    net_expr = func.coalesce(func.sum(StockMovement.line_total), 0)

    base = [StockMovement.line_total.is_not(None)]
    total = (await db.execute(
        select(qty_expr, func.count(StockMovement.id), gross_expr, discount_expr, net_expr).where(*base)
    )).one()

    rows = (await db.execute(
        select(
            StockMovement.channel_id,
            func.coalesce(SalesChannel.name, "بدون پلتفرم"),
            qty_expr,
            func.count(StockMovement.id),
            gross_expr,
            discount_expr,
            net_expr,
        )
        .outerjoin(SalesChannel, SalesChannel.id == StockMovement.channel_id)
        .where(*base)
        .group_by(StockMovement.channel_id, SalesChannel.name)
        .order_by(net_expr.desc())
    )).all()

    return {
        "quantity": int(total[0] or 0),
        "outbound_count": int(total[1] or 0),
        "gross_amount": total[2] or 0,
        "discount_amount": total[3] or 0,
        "net_amount": total[4] or 0,
        "channels": [
            {
                "channel_id": r[0], "channel_name": r[1], "quantity": int(r[2] or 0),
                "outbound_count": int(r[3] or 0), "gross_amount": r[4] or 0,
                "discount_amount": r[5] or 0, "net_amount": r[6] or 0,
            } for r in rows
        ],
    }

@router.get("/reservations", response_model=list[StockReservationRead])
async def reservations(
    variant_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryRepository(db).list_reservations(variant_id=variant_id, offset=offset, limit=limit)


@router.post("/reservations", response_model=StockReservationRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def reserve(p: StockReservationCreate, user=Depends(get_current_user), s: InventoryService = Depends(svc)):
    try:
        return await s.reserve(p.model_copy(update={"created_by": user.id}))
    except Exception as exc:
        h(exc)


@router.post("/reservations/{reservation_id}/release", response_model=StockReservationRead, dependencies=[Depends(require_permission("inventory.manage"))])
async def release(
    reservation_id: int,
    user=Depends(get_current_user),
    s: InventoryService = Depends(svc),
):
    try:
        return await s.release_reservation(reservation_id, user.id)
    except Exception as exc:
        h(exc)


@router.get("/default-locations", response_model=list[ProductDefaultLocationRead])
async def default_locations(
    variant_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryRepository(db).list_default_locations(variant_id=variant_id, offset=offset, limit=limit)


@router.post("/default-locations", response_model=ProductDefaultLocationRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def default_location(
    p: ProductDefaultLocationCreate, s: InventoryService = Depends(svc)
):
    try:
        return await s.create_default_location(p)
    except Exception as exc:
        h(exc)

@router.patch("/items/{item_id}", response_model=ProductItemRead, dependencies=[Depends(require_permission("inventory.manage"))])
async def update_item(item_id:int, p:ProductItemUpdate, db:AsyncSession=Depends(get_db)):
    obj=await InventoryRepository(db).get_item(item_id)
    if obj is None:
        raise HTTPException(404,"Product item not found")
    values=p.model_dump(exclude_unset=True)
    if "serial_number" in values:
        values["serial_number"]=(values["serial_number"] or "").strip() or None
    for k,v in values.items():
        setattr(obj,k,v)
    try:
        await db.commit(); await db.refresh(obj); return obj
    except Exception as exc:
        await db.rollback()
        from sqlalchemy.exc import IntegrityError
        if isinstance(exc, IntegrityError):
            raise HTTPException(409,"سریال داخلی قبلاً استفاده شده است") from exc
        raise

@router.patch("/default-locations/{row_id}", response_model=ProductDefaultLocationRead, dependencies=[Depends(require_permission("inventory.manage"))])
async def update_default_location(row_id:int,p:ProductDefaultLocationUpdate,db:AsyncSession=Depends(get_db)):
    from app.modules.inventory.model import ProductDefaultLocation
    obj=await db.get(ProductDefaultLocation,row_id)
    if obj is None: raise HTTPException(404,"Default location not found")
    vals=p.model_dump(exclude_unset=True)
    if vals.get("is_primary") is True: await InventoryRepository(db).clear_primary_default_location(obj.variant_id)
    for k,v in vals.items(): setattr(obj,k,v)
    await db.commit(); await db.refresh(obj); return obj
