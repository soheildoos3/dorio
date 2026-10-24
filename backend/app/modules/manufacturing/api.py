from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.manufacturing.model import BOM, LaborEntry, Material, MaterialMovement, MaterialStock, OverheadRate, ProductionOrder
from app.modules.manufacturing.schemas import BOMCreate, BOMRead, BOMUpdate, IssueBOMRequest, LaborCreate, LaborRead, LaborUpdate, MaterialAdjustment, MaterialCreate, MaterialIssue, MaterialMovementRead, MaterialPurchase, MaterialRead, MaterialStockRead, MaterialUpdate, OverheadRateCreate, OverheadRateRead, OverheadRateUpdate, PrepareQCRequest, ProductionOrderCreate, ProductionOrderRead, ProductionOrderUpdate, ProductionStatusUpdate
from app.modules.manufacturing.service import ManufacturingError, ManufacturingService

router=APIRouter(prefix="/manufacturing",tags=["manufacturing"],dependencies=[Depends(get_current_user),Depends(require_permission("manufacturing.view"))])


def fail(exc:Exception,db:AsyncSession):
    if isinstance(exc,ManufacturingError): raise HTTPException(409,str(exc))
    raise exc


@router.get("/materials",response_model=list[MaterialRead])
async def materials(db:AsyncSession=Depends(get_db)): return list((await db.scalars(select(Material).order_by(Material.code))).all())

