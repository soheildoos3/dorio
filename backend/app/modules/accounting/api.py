from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.accounting.model import Account, AuditEvent, CostCenter, JournalEntry, JournalLine
from app.modules.accounting.schemas import AccountCreate, AccountRead, AccountUpdate, AuditRead, CostCenterCreate, CostCenterRead, CostCenterUpdate, InventoryImpairmentCreate, JournalCreate, JournalRead, OverheadVarianceCreate
from app.modules.accounting.service import AccountingError, AccountingService
from app.modules.auth.dependencies import get_current_user, require_permission

router = APIRouter(prefix="/accounting", tags=["accounting"], dependencies=[Depends(get_current_user), Depends(require_permission("accounting.view"))])


def fail(exc: Exception):
    if isinstance(exc, AccountingError):
        raise HTTPException(409, str(exc))
    raise exc


@router.post("/bootstrap", dependencies=[Depends(require_permission("accounting.manage"))])
async def bootstrap(db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    await service.ensure_defaults()
    await db.commit()
    return {"ok": True}


@router.get("/accounts", response_model=list[AccountRead])
async def accounts(db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    await service.ensure_defaults(); await db.commit()
    return list((await db.scalars(select(Account).order_by(Account.code))).all())


@router.post("/accounts", response_model=AccountRead, status_code=201, dependencies=[Depends(require_permission("accounting.manage"))])
async def create_account(p: AccountCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if p.parent_id is not None:
        parent = await db.get(Account, p.parent_id)
        if parent is None:
            raise HTTPException(400, "حساب والد پیدا نشد")
        if parent.account_type != p.account_type:
            raise HTTPException(409, "نوع حساب والد باید با نوع حساب جدید یکسان باشد")
    obj = Account(**p.model_dump(), is_system=False)
    db.add(obj)
    try:
        await db.flush()
        await AccountingService(db).log_audit(user_id=user.id, action="account.create", entity_type="account", entity_id=obj.id, source_ref=obj.code, after_data=p.model_dump(mode="json"))
        await db.commit(); await db.refresh(obj); return obj
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "کد حساب تکراری است") from exc


@router.patch("/accounts/{account_id}", response_model=AccountRead, dependencies=[Depends(require_permission("accounting.manage"))])
async def update_account(account_id: int, p: AccountUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    obj = await db.get(Account, account_id)
    if not obj:
        raise HTTPException(404, "حساب پیدا نشد")
    if obj.is_system:
        raise HTTPException(409, "حساب سیستمی قابل ویرایش نیست")
    data = p.model_dump(exclude_unset=True)
    if "parent_id" in data:
        parent_id = data["parent_id"]
        if parent_id == obj.id:
            raise HTTPException(400, "حساب نمی‌تواند والد خودش باشد")
        if parent_id is not None:
            parent = await db.get(Account, parent_id)
            if parent is None:
                raise HTTPException(400, "حساب والد پیدا نشد")
            if parent.account_type != obj.account_type:
                raise HTTPException(409, "نوع حساب والد باید با نوع این حساب یکسان باشد")
            cursor = parent
            while cursor.parent_id is not None:
                if cursor.parent_id == obj.id:
                    raise HTTPException(409, "این تغییر درخت حساب‌ها را حلقه‌ای می‌کند")
                cursor = await db.get(Account, cursor.parent_id)
                if cursor is None:
                    break
    before = {"name": obj.name, "parent_id": obj.parent_id, "allow_posting": obj.allow_posting, "is_active": obj.is_active}
    for key, value in data.items():
        setattr(obj, key, value)
    await AccountingService(db).log_audit(user_id=user.id, action="account.update", entity_type="account", entity_id=obj.id, source_ref=obj.code, before_data=before, after_data=data)
    await db.commit(); await db.refresh(obj); return obj


@router.delete("/accounts/{account_id}", status_code=204, dependencies=[Depends(require_permission("accounting.manage"))])
async def delete_account(account_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    obj = await db.get(Account, account_id)
    if not obj:
        raise HTTPException(404, "حساب پیدا نشد")
    if obj.is_system:
        raise HTTPException(409, "حساب سیستمی قابل حذف نیست")
    used = await db.scalar(select(JournalLine.id).where(JournalLine.account_id == account_id).limit(1))
    child = await db.scalar(select(Account.id).where(Account.parent_id == account_id).limit(1))
    if used or child:
        raise HTTPException(409, "این حساب سابقه یا زیرحساب دارد و حذف آن امن نیست؛ آن را غیرفعال کنید")
    code = obj.code
    await db.delete(obj)
    await AccountingService(db).log_audit(user_id=user.id, action="account.delete", entity_type="account", entity_id=account_id, source_ref=code, before_data={"code": code, "name": obj.name})
    await db.commit()


@router.get("/cost-centers", response_model=list[CostCenterRead])
async def cost_centers(db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    await service.ensure_defaults(); await db.commit()
    return list((await db.scalars(select(CostCenter).order_by(CostCenter.code))).all())


@router.post("/cost-centers", response_model=CostCenterRead, status_code=201, dependencies=[Depends(require_permission("accounting.manage"))])
async def create_cost_center(p: CostCenterCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    obj = CostCenter(**p.model_dump()); db.add(obj)
    try:
        await db.flush(); await AccountingService(db).log_audit(user_id=user.id, action="cost_center.create", entity_type="cost_center", entity_id=obj.id, source_ref=obj.code, after_data=p.model_dump(mode="json")); await db.commit(); await db.refresh(obj); return obj
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "کد مرکز هزینه تکراری است") from exc


@router.patch("/cost-centers/{center_id}", response_model=CostCenterRead, dependencies=[Depends(require_permission("accounting.manage"))])
async def update_cost_center(center_id: int, p: CostCenterUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    obj = await db.get(CostCenter, center_id)
    if not obj:
        raise HTTPException(404, "مرکز هزینه پیدا نشد")
    data = p.model_dump(exclude_unset=True)
    before = {"name": obj.name, "center_type": obj.center_type, "is_active": obj.is_active}
    for key, value in data.items():
        setattr(obj, key, value)
    await AccountingService(db).log_audit(user_id=user.id, action="cost_center.update", entity_type="cost_center", entity_id=obj.id, source_ref=obj.code, before_data=before, after_data=data)
    await db.commit(); await db.refresh(obj); return obj


@router.delete("/cost-centers/{center_id}", status_code=204, dependencies=[Depends(require_permission("accounting.manage"))])
async def delete_cost_center(center_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    obj = await db.get(CostCenter, center_id)
    if not obj:
        raise HTTPException(404, "مرکز هزینه پیدا نشد")
    if obj.code in {"PROD", "RAW", "FG", "SALES", "ADMIN"}:
        raise HTTPException(409, "مرکز هزینه سیستمی قابل حذف نیست")
    used = await db.scalar(select(JournalLine.id).where(JournalLine.cost_center_id == center_id).limit(1))
    if used:
        raise HTTPException(409, "این مرکز هزینه در اسناد استفاده شده و حذف آن امن نیست؛ آن را غیرفعال کنید")
    code = obj.code
    await db.delete(obj)
    await AccountingService(db).log_audit(user_id=user.id, action="cost_center.delete", entity_type="cost_center", entity_id=center_id, source_ref=code, before_data={"code": code, "name": obj.name})
    await db.commit()


@router.get("/journals", response_model=list[JournalRead])
async def journals(offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    rows = list((await db.execute(select(JournalEntry).order_by(JournalEntry.id.desc()).offset(offset).limit(limit))).scalars().unique().all())
    return rows


@router.post("/journals", response_model=JournalRead, status_code=201, dependencies=[Depends(require_permission("accounting.post"))])
async def post_journal(p: JournalCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await AccountingService(db).create_draft(p, user.id)
    except Exception as exc:
        fail(exc)


@router.post("/journals/{entry_id}/post", response_model=JournalRead, dependencies=[Depends(require_permission("accounting.post"))])
async def finalize_journal(entry_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await AccountingService(db).finalize(entry_id, user.id)
    except Exception as exc:
        fail(exc)


@router.post("/journals/{entry_id}/reverse", response_model=JournalRead, dependencies=[Depends(require_permission("accounting.post"))])
async def reverse(entry_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await AccountingService(db).reverse(entry_id, user.id)
    except Exception as exc:
        fail(exc)


def _date_filters(date_from: date | None, date_to: date | None):
    filters = []
    if date_from is not None:
        filters.append(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        filters.append(JournalEntry.entry_date <= date_to)
    return filters


@router.get("/reports/trial-balance")
async def trial_balance(date_from: date | None = None, date_to: date | None = None, db: AsyncSession = Depends(get_db)):
    activity = (
        select(
            JournalLine.account_id.label("account_id"),
            func.sum(JournalLine.debit).label("debit"),
            func.sum(JournalLine.credit).label("credit"),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalEntry.status.in_(["posted", "reversed"]), *_date_filters(date_from, date_to))
        .group_by(JournalLine.account_id)
        .subquery()
    )
    rows = (await db.execute(
        select(
            Account.id, Account.code, Account.name, Account.account_type,
            func.coalesce(activity.c.debit, 0).label("debit"),
            func.coalesce(activity.c.credit, 0).label("credit"),
        )
        .outerjoin(activity, activity.c.account_id == Account.id)
        .where(Account.allow_posting.is_(True))
        .order_by(Account.code)
    )).all()
    return [{
        "account_id": r.id, "code": r.code, "name": r.name, "account_type": r.account_type,
        "debit": r.debit, "credit": r.credit, "balance": Decimal(r.debit or 0) - Decimal(r.credit or 0),
    } for r in rows]


@router.get("/reports/financial-statements")
async def financial_statements(date_from: date | None = None, date_to: date | None = None, db: AsyncSession = Depends(get_db)):
    trial = await trial_balance(date_from=date_from, date_to=date_to, db=db)
    revenue = sum((-Decimal(x["balance"]) for x in trial if x["account_type"] == "revenue"), Decimal("0"))
    expense = sum((Decimal(x["balance"]) for x in trial if x["account_type"] == "expense"), Decimal("0"))
    assets = sum((Decimal(x["balance"]) for x in trial if x["account_type"] == "asset"), Decimal("0"))
    liabilities = sum((-Decimal(x["balance"]) for x in trial if x["account_type"] == "liability"), Decimal("0"))
    equity = sum((-Decimal(x["balance"]) for x in trial if x["account_type"] == "equity"), Decimal("0"))
    return {
        "date_from": date_from, "date_to": date_to,
        "profit_and_loss": {"revenue": revenue, "expense": expense, "net_profit": revenue - expense},
        "balance_sheet": {"assets": assets, "liabilities": liabilities, "equity": equity, "check": assets - liabilities - equity},
    }


@router.post("/period-adjustments/inventory-impairment", response_model=JournalRead, status_code=201, dependencies=[Depends(require_permission("accounting.post"))])
async def inventory_impairment(p: InventoryImpairmentCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await AccountingService(db).create_inventory_impairment_draft(p, user.id)
    except Exception as exc:
        fail(exc)


@router.post("/period-adjustments/overhead-variance", response_model=JournalRead, status_code=201, dependencies=[Depends(require_permission("accounting.post"))])
async def overhead_variance(p: OverheadVarianceCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await AccountingService(db).create_overhead_variance_draft(p, user.id)
    except Exception as exc:
        fail(exc)


@router.get("/audit", response_model=list[AuditRead], dependencies=[Depends(require_permission("audit.view"))])
async def audit(offset: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=2000), entity_type: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).offset(offset).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    return list((await db.scalars(stmt)).all())
