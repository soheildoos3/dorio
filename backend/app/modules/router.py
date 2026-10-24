from fastapi import APIRouter

from app.modules.catalog.api import router as catalog_router
from app.modules.inventory.api import router as inventory_router
from app.modules.inventory_operations.api import router as inventory_operations_router
from app.modules.quality.api import router as quality_router
from app.modules.warehouse.api import router as warehouse_router

api_router = APIRouter()
api_router.include_router(catalog_router)
api_router.include_router(warehouse_router)
api_router.include_router(inventory_router)
api_router.include_router(inventory_operations_router)
api_router.include_router(quality_router)
