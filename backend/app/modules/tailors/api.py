from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, permission_codes, require_any_permission, require_permission
from app.modules.catalog.model import Product
from app.modules.manufacturing.model import ProductionOrder
from app.modules.tailors.model import TailorWork, TailorWorkEvent
from app.modules.tailors.schemas import MonthlyStats, TailorRead, TailorStats, WorkCreate, WorkRead, WorkReport, WorkUpdate
from app.modules.user.model import User
from app.modules.inventory_operations.numbers import next_document_number

router = APIRouter(prefix="/tailors", tags=["tailors"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TailorRead], dependencies=[Depends(require_permission("tailors.view"))])
async def list_tailors(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.user_type == "tailor", User.status == "active")
    if user.user_type == "tailor" and "tailors.manage" not in permission_codes(user) and not user.is_superuser:
        query = query.where(User.id == user.id)
    users = list((await db.execute(query.order_by(User.full_name))).scalars().all())
    return [{"id":u.id,"full_name":u.full_name,"phone":u.phone,"status":u.status,"panel_access":u.panel_access,"role_id":u.role_id} for u in users]


@router.get("/works", response_model=list[WorkRead], dependencies=[Depends(require_permission("tailors.view"))])
async def list_works(tailor_user_id: int | None = None, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(TailorWork).order_by(TailorWork.id.desc())
    if user.user_type == "tailor" and "tailors.manage" not in permission_codes(user) and not user.is_superuser:
        tailor_user_id = user.id
    if tailor_user_id is not None:
        query = query.where(TailorWork.tailor_user_id == tailor_user_id)
    return list((await db.execute(query)).scalars().all())


@router.post("/works", response_model=WorkRead, status_code=201, dependencies=[Depends(require_permission("tailors.manage"))])
async def create_work(payload: WorkCreate, db: AsyncSession = Depends(get_db)):
    if payload.production_order_id is not None:
        raise HTTPException(409, "کار مرتبط با دستور تولید باید از خود دستور تولید ساخته شود")
    tailor = await db.get(User, payload.tailor_user_id)
    if not tailor or tailor.user_type != "tailor":
        raise HTTPException(404, "خیاط انتخاب‌شده پیدا نشد")
    if tailor.status != "active":
        raise HTTPException(409, "حساب خیاط فعال نیست")
    if payload.product_id is not None and await db.get(Product, payload.product_id) is None:
        raise HTTPException(404, "محصول پیدا نشد")
    data = payload.model_dump(exclude_none=True)
    if not data.get("work_no"):
        data["work_no"] = await next_document_number(db, "TW")
    obj = TailorWork(**data)
    db.add(obj)
    try:
        await db.commit(); await db.refresh(obj); return obj
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "شماره کار تکراری است یا داده مرجع معتبر نیست") from exc


@router.patch("/works/{work_id}", response_model=WorkRead, dependencies=[Depends(require_permission("tailors.manage"))])
async def update_work(work_id: int, payload: WorkUpdate, db: AsyncSession = Depends(get_db)):
    obj = await db.get(TailorWork, work_id)
    if not obj:
        raise HTTPException(404, "کار پیدا نشد")
    values = payload.model_dump(exclude_unset=True)
    if obj.production_order_id is not None:
        protected = {"tailor_user_id", "product_id", "quantity", "due_at", "status", "completed_at"}
        if protected.intersection(values):
            raise HTTPException(409, "مشخصات این کار از دستور تولید کنترل می‌شود؛ دستور تولید را ویرایش کنید")
    if "tailor_user_id" in values:
        tailor = await db.get(User, values["tailor_user_id"])
        if not tailor or tailor.user_type != "tailor" or tailor.status != "active":
            raise HTTPException(409, "خیاط انتخاب‌شده معتبر یا فعال نیست")
    if "product_id" in values and values["product_id"] is not None and await db.get(Product, values["product_id"]) is None:
        raise HTTPException(404, "محصول پیدا نشد")
    if "quantity" in values and values["quantity"] < obj.delivered_good:
        raise HTTPException(409, "تعداد کار نمی‌تواند از تعداد سالم تحویل‌شده کمتر باشد")
    final_quantity = values.get("quantity", obj.quantity)
    if values.get("status") == "completed" and obj.delivered_good < final_quantity:
        raise HTTPException(409, "کار تا قبل از تحویل تعداد سالم کامل، قابل تکمیل نیست")
    for k,v in values.items():
        setattr(obj,k,v)
    if obj.status == "completed" and obj.completed_at is None:
        obj.completed_at = date.today()
    elif obj.status != "completed" and "status" in values:
        obj.completed_at = None
    await db.commit(); await db.refresh(obj); return obj


@router.delete("/works/{work_id}", status_code=204, dependencies=[Depends(require_permission("tailors.manage"))])
async def delete_work(work_id: int, db: AsyncSession = Depends(get_db)):
    obj = await db.get(TailorWork, work_id)
    if not obj:
        raise HTTPException(404, "کار پیدا نشد")
    if obj.production_order_id is not None:
        raise HTTPException(409, "کار متصل به دستور تولید را از خود دستور تولید حذف یا لغو کنید")
    has_event = await db.scalar(select(TailorWorkEvent.id).where(TailorWorkEvent.work_id == work_id).limit(1))
    if has_event is not None:
        raise HTTPException(409, "این کار سابقه تحویل دارد و برای حفظ تاریخچه قابل حذف نیست؛ آن را لغو کنید")
    await db.delete(obj)
    await db.commit()
    return Response(status_code=204)


