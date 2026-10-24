import io

import qrcode

from app.modules.inventory.qr_decoder import QRDecodeError, decode_qr_image_bytes


def test_decode_qr_image_bytes_round_trip():
    expected = "http://192.168.1.10:5173/warranty/DARIO-TEST-0001"
    image = qrcode.make(expected)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    assert decode_qr_image_bytes(buffer.getvalue()) == expected


def test_decode_qr_image_rejects_invalid_image():
    try:
        decode_qr_image_bytes(b"not-an-image")
    except QRDecodeError as exc:
        assert "تصویر" in str(exc)
    else:
        raise AssertionError("invalid image must raise QRDecodeError")
