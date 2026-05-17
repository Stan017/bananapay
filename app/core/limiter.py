"""
Rate limiter compartido — slowapi con Redis como storage.
Usar con @limiter.limit("N/minute") en los endpoints.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# Redis como backend — los contadores sobreviven reinicios y son compartidos
# entre múltiples workers. Si Redis no está, falla abierta (memoria local).
_storage = f"redis://{settings.redis_url.removeprefix('redis://')}" \
    if settings.redis_url else "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage,
    default_limits=[],  # sin límite global — solo donde se decora
)