@router.post("/materials",response_model=MaterialRead,status_code=201,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def create_material(p:MaterialCreate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).create_material(p,user.id)
    except Exception as e:fail(e,db)

@router.patch("/materials/{material_id}",response_model=MaterialRead,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def update_material(material_id:int,p:MaterialUpdate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).update_material(material_id,p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.delete("/materials/{material_id}",status_code=204,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def delete_material(material_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:await ManufacturingService(db).delete_material(material_id,user.id);return Response(status_code=204)
    except Exception as e:await db.rollback();fail(e,db)

@router.get("/material-stock",response_model=list[MaterialStockRead])
async def material_stock(material_id:int|None=None,db:AsyncSession=Depends(get_db)):
    stmt=select(MaterialStock).order_by(MaterialStock.material_id,MaterialStock.location_id)
    if material_id is not None:stmt=stmt.where(MaterialStock.material_id==material_id)
    return list((await db.execute(stmt)).scalars().unique().all())

@router.get("/material-movements",response_model=list[MaterialMovementRead])
async def material_movements(offset:int=Query(0,ge=0),limit:int=Query(500,ge=1,le=2000),db:AsyncSession=Depends(get_db)):
    return list((await db.execute(select(MaterialMovement).order_by(MaterialMovement.id.desc()).offset(offset).limit(limit))).scalars().unique().all())

@router.post("/materials/purchase",response_model=MaterialMovementRead,status_code=201,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def purchase(p:MaterialPurchase,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).purchase(p,user.id)
    except Exception as e: await db.rollback();fail(e,db)

@router.post("/materials/issue",response_model=MaterialMovementRead,status_code=201,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def issue(p:MaterialIssue,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).issue(p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.post("/materials/return",response_model=MaterialMovementRead,status_code=201,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def return_material(p:MaterialIssue,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).return_material(p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.post("/materials/adjust",response_model=MaterialMovementRead,status_code=201,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def adjust(p:MaterialAdjustment,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).adjust(p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.get("/boms",response_model=list[BOMRead])
async def boms(product_id:int|None=None,db:AsyncSession=Depends(get_db)):
    stmt=select(BOM).order_by(BOM.product_id,BOM.version.desc())
    if product_id is not None:stmt=stmt.where(BOM.product_id==product_id)
    return list((await db.execute(stmt)).scalars().unique().all())

@router.post("/boms",response_model=BOMRead,status_code=201,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def create_bom(p:BOMCreate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).create_bom(p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.patch("/boms/{bom_id}",response_model=BOMRead,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def update_bom(bom_id:int,p:BOMUpdate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).update_bom(bom_id,p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.delete("/boms/{bom_id}",status_code=204,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def delete_bom(bom_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:await ManufacturingService(db).delete_bom(bom_id,user.id);return Response(status_code=204)
    except Exception as e:await db.rollback();fail(e,db)

@router.get("/orders",response_model=list[ProductionOrderRead])
async def orders(status:str|None=None,db:AsyncSession=Depends(get_db)):
    stmt=select(ProductionOrder).order_by(ProductionOrder.id.desc())
    if status:stmt=stmt.where(ProductionOrder.status==status)
    return list((await db.scalars(stmt)).all())

@router.post("/orders",response_model=ProductionOrderRead,status_code=201,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def create_order(p:ProductionOrderCreate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).create_order(p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.patch("/orders/{order_id}",response_model=ProductionOrderRead,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def update_order(order_id:int,p:ProductionOrderUpdate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).update_order(order_id,p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.delete("/orders/{order_id}",status_code=204,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def delete_order(order_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:await ManufacturingService(db).delete_order(order_id,user.id);return Response(status_code=204)
    except Exception as e:await db.rollback();fail(e,db)

@router.post("/orders/{order_id}/issue-bom",response_model=ProductionOrderRead,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def issue_bom(order_id:int,p:IssueBOMRequest,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).issue_bom(order_id,p.location_id,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.patch("/orders/{order_id}/status",response_model=ProductionOrderRead,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def status(order_id:int,p:ProductionStatusUpdate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).update_status(order_id,p.status,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.post("/orders/{order_id}/prepare-qc",response_model=ProductionOrderRead,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def prepare_qc(order_id:int,p:PrepareQCRequest,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).prepare_qc(order_id,p.location_id,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.get("/labor",response_model=list[LaborRead])
async def labor(order_id:int|None=None,db:AsyncSession=Depends(get_db)):
    stmt=select(LaborEntry).order_by(LaborEntry.id.desc())
    if order_id is not None:stmt=stmt.where(LaborEntry.production_order_id==order_id)
    return list((await db.scalars(stmt)).all())

@router.post("/labor",response_model=LaborRead,status_code=201,dependencies=[Depends(require_permission("labor.manage"))])
async def create_labor(p:LaborCreate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).create_labor(p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.patch("/labor/{labor_id}",response_model=LaborRead,dependencies=[Depends(require_permission("labor.manage"))])
async def update_labor(labor_id:int,p:LaborUpdate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).update_labor(labor_id,p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.delete("/labor/{labor_id}",status_code=204,dependencies=[Depends(require_permission("labor.manage"))])
async def delete_labor(labor_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:await ManufacturingService(db).delete_labor(labor_id,user.id);return Response(status_code=204)
    except Exception as e:await db.rollback();fail(e,db)

@router.post("/labor/{labor_id}/approve",response_model=LaborRead,dependencies=[Depends(require_permission("labor.approve"))])
async def approve_labor(labor_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).approve_labor(labor_id,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.get("/overhead-rates",response_model=list[OverheadRateRead])
async def overhead_rates(db:AsyncSession=Depends(get_db)):return list((await db.scalars(select(OverheadRate).order_by(OverheadRate.effective_from.desc(),OverheadRate.id.desc()))).all())

@router.post("/overhead-rates",response_model=OverheadRateRead,status_code=201,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def create_overhead_rate(p:OverheadRateCreate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).create_overhead_rate(p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.patch("/overhead-rates/{rate_id}",response_model=OverheadRateRead,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def update_overhead_rate(rate_id:int,p:OverheadRateUpdate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).update_overhead_rate(rate_id,p,user.id)
    except Exception as e:await db.rollback();fail(e,db)

@router.delete("/overhead-rates/{rate_id}",status_code=204,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def delete_overhead_rate(rate_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:await ManufacturingService(db).delete_overhead_rate(rate_id,user.id);return Response(status_code=204)
    except Exception as e:await db.rollback();fail(e,db)

@router.post("/orders/{order_id}/absorb-overhead/{rate_id}",response_model=ProductionOrderRead,dependencies=[Depends(require_permission("manufacturing.manage"))])
async def absorb_overhead(order_id:int,rate_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await ManufacturingService(db).absorb_overhead(order_id,rate_id,user.id)
    except Exception as e:await db.rollback();fail(e,db)
