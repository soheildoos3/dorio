from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.inventory_operations.repository import InventoryOperationsRepository
from app.modules.inventory_operations.schemas import *
from app.modules.inventory_operations.service import *

router = APIRouter(prefix="/inventory-operations", tags=["inventory-operations"], dependencies=[Depends(get_current_user), Depends(require_permission("inventory.view"))])


def svc(db: AsyncSession = Depends(get_db)):
    return InventoryOperationsService(db)


def h(e):
    if isinstance(e, OperationNotFoundError):
        raise HTTPException(404, str(e))
    if isinstance(e, OperationConflictError):
        raise HTTPException(409, str(e))
    raise e


@router.get("/transfers", response_model=list[StockTransferRead])
async def transfers(db: AsyncSession = Depends(get_db)):
    return await InventoryOperationsRepository(db).list_transfers()


@router.post("/transfers", response_model=StockTransferRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def create_transfer(
    p: StockTransferCreate, user=Depends(get_current_user), s: InventoryOperationsService = Depends(svc)
):
    try:
        return await s.create_transfer(p.model_copy(update={"requested_by": user.id}))
    except Exception as e:
        h(e)


@router.post("/transfers/{transfer_id}/complete", response_model=StockTransferRead, dependencies=[Depends(require_permission("inventory.manage"))])
async def complete_transfer(
    transfer_id: int, user=Depends(get_current_user), s: InventoryOperationsService = Depends(svc)
):
    try:
        return await s.complete_transfer(transfer_id, user.id)
    except Exception as e:
        h(e)


@router.get("/adjustments", response_model=list[StockAdjustmentRead])
async def adjustments(
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryOperationsRepository(db).list_adjustments(offset=offset, limit=limit)


@router.post("/adjustments", response_model=StockAdjustmentRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def adjustment(
    p: StockAdjustmentCreate, user=Depends(get_current_user), s: InventoryOperationsService = Depends(svc)
):
    try:
        return await s.create_adjustment(p.model_copy(update={"created_by": user.id, "approved_by": p.approved_by or user.id}))
    except Exception as e:
        h(e)


@router.get("/cycle-counts", response_model=list[CycleCountRead])
async def cycle_counts(
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryOperationsRepository(db).list_cycle_counts(offset=offset, limit=limit)


@router.post("/cycle-counts", response_model=CycleCountRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def cycle_count(
    p: CycleCountCreate, user=Depends(get_current_user), s: InventoryOperationsService = Depends(svc)
):
    try:
        return await s.create_cycle_count(p.model_copy(update={"created_by": user.id}))
    except Exception as e:
        h(e)


@router.post("/cycle-count-lines", response_model=CycleCountLineRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def cycle_line(
    p: CycleCountLineCreate, s: InventoryOperationsService = Depends(svc)
):
    try:
        return await s.add_cycle_line(p)
    except Exception as e:
        h(e)


@router.get("/cycle-counts/{count_id}/lines", response_model=list[CycleCountLineRead])
async def lines(count_id: int, db: AsyncSession = Depends(get_db)):
    return await InventoryOperationsRepository(db).list_cycle_lines(count_id)


@router.get("/openings", response_model=list[StockOpeningRead])
async def openings(
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryOperationsRepository(db).list_openings(offset=offset, limit=limit)


@router.post("/openings", response_model=StockOpeningRead, status_code=201, dependencies=[Depends(require_permission("inventory.manage"))])
async def opening(p: StockOpeningCreate, user=Depends(get_current_user), s: InventoryOperationsService = Depends(svc)):
    try:
        return await s.create_opening(p.model_copy(update={"recorded_by": user.id}))
    except Exception as e:
        h(e)
