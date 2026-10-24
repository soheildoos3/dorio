from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


class QRDecodeError(ValueError):
    pass


def _prepare_image(data: bytes):
    try:
        image = Image.open(BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise QRDecodeError("فایل تصویر معتبر نیست") from exc

    # Very large phone photos waste CPU and often make QR detection less stable.
    max_side = 2400
    if max(image.size) > max_side:
        scale = max_side / max(image.size)
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    return image


def decode_qr_image_bytes(data: bytes) -> str | None:
    """Decode a QR code from a still image.

    OpenCV is intentionally used on the server as a fallback because mobile browsers
    often block getUserMedia on plain HTTP and some WebKit browsers do not expose
    BarcodeDetector at all.
    """
    if not data:
        raise QRDecodeError("تصویر خالی است")

    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:  # pragma: no cover - deployment guard
        raise RuntimeError(
            "QR image decoding dependency is missing; install backend requirements"
        ) from exc

    pil_image = _prepare_image(data)
    rgb = np.asarray(pil_image)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    variants = [bgr, gray]
    try:
        variants.append(cv2.equalizeHist(gray))
        variants.append(cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1])
    except cv2.error:
        pass

    detector = cv2.QRCodeDetector()
    for frame in variants:
        try:
            value, _points, _straight = detector.detectAndDecode(frame)
            if value and value.strip():
                return value.strip()
        except cv2.error:
            continue

        # Some photos contain more than one code or are easier for the multi decoder.
        try:
            ok, values, _points, _straight = detector.detectAndDecodeMulti(frame)
            if ok:
                for value in values or ():
                    if value and value.strip():
                        return value.strip()
        except (cv2.error, ValueError):
            continue

    return None
