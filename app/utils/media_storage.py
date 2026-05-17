"""
media_storage.py — Almacenamiento local de archivos multimedia
══════════════════════════════════════════════════════════════
Guarda comprobantes de depósito (y futuros medios) en disco local o NAS.
Si MEDIA_STORAGE_PATH está vacío, no hace nada — falla silenciosamente.

Estructura de carpetas:
    {MEDIA_STORAGE_PATH}/
        vouchers/
            2024/
                04/
                    deposit_abc123_20240417_143022.jpg

Cuando conectes el NAS:
    Solo cambia MEDIA_STORAGE_PATH en .env — el código no cambia nada.
"""

import hashlib
import mimetypes
import os
from datetime import datetime
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _get_storage_root() -> Path | None:
    """Retorna la ruta raíz de almacenamiento o None si no está configurada."""
    from app.config import settings
    path = settings.media_storage_path.strip()
    if not path:
        return None
    return Path(path)


def compute_hash(data: bytes) -> str:
    """Calcula SHA-256 del contenido — sirve para detectar duplicados reales."""
    return hashlib.sha256(data).hexdigest()


def save_voucher(
    data: bytes,
    mime_type: str,
    deposit_id: str,
) -> tuple[str | None, str]:
    """
    Guarda un comprobante de depósito en disco.

    Args:
        data:       Bytes del archivo (imagen).
        mime_type:  MIME type (image/jpeg, image/png, etc.).
        deposit_id: ID del depósito — se incluye en el nombre del archivo.

    Returns:
        (local_path, file_hash)
        local_path: Ruta donde se guardó el archivo, o None si no hay storage configurado.
        file_hash:  SHA-256 del contenido (siempre se calcula).
    """
    file_hash = compute_hash(data)

    root = _get_storage_root()
    if root is None:
        logger.debug("media_storage: MEDIA_STORAGE_PATH no configurado — solo calculando hash")
        return None, file_hash

    # Extensión según MIME type
    ext = mimetypes.guess_extension(mime_type) or ".jpg"
    # mimetypes a veces retorna .jpe en lugar de .jpg
    if ext in (".jpe", ".jpeg"):
        ext = ".jpg"

    # Carpeta organizada por año/mes
    now       = datetime.now()
    subfolder = root / "vouchers" / str(now.year) / f"{now.month:02d}"
    subfolder.mkdir(parents=True, exist_ok=True)

    # Nombre de archivo único
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename  = f"deposit_{deposit_id[:8]}_{timestamp}{ext}"
    filepath  = subfolder / filename

    try:
        filepath.write_bytes(data)
        local_path = str(filepath)
        logger.info("media_storage: guardado comprobante → %s (%d bytes)", local_path, len(data))
        return local_path, file_hash
    except Exception as exc:
        logger.error("media_storage: no se pudo guardar %s — %s", filepath, exc)
        return None, file_hash


def check_duplicate_hash(file_hash: str) -> str | None:
    """
    Busca en la BD si ya existe un depósito con este hash de comprobante.
    Retorna el deposit_id previo si hay duplicado, o None si es único.
    """
    try:
        from app.integrations.supabase_client import get_supabase
        db = get_supabase()
        result = (
            db.table("deposits")
            .select("id, user_id, amount, created_at")
            .eq("voucher_hash", file_hash)
            .neq("status", "rejected")
            .limit(1)
            .execute()
        )
        if result.data:
            prev = result.data[0]
            logger.warning(
                "media_storage: hash duplicado detectado — depósito previo id=%s amount=%s",
                prev["id"], prev["amount"],
            )
            return prev["id"]
    except Exception as exc:
        logger.error("media_storage: error buscando hash duplicado — %s", exc)
    return None
