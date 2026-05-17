"""
Rate limiter compartido — slowapi con Redis como storage.
Usar con @limiter.limit("N/minute") en los endpoints.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# Usa Redis si la URL tiene un host real (no localhost ni vacío).
# En producción Railway setea REDIS_URL con host externo.
# Fallback a memoria: el límite funciona igual, solo no persiste entre workers.
def _get_storage() -> str:
    url = settings.redis_url or ""
    if url and "localhost" not in url and "127.0.0.1" not in url:
        return url
    return "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_get_storage(),
    default_limits=[],  # sin límite global — solo donde se decora
)
