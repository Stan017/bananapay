"""
retry.py — Backoff exponencial para llamadas a APIs externas.

Uso:
    from app.utils.retry import with_retry

    result = await with_retry(some_async_fn, arg1, arg2)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Códigos HTTP que ameritan reintento (problemas transitorios del servidor)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def with_retry(
    fn: Callable,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    label: str = "",
    **kwargs,
):
    """
    Ejecuta `fn(*args, **kwargs)` con hasta `max_attempts` intentos.
    Entre reintentos espera 1s → 2s → 4s (exponential backoff).

    Reintenta en:
      - httpx.TimeoutException
      - httpx.ConnectError / httpx.NetworkError
      - Excepciones genéricas de red

    No reintenta en:
      - httpx.HTTPStatusError con status 4xx (error del cliente — no cambiará)
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)

        except httpx.HTTPStatusError as exc:
            # 4xx → error del cliente, reintentar no ayuda
            if exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
            last_exc = exc
            msg = f"HTTP {exc.response.status_code}"

        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            last_exc = exc
            msg = type(exc).__name__

        except Exception as exc:
            # Excepción genérica — reintentar por si es transitoria
            last_exc = exc
            msg = str(exc)[:80]

        if attempt < max_attempts:
            delay = base_delay * (2 ** (attempt - 1))   # 1s, 2s, 4s
            logger.warning(
                "retry: %s — intento %d/%d fallido (%s), reintentando en %.0fs",
                label or fn.__name__, attempt, max_attempts, msg, delay,
            )
            await asyncio.sleep(delay)
        else:
            logger.error(
                "retry: %s — todos los intentos fallaron (%s)",
                label or fn.__name__, msg,
            )

    raise last_exc
