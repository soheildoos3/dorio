from datetime import datetime, timezone
import html

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.inventory.model import ProductItem
from app.modules.quality.constants import LabelType
from app.modules.quality.schemas import LabelCreate
from app.modules.quality.printing import single_label_page
from app.modules.quality.service import QualityConflictError, QualityNotFoundError, QualityService
from app.modules.warranty.model import WarrantyRecord, WarrantySetting
from app.modules.warranty.schemas import (
    PublicWarrantyActivate,
    PublicWarrantyRead,
    SettingCreate,
    SettingRead,
    SettingUpdate,
    WarrantyCreate,
    WarrantyRead,
    WarrantyUpdate,
)
from app.modules.warranty.service import WarrantyConflictError, WarrantyService, add_months
from app.modules.warranty.urls import dynamic_qr_destination, qr_resolver_url, resolve_warranty_base


router = APIRouter(
    prefix="/warranty",
    tags=["warranty"],
    dependencies=[Depends(get_current_user)],
)
public_router = APIRouter(tags=["warranty-public"])


async def _clear_default(db: AsyncSession, excluding_id: int | None = None) -> None:
    stmt = update(WarrantySetting).values(is_default=False)
    if excluding_id is not None:
        stmt = stmt.where(WarrantySetting.id != excluding_id)
    await db.execute(stmt)


@router.get("/settings", response_model=list[SettingRead], dependencies=[Depends(require_permission("warranty.view"))])
async def list_settings(db: AsyncSession = Depends(get_db)):
    return list((await db.execute(select(WarrantySetting).order_by(WarrantySetting.id.desc()))).scalars().all())


