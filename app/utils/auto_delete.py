"""
auto_delete.py — Borrado automático de mensajes sensibles de WhatsApp.

Usa asyncio.create_task() para programar el borrado en background
sin bloquear la respuesta al usuario ni depender de Redis/Celery.
"""

import asyncio

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Mensajes sensibles se borran después de este tiempo
DELETE_AFTER_SECONDS = 5 * 60  # 5 minutos


def schedule_delete(message_id: str | None, delay: int = DELETE_AFTER_SECONDS) -> None:
    """
    Programa el borrado de un mensaje de WhatsApp en background.
    Si message_id es None o no hay loop activo, falla silenciosamente.
    """
    if not message_id:
        return
    try:
        asyncio.create_task(_delete_after(message_id, delay))
    except RuntimeError:
        # Sin event loop activo (tests, etc.) — ignorar
        pass


async def _delete_after(message_id: str, delay: int) -> None:
    """Espera `delay` segundos y borra el mensaje."""
    await asyncio.sleep(delay)
    from app.integrations.whatsapp.client import delete_message
    await delete_message(message_id)
    logger.info("Auto-borrado ejecutado: message_id=%s", message_id)
