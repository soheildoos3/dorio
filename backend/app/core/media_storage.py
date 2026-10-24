from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import settings

ALLOWED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class MediaStorageError(ValueError):
    pass


def media_root() -> Path:
    root = settings.MEDIA_DIR
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


async def save_image(file: UploadFile, relative_dir: Path) -> str:
    max_bytes = max(settings.MAX_IMAGE_SIZE_MB, 1) * 1024 * 1024
    data = await file.read(max_bytes + 1)
    await file.close()
    if not data:
        raise MediaStorageError("فایل تصویر خالی است")
    if len(data) > max_bytes:
        raise MediaStorageError(f"حجم تصویر نباید بیشتر از {settings.MAX_IMAGE_SIZE_MB} مگابایت باشد")

    try:
        with Image.open(BytesIO(data)) as source:
            source.load()
            image_format = (source.format or "").upper()
            suffix = ALLOWED_IMAGE_FORMATS.get(image_format)
            if suffix is None:
                raise MediaStorageError("فقط تصاویر JPG، PNG و WEBP مجاز هستند")

            # Re-encode the validated image instead of persisting arbitrary uploaded bytes.
            # This strips embedded metadata and prevents image/polyglot payloads from being served back.
            image = source.copy()
            output = BytesIO()
            if image_format == "JPEG":
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                image.save(output, format="JPEG", quality=90, optimize=True)
            elif image_format == "PNG":
                image.save(output, format="PNG", optimize=True)
            else:
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                image.save(output, format="WEBP", quality=90, method=6)
            sanitized_data = output.getvalue()
    except MediaStorageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise MediaStorageError("فایل انتخاب‌شده تصویر معتبر نیست") from exc

    filename = f"{uuid4().hex}{suffix}"
    destination_dir = media_root() / relative_dir
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename
    await asyncio.to_thread(destination.write_bytes, sanitized_data)

    return f"/media/{relative_dir.as_posix()}/{filename}"


async def save_product_image(file: UploadFile, product_id: int) -> str:
    return await save_image(file, Path("products") / str(product_id))


async def save_qc_image(file: UploadFile, item_id: int) -> str:
    return await save_image(file, Path("qc") / str(item_id))


async def delete_local_media_url(url: str) -> None:
    if not url.startswith("/media/"):
        return
    relative = url.removeprefix("/media/")
    root = media_root()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return
    if candidate.is_file():
        try:
            await asyncio.to_thread(candidate.unlink)
        except OSError:
            return
