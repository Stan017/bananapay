"""
worker.py — Proceso worker independiente: listener de depósitos USDT TRC-20
════════════════════════════════════════════════════════════════════════════
En producción (Railway) este proceso corre separado del servidor web:

  web:    uvicorn main:app ...
  worker: python worker.py

Así el listener no comparte el event loop con las requests HTTP y puede
escalar / reiniciarse de forma independiente.

En desarrollo, el listener se inicia inline desde main.py (ver DEPOSIT_LISTENER_WORKER).
"""

import asyncio
import logging
import sys

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def main() -> None:
    logger.info("worker: iniciando proceso worker BananaPay...")

    from app.modules.crypto.deposit_listener import run_deposit_listener

    try:
        await run_deposit_listener()
    except KeyboardInterrupt:
        logger.info("worker: detenido por KeyboardInterrupt")
    except Exception as exc:
        logger.critical("worker: error fatal — %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
