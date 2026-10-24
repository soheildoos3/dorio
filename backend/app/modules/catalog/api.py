from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.media_storage import MediaStorageError, delete_local_media_url, save_product_image
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.catalog.model import (
    Attribute, AttributeValue, Category, Product, ProductAttribute, ProductAttributeValue, VariantAttributeValue,
)
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    AttributeCreate, AttributeRead, AttributeUpdate, AttributeValueCreate, AttributeValueRead, AttributeValueUpdate,
    CategoryCreate, CategoryRead, CategoryUpdate, GenerateVariantsRequest, MediaCreate, MediaRead, MediaUpdate,
    ProductAttributesUpdate, ProductCreate, ProductDetail, ProductRead, ProductUpdate,
    ProductVariantCreate, ProductVariantRead, ProductVariantUpdate,
)
from app.modules.catalog.service import CatalogConflictError, CatalogNotFoundError, CatalogService

router = APIRouter(prefix="/catalog", tags=["catalog"], dependencies=[Depends(get_current_user), Depends(require_permission("catalog.view"))])


def svc(db: AsyncSession = Depends(get_db)) -> CatalogService: return CatalogService(db)

def handle(exc: Exception):
    if isinstance(exc, CatalogNotFoundError): raise HTTPException(404, str(exc))
    if isinstance(exc, (CatalogConflictError, MediaStorageError)): raise HTTPException(409 if isinstance(exc, CatalogConflictError) else 400, str(exc))
    raise exc


def variant_read(v):
    resolved=[]
    for row in v.attribute_values:
        av=row.attribute_value; a=av.attribute
        resolved.append({"attribute_id":a.id,"attribute_code":a.code,"attribute_name":a.name,"value_id":av.id,"value":av.value})
    return {**ProductVariantRead.model_validate(v).model_dump(exclude={"resolved_attributes"}), "resolved_attributes":resolved}


def config_read(rows):
    out=[]
    for pa in rows:
        out.append({"id":pa.id,"attribute":AttributeRead.model_validate(pa.attribute),"values":[AttributeValueRead.model_validate(x.attribute_value) for x in pa.values],"sort_order":pa.sort_order})
    return out


@router.get("/categories", response_model=list[CategoryRead])
async def list_categories(active_only: bool=False, db: AsyncSession=Depends(get_db)): return await CatalogRepository(db).list_categories(active_only=active_only)

@router.post("/categories", response_model=CategoryRead, status_code=201, dependencies=[Depends(require_permission("catalog.manage"))])
async def create_category(p:CategoryCreate,s:CatalogService=Depends(svc)):
    try:return await s.create_category(p)
    except Exception as e:handle(e)

@router.patch("/categories/{category_id}", response_model=CategoryRead, dependencies=[Depends(require_permission("catalog.manage"))])
async def update_category(category_id:int,p:CategoryUpdate,s:CatalogService=Depends(svc)):
    try:return await s.update_category(category_id,p)
    except Exception as e:handle(e)

@router.delete("/categories/{category_id}", status_code=204, dependencies=[Depends(require_permission("catalog.manage"))])
async def delete_category(category_id:int, db:AsyncSession=Depends(get_db)):
    obj=await db.get(Category,category_id)
    if not obj: raise HTTPException(404,"Category not found")
    if await db.scalar(select(Category.id).where(Category.parent_id==category_id).limit(1)):
        raise HTTPException(409,"این دسته زیرمجموعه دارد؛ ابتدا زیرمجموعه‌ها را جابه‌جا یا حذف کنید")
    if await db.scalar(select(Product.id).where(Product.category_id==category_id).limit(1)):
        raise HTTPException(409,"این دسته به محصول متصل است؛ برای حفظ سابقه آن را غیرفعال کنید")
    await db.delete(obj);await db.commit();return Response(status_code=204)

@router.get("/products", response_model=list[ProductRead])
async def list_products(offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=500),db:AsyncSession=Depends(get_db)): return await CatalogRepository(db).list_products(offset=offset,limit=limit)

@router.get("/products/{product_id}", response_model=ProductDetail)
async def product_detail(product_id:int,db:AsyncSession=Depends(get_db)):
    repo=CatalogRepository(db); p=await repo.get_product(product_id)
    if not p or p.deleted_at is not None: raise HTTPException(404,"Product not found")
    category=await repo.get_category(p.category_id) if p.category_id else None
    variants=[variant_read(v) for v in await repo.list_variants(product_id=product_id)]
    return {**ProductRead.model_validate(p).model_dump(),"category":category,"variants":variants,"media":await repo.list_media(product_id),"attribute_config":config_read(await repo.get_product_attribute_config(product_id))}

