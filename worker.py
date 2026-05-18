"""
worker.py — Proceso worker independiente: listener de depósitos USDT TRC-20
════════════════════════════════════════════════════════════════════════════
En producción (Railway) este proceso corre separado del servidor web:

  web:    uvicorn main:app ...
  worker: python worker.py

Railway requiere que cualquier servicio se ligue a $PORT.
Levantamos un micro-servidor de health (/health → 200 OK) en $PORT
mientras el deposit listener corre en paralelo en el mismo event loop.
"""

import asyncio
import logging
import os
import sys
from aiohttp import web

from app.utils.logger import get_logger

logger = get_logger(__name__)

PORT = int(os.environ.get("PORT", 8080))


async def _health(request: web.Request) -> web.Response:
    return web.Response(text="ok", status=200)


async def _run_health_server() -> None:
    """Micro-servidor HTTP solo para el healthcheck de Railway."""
    app = web.Application()
    app.router.add_get("/health", _health)
    app.router.add_get("/", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("worker: health server escuchando en :%s", PORT)


async def main() -> None:
    logger.info("worker: iniciando proceso worker BananaPay...")

    from app.modules.crypto.deposit_listener import run_deposit_listener

    # Correr health server y deposit listener en paralelo
    await asyncio.gather(
        _run_health_server(),
        run_deposit_listener(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("worker: detenido por KeyboardInterrupt")
    except Exception as exc:
        logger.critical("worker: error fatal — %s", exc, exc_info=True)
        sys.exit(1)
