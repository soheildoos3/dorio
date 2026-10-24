from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.warehouse.repository import WarehouseRepository
from app.modules.warehouse.schemas import *
from app.modules.warehouse.service import *
router = APIRouter(prefix='/warehouses', tags=['warehouses'], dependencies=[Depends(get_current_user), Depends(require_permission("warehouse.view"))])

def svc(db: AsyncSession=Depends(get_db)):
    return WarehouseService(db)

def handle(e):
    if isinstance(e, WarehouseNotFoundError):
        raise HTTPException(404, str(e))
    if isinstance(e, WarehouseConflictError):
        raise HTTPException(409, str(e))
    raise e

@router.get('', response_model=list[WarehouseRead])
async def list_warehouses(db: AsyncSession=Depends(get_db)):
    return await WarehouseRepository(db).list_warehouses()

@router.post('', response_model=WarehouseRead, status_code=201, dependencies=[Depends(require_permission("warehouse.manage"))])
async def create_warehouse(payload: WarehouseCreate, s: WarehouseService=Depends(svc)):
    try:
        return await s.create_warehouse(payload)
    except Exception as e:
        handle(e)

@router.patch('/{warehouse_id}', response_model=WarehouseRead, dependencies=[Depends(require_permission("warehouse.manage"))])
async def update_warehouse(warehouse_id: int, payload: WarehouseUpdate, s: WarehouseService=Depends(svc)):
    try:
        return await s.update_warehouse(warehouse_id, payload)
    except Exception as e:
        handle(e)

@router.delete('/{warehouse_id}', status_code=204, dependencies=[Depends(require_permission("warehouse.manage"))])
async def delete_warehouse(warehouse_id: int, s: WarehouseService=Depends(svc)):
    try:
        await s.delete_warehouse(warehouse_id)
    except Exception as e:
        handle(e)

@router.get('/{warehouse_id}/locations', response_model=list[LocationRead])
async def list_locations(warehouse_id: int, db: AsyncSession=Depends(get_db)):
    return await WarehouseRepository(db).list_locations(warehouse_id)

@router.post('/locations', response_model=LocationRead, status_code=201, dependencies=[Depends(require_permission("warehouse.manage"))])
async def create_location(payload: LocationCreate, s: WarehouseService=Depends(svc)):
    try:
        return await s.create_location(payload)
    except Exception as e:
        handle(e)

@router.delete('/locations/{location_id}', status_code=204, dependencies=[Depends(require_permission("warehouse.manage"))])
async def delete_location(location_id: int, s: WarehouseService=Depends(svc)):
    try:
        await s.delete_location(location_id)
    except Exception as e:
        handle(e)

@router.patch('/locations/{location_id}', response_model=LocationRead, dependencies=[Depends(require_permission("warehouse.manage"))])
async def update_location(location_id: int, payload: LocationUpdate, s: WarehouseService=Depends(svc)):
    try:
        return await s.update_location(location_id, payload)
    except Exception as e:
        handle(e)
