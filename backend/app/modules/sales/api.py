from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.sales.model import SalesInvoice, SalesReturn
from app.modules.sales.schemas import CatalogFeedRow, InvoiceCreate, InvoiceRead, SalesReturnCreate, SalesReturnRead
from app.modules.sales.service import SalesError, SalesService

router=APIRouter(prefix="/sales",tags=["sales"],dependencies=[Depends(get_current_user),Depends(require_permission("sales.view"))])

def fail(exc:Exception):
    if isinstance(exc,SalesError): raise HTTPException(409,str(exc))
    raise exc

@router.get("/invoices",response_model=list[InvoiceRead])
async def invoices(offset:int=Query(0,ge=0),limit:int=Query(200,ge=1,le=1000),db:AsyncSession=Depends(get_db)):
    return list((await db.execute(select(SalesInvoice).order_by(SalesInvoice.id.desc()).offset(offset).limit(limit))).scalars().unique().all())

@router.post("/invoices",response_model=InvoiceRead,status_code=201,dependencies=[Depends(require_permission("sales.manage"))])
async def create_invoice(p:InvoiceCreate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await SalesService(db).create_invoice(p,user.id)
    except Exception as exc:fail(exc)

@router.post("/invoices/{invoice_id}/confirm",response_model=InvoiceRead,dependencies=[Depends(require_permission("sales.manage"))])
async def confirm(invoice_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await SalesService(db).confirm(invoice_id,user.id)
    except Exception as exc:fail(exc)

@router.post("/invoices/{invoice_id}/ship",response_model=InvoiceRead,dependencies=[Depends(require_permission("sales.ship"))])
async def ship(invoice_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await SalesService(db).ship(invoice_id,user.id)
    except Exception as exc:fail(exc)

@router.post("/invoices/{invoice_id}/cancel",response_model=InvoiceRead,dependencies=[Depends(require_permission("sales.manage"))])
async def cancel(invoice_id:int,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await SalesService(db).cancel(invoice_id,user.id)
    except Exception as exc:fail(exc)

@router.post("/invoices/{invoice_id}/returns",response_model=SalesReturnRead,status_code=201,dependencies=[Depends(require_permission("sales.return"))])
async def create_return(invoice_id:int,p:SalesReturnCreate,user=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    try:return await SalesService(db).create_return(invoice_id,p,user.id)
    except Exception as exc:fail(exc)

@router.get("/returns",response_model=list[SalesReturnRead])
async def returns(offset:int=Query(0,ge=0),limit:int=Query(200,ge=1,le=1000),db:AsyncSession=Depends(get_db)):
    return list((await db.execute(select(SalesReturn).order_by(SalesReturn.id.desc()).offset(offset).limit(limit))).scalars().unique().all())

@router.get("/catalog-feed/{channel_id}",response_model=list[CatalogFeedRow])
async def catalog_feed(channel_id:int,db:AsyncSession=Depends(get_db)):
    try:return await SalesService(db).catalog_feed(channel_id)
    except Exception as exc:fail(exc)