@router.post("/settings", response_model=SettingRead, status_code=201, dependencies=[Depends(require_permission("warranty.manage"))])
async def create_setting(payload: SettingCreate, db: AsyncSession = Depends(get_db)):
    if payload.is_default:
        await _clear_default(db)
    obj = WarrantySetting(**payload.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.patch("/settings/{setting_id}", response_model=SettingRead, dependencies=[Depends(require_permission("warranty.manage"))])
async def update_setting(setting_id: int, payload: SettingUpdate, db: AsyncSession = Depends(get_db)):
    obj = await db.get(WarrantySetting, setting_id)
    if obj is None:
        raise HTTPException(404, "Warranty setting not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("is_default") is True:
        await _clear_default(db, excluding_id=obj.id)
    for key, value in values.items():
        setattr(obj, key, value)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("", response_model=list[WarrantyRead], dependencies=[Depends(require_permission("warranty.view"))])
async def list_warranties(db: AsyncSession = Depends(get_db)):
    rows = list((await db.execute(select(WarrantyRecord).order_by(WarrantyRecord.id.desc()))).scalars().all())
    service = WarrantyService(db)
    changed = False
    before = [(x.status, x.activated_at, x.expires_at) for x in rows]
    for row in rows:
        await service.refresh_record(row)
    after = [(x.status, x.activated_at, x.expires_at) for x in rows]
    changed = before != after
    if changed:
        await db.commit()
    return rows


@router.post("", response_model=WarrantyRead, status_code=201, dependencies=[Depends(require_permission("warranty.manage"))])
async def create_warranty(payload: WarrantyCreate, db: AsyncSession = Depends(get_db)):
    item = await db.get(ProductItem, payload.item_id)
    if item is None:
        raise HTTPException(404, "Product item not found")
    service = WarrantyService(db)
    try:
        obj = await service.ensure_for_item(item)
        if payload.customer_name is not None:
            obj.customer_name = payload.customer_name.strip() or None
        if payload.customer_phone is not None:
            obj.customer_phone = payload.customer_phone.strip() or None
        if payload.notes is not None:
            obj.notes = payload.notes
        await service.refresh_record(obj)
        await db.commit()
        await db.refresh(obj)
        return obj
    except (IntegrityError, WarrantyConflictError) as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.patch("/{warranty_id}", response_model=WarrantyRead, dependencies=[Depends(require_permission("warranty.manage"))])
async def update_warranty(warranty_id: int, payload: WarrantyUpdate, db: AsyncSession = Depends(get_db)):
    obj = await db.get(WarrantyRecord, warranty_id)
    if obj is None:
        raise HTTPException(404, "Warranty not found")
    values = payload.model_dump(exclude_unset=True)
    requested_status = values.pop("status", None)
    warranty_months_changed = "warranty_months" in values
    explicit_expires_at = "expires_at" in values
    if warranty_months_changed:
        # Apply duration before an activation request so the newly calculated expiry
        # always uses the administrator's latest warranty duration.
        obj.warranty_months = values.pop("warranty_months")
    service = WarrantyService(db)
    try:
        if requested_status == "active" and obj.activated_at is None:
            await service.activate(obj, source="admin")
        elif requested_status == "void":
            obj.status = "void"
        elif requested_status in {"inactive", "grace"} and obj.activated_at is None:
            obj.status = requested_status
        elif requested_status == "expired":
            obj.status = "expired"
        for key, value in values.items():
            setattr(obj, key, value)
        if warranty_months_changed and obj.activated_at and not explicit_expires_at:
            obj.expires_at = add_months(obj.activated_at, obj.warranty_months)
        if obj.activated_at and obj.expires_at and obj.expires_at <= obj.activated_at:
            raise WarrantyConflictError("Warranty expiry must be after activation")
        await service.refresh_record(obj)
        await db.commit()
        await db.refresh(obj)
        return obj
    except WarrantyConflictError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.get("/by-serial/{serial}", response_model=WarrantyRead, dependencies=[Depends(require_permission("warranty.view"))])
async def warranty_by_serial(serial: str, db: AsyncSession = Depends(get_db)):
    obj = await WarrantyService(db).get_by_serial(serial)
    if obj is None:
        raise HTTPException(404, "گارانتی پیدا نشد")
    await WarrantyService(db).refresh_record(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.post("/by-serial/{serial}/activate", response_model=WarrantyRead, dependencies=[Depends(require_permission("warranty.manage"))])
async def activate_warranty_by_serial(serial: str, db: AsyncSession = Depends(get_db)):
    service = WarrantyService(db)
    obj = await service.get_by_serial(serial, for_update=True)
    if obj is None:
        raise HTTPException(404, "گارانتی پیدا نشد")
    try:
        await service.activate(obj, source="admin")
        await db.commit()
        await db.refresh(obj)
        return obj
    except WarrantyConflictError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.post("/{warranty_id}/activate", response_model=WarrantyRead, dependencies=[Depends(require_permission("warranty.manage"))])
async def activate_warranty(warranty_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(WarrantyRecord, warranty_id)
    if obj is None:
        raise HTTPException(404, "Warranty not found")
    try:
        await WarrantyService(db).activate(obj, source="admin")
        await db.commit()
        await db.refresh(obj)
        return obj
    except WarrantyConflictError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.post("/refresh/due", response_model=dict[str, int], dependencies=[Depends(require_permission("warranty.manage"))])
async def refresh_due_warranties(db: AsyncSession = Depends(get_db)):
    return {"activated": await WarrantyService(db).refresh_due()}


@router.post("/{warranty_id}/print-log", status_code=201, dependencies=[Depends(require_permission("warranty.manage"))])
async def log_warranty_print(
    warranty_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    obj = await db.get(WarrantyRecord, warranty_id)
    if obj is None:
        raise HTTPException(404, "Warranty not found")
    try:
        label = await QualityService(db).log_label(
            LabelCreate(item_id=obj.item_id, label_type=LabelType.WARRANTY, printed_by=user.id)
        )
        return {"id": label.id, "printed_at": label.printed_at}
    except QualityNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except QualityConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{warranty_id}/print", response_class=HTMLResponse, dependencies=[Depends(require_permission("warranty.view"))])
async def print_warranty(
    warranty_id: int,
    request: Request,
    label_width_mm: float = Query(45, ge=20, le=120),
    label_height_mm: float = Query(50, ge=20, le=150),
    qr_size_mm: float = Query(27, ge=12, le=100),
    show_title: bool = True,
    show_serial: bool = True,
    db: AsyncSession = Depends(get_db),
):
    obj = await db.get(WarrantyRecord, warranty_id)
    if obj is None:
        raise HTTPException(404, "Warranty not found")
    setting = (await db.execute(select(WarrantySetting).where(WarrantySetting.is_default.is_(True)).order_by(WarrantySetting.id.desc()))).scalars().first()
    qr_url = qr_resolver_url(obj.serial, setting.qr_base_url if setting else None, str(request.base_url))
    try:
        page = single_label_page(
            obj.serial,
            qr_url,
            label_width_mm=label_width_mm,
            label_height_mm=label_height_mm,
            qr_size_mm=qr_size_mm,
            show_title=show_title,
            show_serial=show_serial,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return HTMLResponse(page)


@public_router.get("/q/{serial}", include_in_schema=False)
async def dynamic_qr_resolver(serial: str, request: Request, db: AsyncSession = Depends(get_db)):
    service = WarrantyService(db)
    obj = await service.get_by_serial(serial)
    if obj is None:
        return HTMLResponse(
            "<html dir='rtl'><meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>"
            "<h2>شناسه پیدا نشد</h2><p>این سریال در سیستم Dario ثبت نشده است.</p></body></html>",
            status_code=404,
        )
    if obj.qr_redirect_url:
        destination = obj.qr_redirect_url
    else:
        setting = (await db.execute(select(WarrantySetting).where(WarrantySetting.is_default.is_(True)).order_by(WarrantySetting.id.desc()))).scalars().first()
        if setting is None:
            destination = f"{str(request.base_url).rstrip('/')}/warranty/{serial}"
        else:
            destination = dynamic_qr_destination(serial, setting.base_url, setting.qr_destination_template, str(request.base_url))
    return RedirectResponse(destination, status_code=307)


@public_router.get("/api/public/warranty/{serial}", response_model=PublicWarrantyRead)
async def public_warranty_json(serial: str, db: AsyncSession = Depends(get_db)):
    service = WarrantyService(db)
    obj = await service.get_by_serial(serial)
    if obj is None:
        raise HTTPException(404, "این شماره گارانتی در سیستم ثبت نشده است")
    payload = await service.public_payload(obj)
    await db.commit()
    return payload


@public_router.post("/api/public/warranty/{serial}/activate", response_model=PublicWarrantyRead)
async def public_warranty_activate(serial: str, payload: PublicWarrantyActivate, db: AsyncSession = Depends(get_db)):
    service = WarrantyService(db)
    obj = await service.get_by_serial(serial, for_update=True)
    if obj is None:
        raise HTTPException(404, "این شماره گارانتی در سیستم ثبت نشده است")
    try:
        await service.activate(
            obj,
            source="customer",
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
        )
        result = await service.public_payload(obj)
        await db.commit()
        return result
    except WarrantyConflictError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from exc


@public_router.get("/warranty/{serial}", response_class=HTMLResponse)
async def legacy_public_warranty(serial: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Compatibility page for QR codes printed by older releases."""
    service = WarrantyService(db)
    obj = await service.get_by_serial(serial)
    if obj is None:
        return HTMLResponse(
            "<html dir='rtl'><meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>"
            "<h2>گارانتی یافت نشد</h2><p>این سریال در سیستم Dario ثبت نشده است.</p></body></html>",
            status_code=404,
        )
    data = await service.public_payload(obj)
    await db.commit()
    status_text = {
        "inactive": "در انبار / غیرفعال",
        "grace": "در مهلت فعال‌سازی",
        "active": "فعال",
        "expired": "منقضی",
        "void": "باطل",
    }.get(data["status"], data["status"])
    configured = await service.base_url()
    react_url = f"{resolve_warranty_base(configured, str(request.base_url))}/{html.escape(serial)}"
    return HTMLResponse(
        f"""<!doctype html><html dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
        <title>گارانتی Dario</title><style>body{{font-family:Tahoma,sans-serif;background:#f8fafc;margin:0;padding:24px;color:#0f172a}}.card{{max-width:520px;margin:40px auto;background:#fff;padding:24px;border-radius:22px;box-shadow:0 12px 35px #0f172a18}}a{{display:block;margin-top:20px;background:#0f172a;color:#fff;padding:12px;border-radius:12px;text-align:center;text-decoration:none}}</style></head>
        <body><div class='card'><h2>گارانتی Dario</h2><p>شماره: <b dir='ltr'>{html.escape(serial)}</b></p><p>وضعیت: <b>{html.escape(status_text)}</b></p><a href='{react_url}'>باز کردن صفحه جدید گارانتی</a></div></body></html>"""
    )
