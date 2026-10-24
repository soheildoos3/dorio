import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.session import async_session_factory
from app.modules.warranty.service import WarrantyService
from app.core.media_storage import media_root
from app.modules.auth.api import router as auth_router
from app.modules.accounting.api import router as accounting_router
from app.modules.catalog.api import router as catalog_router
from app.modules.channels.api import router as channels_router
from app.modules.hr.api import router as hr_router
from app.modules.inventory.api import router as inventory_router
from app.modules.inventory_operations.api import router as inventory_operations_router
from app.modules.manufacturing.api import router as manufacturing_router
from app.modules.quality.api import router as quality_router
from app.modules.sales.api import router as sales_router
from app.modules.system_tools.api import router as system_tools_router
from app.modules.tailors.api import router as tailors_router
from app.modules.user.api import router as user_router
from app.modules.warehouse.api import router as warehouse_router
from app.modules.warranty.api import public_router as warranty_public_router
from app.modules.warranty.api import router as warranty_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop = asyncio.Event()

    async def warranty_worker():
        while not stop.is_set():
            try:
                async with async_session_factory() as session:
                    await WarrantyService(session).refresh_due()
            except Exception:
                logger.exception("Automatic warranty refresh failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(60, settings.WARRANTY_REFRESH_SECONDS))
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(warranty_worker(), name="warranty-auto-activation")
    try:
        yield
    finally:
        stop.set()
        await task


app = FastAPI(title="Dario API", version="4.2.0", lifespan=lifespan)

origins = [x.strip() for x in settings.CORS_ORIGINS.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Accept"],
)

app.mount("/media", StaticFiles(directory=media_root()), name="media")

for router in [
    auth_router,
    accounting_router,
    user_router,
    catalog_router,
    warehouse_router,
    inventory_router,
    inventory_operations_router,
    manufacturing_router,
    quality_router,
    sales_router,
    system_tools_router,
    channels_router,
    tailors_router,
    warranty_router,
    hr_router,
]:
    app.include_router(router, prefix="/api")

app.include_router(warranty_public_router)


@app.get("/api/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "4.2.0"}