@router.post("/works/{work_id}/report", response_model=WorkRead, dependencies=[Depends(require_any_permission("tailors.manage", "tailors.report"))])
async def report_work(work_id: int, payload: WorkReport, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(TailorWork)
        .options(lazyload(TailorWork.tailor))
        .where(TailorWork.id == work_id)
        .with_for_update()
    )
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "کار پیدا نشد")
    if user.user_type == "tailor" and "tailors.manage" not in permission_codes(user) and not user.is_superuser and obj.tailor_user_id != user.id:
        raise HTTPException(403, "فقط تحویل کارهای خودتان قابل ثبت است")
    if obj.status == "cancelled":
        raise HTTPException(409, "برای کار لغوشده نمی‌توان تحویل ثبت کرد")
    if obj.production_order_id is not None:
        order = await db.get(ProductionOrder, obj.production_order_id)
        if order is None:
            raise HTTPException(409, "دستور تولید مرتبط پیدا نشد")
        if order.status not in {"in_production", "waiting_qc", "rejected"}:
            raise HTTPException(409, "تحویل خیاط فقط بعد از شروع تولید و قبل از بسته‌شدن دستور قابل ثبت است")
    remaining = max(obj.quantity - obj.delivered_good, 0)
    if payload.delivered_good > remaining:
        raise HTTPException(409, "تعداد سالم تحویلی از باقیمانده تعهد بیشتر است")
    if obj.production_order_id is not None and (payload.returned_for_fix or payload.damaged):
        raise HTTPException(409, "برای کار متصل به تولید، برگشتی و خرابی از نتیجه QC به‌صورت خودکار ثبت می‌شود")
    obj.delivered_good += payload.delivered_good
    obj.returned_for_fix += payload.returned_for_fix
    obj.damaged += payload.damaged
    db.add(TailorWorkEvent(work_id=work_id, recorded_by=user.id, **payload.model_dump()))
    if obj.delivered_good >= obj.quantity:
        obj.status="completed"; obj.completed_at=date.today()
    else:
        obj.status="open"; obj.completed_at=None
    await db.commit(); await db.refresh(obj); return obj


@router.get("/stats", response_model=list[TailorStats], dependencies=[Depends(require_permission("tailors.view"))])
async def stats(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query=select(User).where(User.user_type=="tailor",User.status=="active")
    if user.user_type == "tailor" and "tailors.manage" not in permission_codes(user) and not user.is_superuser:
        query=query.where(User.id==user.id)
    tailors=(await db.execute(query)).scalars().all(); today=date.today(); result=[]
    for tailor in tailors:
        works=(await db.execute(select(TailorWork).where(TailorWork.tailor_user_id==tailor.id))).scalars().all()
        assigned=sum(w.quantity for w in works); good=sum(w.delivered_good for w in works); returned=sum(w.returned_for_fix for w in works); damaged=sum(w.damaged for w in works); inspected=good+returned+damaged
        open_work=sum(max(w.quantity-w.delivered_good,0) for w in works if w.status!="cancelled")
        overdue=sum(max(w.quantity-w.delivered_good,0) for w in works if w.status not in {"completed","cancelled"} and w.due_at and w.due_at<today)
        result.append(TailorStats(tailor_user_id=tailor.id,assigned=assigned,delivered_good=good,returned_for_fix=returned,damaged=damaged,defect_rate=round((returned+damaged)*100/inspected,2) if inspected else 0,open_work=open_work,overdue_work=overdue))
    return result


@router.get("/{tailor_user_id}/monthly", response_model=list[MonthlyStats], dependencies=[Depends(require_permission("tailors.view"))])
async def monthly(tailor_user_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    if user.user_type == "tailor" and "tailors.manage" not in permission_codes(user) and not user.is_superuser and tailor_user_id != user.id:
        raise HTTPException(403,"فقط اطلاعات خیاطی خودتان قابل مشاهده است")
    tailor=await db.get(User,tailor_user_id)
    if not tailor or tailor.user_type!="tailor": raise HTTPException(404,"خیاط پیدا نشد")
    rows=(await db.execute(select(TailorWorkEvent.recorded_at,TailorWorkEvent.delivered_good,TailorWorkEvent.returned_for_fix,TailorWorkEvent.damaged).join(TailorWork,TailorWork.id==TailorWorkEvent.work_id).where(TailorWork.tailor_user_id==tailor_user_id).order_by(TailorWorkEvent.recorded_at))).all()
    buckets={}
    for at,g,r,d in rows:
        key=at.strftime("%Y-%m"); b=buckets.setdefault(key,[0,0,0]); b[0]+=g;b[1]+=r;b[2]+=d
    return [MonthlyStats(month=m,delivered_good=g,returned_for_fix=r,damaged=d,defect_rate=round((r+d)*100/(g+r+d),2) if g+r+d else 0) for m,(g,r,d) in sorted(buckets.items())]