@router.post("/products", response_model=ProductRead,status_code=201,dependencies=[Depends(require_permission("catalog.manage"))])
async def create_product(p:ProductCreate,s:CatalogService=Depends(svc)):
    try:return await s.create_product(p)
    except Exception as e:handle(e)

@router.patch("/products/{product_id}", response_model=ProductRead,dependencies=[Depends(require_permission("catalog.manage"))])
async def update_product(product_id:int,p:ProductUpdate,s:CatalogService=Depends(svc)):
    try:return await s.update_product(product_id,p)
    except Exception as e:handle(e)

@router.delete("/products/{product_id}",status_code=204,dependencies=[Depends(require_permission("catalog.manage"))])
async def delete_product(product_id:int,s:CatalogService=Depends(svc)):
    try:await s.soft_delete_product(product_id);return Response(status_code=204)
    except Exception as e:handle(e)

@router.get("/products/{product_id}/attributes")
async def product_attributes(product_id:int,db:AsyncSession=Depends(get_db)): return config_read(await CatalogRepository(db).get_product_attribute_config(product_id))

@router.put("/products/{product_id}/attributes",dependencies=[Depends(require_permission("catalog.manage"))])
async def set_product_attributes(product_id:int,p:ProductAttributesUpdate,s:CatalogService=Depends(svc)):
    try:return config_read(await s.set_product_attributes(product_id,p))
    except Exception as e:handle(e)

@router.post("/products/{product_id}/generate-variants",response_model=list[ProductVariantRead],dependencies=[Depends(require_permission("catalog.manage"))])
async def generate_variants(product_id:int,p:GenerateVariantsRequest,s:CatalogService=Depends(svc)):
    try:return [variant_read(v) for v in await s.generate_variants(product_id,p)]
    except Exception as e:handle(e)

@router.get("/variants",response_model=list[ProductVariantRead])
async def list_variants(product_id:int|None=None,offset:int=0,limit:int=500,db:AsyncSession=Depends(get_db)): return [variant_read(v) for v in await CatalogRepository(db).list_variants(product_id=product_id,offset=offset,limit=min(limit,1000))]

@router.post("/variants",response_model=ProductVariantRead,status_code=201,dependencies=[Depends(require_permission("catalog.manage"))])
async def create_variant(p:ProductVariantCreate,s:CatalogService=Depends(svc)):
    try:return variant_read(await s.create_variant(p))
    except Exception as e:handle(e)

@router.patch("/variants/{variant_id}",response_model=ProductVariantRead,dependencies=[Depends(require_permission("catalog.manage"))])
async def update_variant(variant_id:int,p:ProductVariantUpdate,s:CatalogService=Depends(svc)):
    try:return variant_read(await s.update_variant(variant_id,p))
    except Exception as e:handle(e)

@router.delete("/variants/{variant_id}", status_code=204, dependencies=[Depends(require_permission("catalog.manage"))])
async def delete_variant(variant_id:int, s:CatalogService=Depends(svc)):
    try:
        await s.delete_variant(variant_id)
        return Response(status_code=204)
    except Exception as e:
        handle(e)


@router.post("/media/upload",response_model=MediaRead,status_code=201,dependencies=[Depends(require_permission("catalog.manage"))])
async def upload_media(product_id:int=Form(...),variant_id:int|None=Form(None),is_primary:bool=Form(False),sort_order:int=Form(0),file:UploadFile=File(...),s:CatalogService=Depends(svc)):
    stored=None
    try:
        product=await s.repo.get_product(product_id)
        if not product or product.deleted_at is not None: raise CatalogNotFoundError("Product not found")
        if variant_id is not None:
            variant=await s.repo.get_variant(variant_id)
            if not variant or variant.product_id!=product_id: raise CatalogConflictError("تنوع به این محصول تعلق ندارد")
        stored=await save_product_image(file,product_id)
        return await s.create_media(MediaCreate(product_id=product_id,variant_id=variant_id,url=stored,is_primary=is_primary,sort_order=sort_order))
    except Exception as e:
        if stored: await delete_local_media_url(stored)
        handle(e)

@router.get("/products/{product_id}/media",response_model=list[MediaRead])
async def list_media(product_id:int,db:AsyncSession=Depends(get_db)): return await CatalogRepository(db).list_media(product_id)

