"""
qr_reader.py — Decodificador de QR desde bytes de imagen.
Usa pyzbar + Pillow. Falla silenciosamente si la imagen no contiene QR.
"""

from __future__ import annotations

import io

from app.utils.logger import get_logger

logger = get_logger(__name__)


def decode_qr(image_bytes: bytes) -> str | None:
    """
    Decodifica el primer QR encontrado en la imagen.
    Retorna el string del QR o None si no hay QR o falla.
    """
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode

        img    = Image.open(io.BytesIO(image_bytes))
        codes  = decode(img)
        if codes:
            return codes[0].data.decode("utf-8")
    except Exception as exc:
        logger.debug("decode_qr: no se pudo leer QR — %s", exc)
    return None
