"""
redis_client.py — Cliente Redis async compartido (singleton).
══════════════════════════════════════════════════════════════
Un solo pool de conexiones para toda la app.
Usado por: sesiones, deduplicación de webhooks, rate limits de Claude.

En desarrollo: redis://localhost:6379 (o sin Redis → funciones degradan gracefully)
En producción: Upstash rediss://... (configurado en REDIS_URL)
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Retorna el cliente Redis async (lazy, singleton)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        logger.debug("redis_client: conectado a %s", settings.redis_url[:30])
    return _redis


async def close_redis() -> None:
    """Cierra el pool de conexiones. Llamar en el shutdown del lifespan."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
