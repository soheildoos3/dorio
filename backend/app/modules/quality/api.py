from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.media_storage import MediaStorageError, save_qc_image
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.warranty.model import WarrantySetting
from app.modules.warranty.urls import qr_resolver_url
from sqlalchemy import or_, select
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.model import ProductItem
from app.modules.inventory.schemas import ProductItemRead
from app.modules.quality.repository import QualityRepository
from app.modules.quality.schemas import LabelBatchCreate, LabelBatchRead, LabelCreate, LabelRead, QCRecordCreate, QCRecordRead
from app.modules.quality.printing import PrintLayout, batch_label_page, single_label_page
from app.modules.quality.service import QualityConflictError, QualityNotFoundError, QualityService

router = APIRouter(prefix="/quality", tags=["quality"], dependencies=[Depends(get_current_user), Depends(require_permission("quality.view"))])


def svc(db: AsyncSession = Depends(get_db)):
    return QualityService(db)


def h(exc: Exception):
    if isinstance(exc, QualityNotFoundError):
        raise HTTPException(404, str(exc))
    if isinstance(exc, MediaStorageError):
        raise HTTPException(400, str(exc))
    if isinstance(exc, QualityConflictError):
        raise HTTPException(409, str(exc))
    raise exc


@router.post("/items/{item_id}/photos", response_model=dict[str, str], status_code=201, dependencies=[Depends(require_permission("quality.manage"))])
async def upload_qc_photo(
    item_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await InventoryRepository(db).get_item(item_id)
        if item is None:
            raise QualityNotFoundError("Product item not found")
        url = await save_qc_image(file, item_id)
        return {"url": url}
    except Exception as exc:
        h(exc)


@router.get("/scan/{identifier}", response_model=ProductItemRead)
async def scan_item(identifier: str, db: AsyncSession = Depends(get_db)):
    value = identifier.strip()
    item = await db.scalar(
        select(ProductItem).where(
            or_(ProductItem.warranty_serial == value, ProductItem.serial_number == value)
        )
    )
    if item is None:
        raise HTTPException(404, "واحد کالا با این شناسه پیدا نشد")
    return item


@router.get("/qc-records", response_model=list[QCRecordRead])
async def all_qc_records(
    item_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await QualityRepository(db).list_qc_records(item_id, offset=offset, limit=limit)


@router.post("/qc-records", response_model=QCRecordRead, status_code=201, dependencies=[Depends(require_permission("quality.manage"))])
async def qc(p: QCRecordCreate, user=Depends(get_current_user), s: QualityService = Depends(svc)):
    try:
        return await s.record_qc(p.model_copy(update={"checked_by": user.id}))
    except Exception as exc:
        h(exc)


@router.get("/items/{item_id}/qc-records", response_model=list[QCRecordRead])
async def qc_history(item_id: int, db: AsyncSession = Depends(get_db)):
    return await QualityRepository(db).list_qc_records(item_id)


@router.get("/labels", response_model=list[LabelRead])
async def all_labels(
    item_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await QualityRepository(db).list_labels(item_id, offset=offset, limit=limit)


@router.post("/labels", response_model=LabelRead, status_code=201, dependencies=[Depends(require_permission("quality.print"))])
async def label(p: LabelCreate, user=Depends(get_current_user), s: QualityService = Depends(svc)):
    try:
        return await s.log_label(p.model_copy(update={"printed_by": user.id}))
    except Exception as exc:
        h(exc)


@router.post("/labels/batch", response_model=LabelBatchRead, status_code=201, dependencies=[Depends(require_permission("quality.print"))])
async def batch_labels(p: LabelBatchCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    flag = ProductItem.warranty_label_printed if p.label_type.value == "warranty" else ProductItem.qc_label_printed
    rows = list((await db.execute(
        select(ProductItem)
        .where(
            ProductItem.variant_id == p.variant_id,
            ProductItem.moved_out_at.is_(None),
            flag.is_(False),
        )
        .order_by(ProductItem.id.desc())
        .limit(p.limit)
        .with_for_update(skip_locked=True)
    )).scalars().all())
    if not rows:
        raise HTTPException(404, "لیبل چاپ‌نشده‌ای برای این تنوع پیدا نشد")
    service = QualityService(db)
    ids: list[int] = []
    for item in rows:
        await service.repo.create_label(item_id=item.id, label_type=p.label_type, printed_by=user.id)
        if p.label_type.value == "warranty":
            item.warranty_label_printed = True
        else:
            item.qc_label_printed = True
        ids.append(item.id)
    await db.commit()
    return {"item_ids": ids, "count": len(ids)}


@router.get("/items/{item_id}/labels", response_model=list[LabelRead])
async def labels(item_id: int, db: AsyncSession = Depends(get_db)):
    return await QualityRepository(db).list_labels(item_id)


@router.get("/print-batch", response_class=HTMLResponse, dependencies=[Depends(require_permission("quality.print"))])
async def print_batch(
    item_ids: str,
    request: Request,
    label_type: str = "warranty",
    label_width_mm: float = Query(45, ge=20, le=120),
    label_height_mm: float = Query(50, ge=20, le=150),
    qr_size_mm: float = Query(27, ge=12, le=100),
    columns: int = Query(4, ge=1, le=10),
    gap_x_mm: float = Query(2, ge=0, le=20),
    gap_y_mm: float = Query(2, ge=0, le=20),
    margin_mm: float = Query(8, ge=0, le=30),
    page_size: str = Query("A4", pattern="^(A4|A5|a4|a5)$"),
    landscape: bool = False,
    show_title: bool = True,
    show_serial: bool = True,
    db: AsyncSession = Depends(get_db),
):
    if label_type not in {"qc", "warranty"}:
        raise HTTPException(400, "Unsupported label type")
    try:
        ids = [int(x) for x in item_ids.split(",") if x.strip()]
    except ValueError as exc:
        raise HTTPException(400, "Invalid item_ids") from exc
    if not ids or len(ids) > 200:
        raise HTTPException(400, "Batch must contain between 1 and 200 items")
    items = list((await db.execute(select(ProductItem).where(ProductItem.id.in_(ids)))).scalars().all())
    by_id = {item.id: item for item in items}
    if len(by_id) != len(set(ids)):
        raise HTTPException(404, "One or more items were not found")
    setting = (await db.execute(select(WarrantySetting).where(WarrantySetting.is_default.is_(True)).order_by(WarrantySetting.id.desc()))).scalars().first()
    rows: list[tuple[str, str]] = []
    for item_id in ids:
        item = by_id[item_id]
        serial = item.warranty_serial or item.serial_number
        if not serial:
            continue
        rows.append((serial, qr_resolver_url(serial, setting.qr_base_url if setting else None, str(request.base_url))))
    if not rows:
        raise HTTPException(409, "هیچ شناسه قابل چاپی در این گروه وجود ندارد")
    layout = PrintLayout(
        label_width_mm=label_width_mm,
        label_height_mm=label_height_mm,
        qr_size_mm=qr_size_mm,
        columns=columns,
        gap_x_mm=gap_x_mm,
        gap_y_mm=gap_y_mm,
        margin_mm=margin_mm,
        page_size=page_size.upper(),
        landscape=landscape,
        show_title=show_title,
        show_serial=show_serial,
    )
    try:
        page = batch_label_page(rows, layout)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return HTMLResponse(page)


@router.get("/items/{item_id}/print", response_class=HTMLResponse, dependencies=[Depends(require_permission("quality.print"))])
async def print_label(
    item_id: int,
    request: Request,
    label_type: str = "qc",
    label_width_mm: float = Query(45, ge=20, le=120),
    label_height_mm: float = Query(50, ge=20, le=150),
    qr_size_mm: float = Query(27, ge=12, le=100),
    show_title: bool = True,
    show_serial: bool = True,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    item = await InventoryRepository(db).get_item(item_id)
    if item is None:
        raise HTTPException(404, "Product item not found")
    if label_type not in {"qc", "warranty"}:
        raise HTTPException(400, "Unsupported label type")
    serial = item.warranty_serial or item.serial_number
    if not serial:
        raise HTTPException(409, "This legacy item has no printable identifier")
    setting = (await db.execute(select(WarrantySetting).where(WarrantySetting.is_default.is_(True)).order_by(WarrantySetting.id.desc()))).scalars().first()
    url = qr_resolver_url(serial, setting.qr_base_url if setting else None, str(request.base_url))
    try:
        page = single_label_page(
            serial,
            url,
            label_width_mm=label_width_mm,
            label_height_mm=label_height_mm,
            qr_size_mm=qr_size_mm,
            show_title=show_title,
            show_serial=show_serial,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return HTMLResponse(page)