@router.patch("/media/{media_id}",response_model=MediaRead,dependencies=[Depends(require_permission("catalog.manage"))])
async def update_media(media_id:int,p:MediaUpdate,s:CatalogService=Depends(svc)):
    try:return await s.update_media(media_id,p)
    except Exception as e:handle(e)

@router.delete("/media/{media_id}",status_code=204,dependencies=[Depends(require_permission("catalog.manage"))])
async def delete_media(media_id:int,s:CatalogService=Depends(svc)):
    try:
        m=await s.delete_media(media_id);await delete_local_media_url(m.url);return Response(status_code=204)
    except Exception as e:handle(e)

@router.get("/attributes",response_model=list[AttributeRead])
async def list_attributes(db:AsyncSession=Depends(get_db)): return await CatalogRepository(db).list_attributes()

@router.post("/attributes",response_model=AttributeRead,status_code=201,dependencies=[Depends(require_permission("catalog.manage"))])
async def create_attribute(p:AttributeCreate,s:CatalogService=Depends(svc)):
    try:return await s.create_attribute(p)
    except Exception as e:handle(e)

@router.patch("/attributes/{attribute_id}",response_model=AttributeRead,dependencies=[Depends(require_permission("catalog.manage"))])
async def update_attribute(attribute_id:int,p:AttributeUpdate,db:AsyncSession=Depends(get_db)):
    obj=await db.get(Attribute,attribute_id)
    if not obj: raise HTTPException(404,"Attribute not found")
    for k,v in p.model_dump(exclude_unset=True).items():setattr(obj,k,v)
    await db.commit();await db.refresh(obj);return obj

@router.delete("/attributes/{attribute_id}",status_code=204,dependencies=[Depends(require_permission("catalog.manage"))])
async def delete_attribute(attribute_id:int,db:AsyncSession=Depends(get_db)):
    obj=await db.get(Attribute,attribute_id)
    if not obj: raise HTTPException(404,"Attribute not found")
    if await db.scalar(select(ProductAttribute.id).where(ProductAttribute.attribute_id==attribute_id).limit(1)):
        raise HTTPException(409,"این ویژگی در تنظیمات محصول استفاده شده و قابل حذف نیست")
    linked_variant=await db.scalar(
        select(VariantAttributeValue.id)
        .join(AttributeValue, AttributeValue.id==VariantAttributeValue.attribute_value_id)
        .where(AttributeValue.attribute_id==attribute_id).limit(1)
    )
    if linked_variant:
        raise HTTPException(409,"یکی از مقادیر این ویژگی در تنوع محصول استفاده شده و قابل حذف نیست")
    await db.delete(obj);await db.commit();return Response(status_code=204)

@router.get("/attribute-values",response_model=list[AttributeValueRead])
async def list_attribute_values(attribute_id:int|None=None,db:AsyncSession=Depends(get_db)): return await CatalogRepository(db).list_attribute_values(attribute_id=attribute_id)

@router.post("/attribute-values",response_model=AttributeValueRead,status_code=201,dependencies=[Depends(require_permission("catalog.manage"))])
async def create_attribute_value(p:AttributeValueCreate,s:CatalogService=Depends(svc)):
    try:return await s.create_attribute_value(p)
    except Exception as e:handle(e)

@router.patch("/attribute-values/{value_id}",response_model=AttributeValueRead,dependencies=[Depends(require_permission("catalog.manage"))])
async def update_attribute_value(value_id:int,p:AttributeValueUpdate,db:AsyncSession=Depends(get_db)):
    obj=await db.get(AttributeValue,value_id)
    if not obj:raise HTTPException(404,"Attribute value not found")
    for k,v in p.model_dump(exclude_unset=True).items():setattr(obj,k,v)
    await db.commit();await db.refresh(obj);return obj


@router.delete("/attribute-values/{value_id}",status_code=204,dependencies=[Depends(require_permission("catalog.manage"))])
async def delete_attribute_value(value_id:int,db:AsyncSession=Depends(get_db)):
    obj=await db.get(AttributeValue,value_id)
    if not obj: raise HTTPException(404,"Attribute value not found")
    if await db.scalar(select(ProductAttributeValue.id).where(ProductAttributeValue.attribute_value_id==value_id).limit(1)):
        raise HTTPException(409,"این مقدار در تنظیمات محصول استفاده شده و قابل حذف نیست")
    if await db.scalar(select(VariantAttributeValue.id).where(VariantAttributeValue.attribute_value_id==value_id).limit(1)):
        raise HTTPException(409,"این مقدار در یک تنوع محصول استفاده شده و قابل حذف نیست")
    await db.delete(obj);await db.commit();return Response(status_code=204)
