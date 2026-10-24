from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse, Response

from app.db.session import async_session_factory
from app.modules.auth.dependencies import require_admin
from app.modules.system_tools.service import REPORT_TYPES, build_pdf, build_report, build_xlsx, create_database_backup

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"], dependencies=[Depends(require_admin)])


@router.get("/backup/database")
async def backup_database(background_tasks: BackgroundTasks):
    # Do not reuse the request session used by require_admin. Authentication has
    # already queried that session, which makes PostgreSQL reject SET TRANSACTION
    # ISOLATION LEVEL. A fresh session lets the backup start a clean snapshot.
    try:
        async with async_session_factory() as backup_db:
            path, filename = await create_database_backup(backup_db)
    except Exception as exc:
        logger.exception("Database backup failed")
        raise HTTPException(500, "تهیه پشتیبان دیتابیس ناموفق بود؛ جزئیات در لاگ بک‌اند ثبت شد") from exc

    background_tasks.add_task(_safe_unlink, path)
    return FileResponse(path, media_type="application/gzip", filename=filename, background=background_tasks)


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@router.get("/reports/{report_type}.{format}")
async def export_report(report_type: str, format: str):
    if report_type not in REPORT_TYPES:
        raise HTTPException(404, "گزارش درخواستی پیدا نشد")
    if format not in {"xlsx", "pdf"}:
        raise HTTPException(400, "فرمت خروجی باید xlsx یا pdf باشد")

    # Use a session dedicated to the report. Authentication already performs DB
    # reads; keeping export work isolated makes failures/rollbacks predictable.
    try:
        async with async_session_factory() as report_db:
            report = await build_report(report_db, report_type)
    except Exception as exc:
        logger.exception("Report data build failed: type=%s format=%s", report_type, format)
        raise HTTPException(
            500,
            "خواندن اطلاعات گزارش از دیتابیس ناموفق بود. ابتدا python -m alembic upgrade head را اجرا کنید؛ جزئیات در لاگ بک‌اند ثبت شد",
        ) from exc

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    try:
        if format == "xlsx":
            content = build_xlsx(report)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if not content.startswith(b"PK"):
                raise RuntimeError("فایل Excel ساخته‌شده معتبر نیست")
        else:
            content = build_pdf(report)
            media_type = "application/pdf"
            # A valid PDF must start with the PDF signature and finish with an
            # EOF marker. Validate before sending so a broken/truncated payload
            # can never be downloaded with a .pdf extension.
            if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-4096:]:
                raise RuntimeError("فایل PDF ساخته‌شده ناقص یا نامعتبر است")
    except RuntimeError as exc:
        logger.warning("Report renderer unavailable: type=%s format=%s error=%s", report_type, format, exc)
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("Report rendering failed: type=%s format=%s", report_type, format)
        raise HTTPException(500, "ساخت فایل گزارش ناموفق بود؛ جزئیات در لاگ بک‌اند ثبت شد") from exc

    filename = f"dario-{report_type}-{stamp}.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
