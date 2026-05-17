"""Cliente para Meta Cloud API — envío de mensajes WhatsApp."""

import asyncio

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY   = 1.0   # segundos (luego 2s, 4s)

_WA_API = "https://graph.facebook.com/v19.0/{phone_number_id}/messages"
_WA_MEDIA_API = "https://graph.facebook.com/v19.0/{media_id}"


async def fetch_media_bytes(media_id: str) -> tuple[bytes, str]:
    """
    Descarga un archivo multimedia de WhatsApp por su media_id.
    Retorna (bytes, mime_type). Reintenta hasta 3 veces ante fallos de red.
    """
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}

    async def _do_fetch():
        async with httpx.AsyncClient(timeout=20) as client:
            meta = await client.get(
                _WA_MEDIA_API.format(media_id=media_id),
                headers=headers,
            )
            meta.raise_for_status()
            media_url = meta.json()["url"]
            mime_type = meta.json().get("mime_type", "image/jpeg")
            resp = await client.get(media_url, headers=headers)
            resp.raise_for_status()
        return resp.content, mime_type

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return await _do_fetch()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
            last_exc = exc
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            last_exc = exc
        if attempt < _MAX_ATTEMPTS:
            delay = _BASE_DELAY * (2 ** (attempt - 1))
            logger.warning("fetch_media_bytes: intento %d/%d fallido, reintento en %.0fs", attempt, _MAX_ATTEMPTS, delay)
            await asyncio.sleep(delay)

    logger.error("fetch_media_bytes: todos los intentos fallaron para media_id=%s", media_id)
    raise last_exc


def _base_payload(to: str) -> dict:
    return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}


async def _post(payload: dict) -> str | None:
    """
    Envía el payload a la API de Meta. Retorna el message_id o None si falla.
    Reintenta hasta 3 veces ante timeouts y errores 5xx/429.
    """
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        logger.warning("WhatsApp no configurado — payload NO enviado: %r", str(payload)[:80])
        return None

    url = _WA_API.format(phone_number_id=settings.whatsapp_phone_number_id)
    wa_headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload, headers=wa_headers)

            if resp.status_code == 200:
                data       = resp.json()
                message_id = (data.get("messages") or [{}])[0].get("id")
                logger.info("Mensaje enviado a %s [type=%s] id=%s", payload.get("to"), payload.get("type"), message_id)
                return message_id

            # 4xx → error del cliente, no reintentar
            if resp.status_code < 500 and resp.status_code != 429:
                logger.error("WhatsApp API error %s | to=%s | %s", resp.status_code, payload.get("to"), resp.text[:200])
                return None

            # 5xx / 429 → transitorio, reintentar
            last_exc = Exception(f"HTTP {resp.status_code}")
            logger.warning("WhatsApp API %s (transitorio) intento %d/%d | to=%s", resp.status_code, attempt, _MAX_ATTEMPTS, payload.get("to"))

        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            last_exc = exc
            logger.warning("WhatsApp red: %s intento %d/%d | to=%s", type(exc).__name__, attempt, _MAX_ATTEMPTS, payload.get("to"))

        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(_BASE_DELAY * (2 ** (attempt - 1)))

    logger.error("WhatsApp: todos los intentos fallaron para to=%s", payload.get("to"))
    return None


async def delete_message(message_id: str) -> None:
    """
    Borra un mensaje enviado por el bot del chat del usuario.
    Usa el endpoint DELETE de Meta Cloud API.
    Falla silenciosamente — nunca rompe el flujo principal.
    """
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        return
    url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                url,
                headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
                params={"message_id": message_id},
            )
        if resp.status_code == 200:
            logger.info("Mensaje borrado: id=%s", message_id)
        else:
            logger.warning("No se pudo borrar mensaje %s: %s", message_id, resp.text[:100])
    except Exception as e:
        logger.warning("delete_message error: %s", e)


async def upload_media(image_bytes: bytes, mime_type: str = "image/png") -> str | None:
    """
    Sube un archivo multimedia a Meta Cloud API.
    Retorna el media_id o None si falla.
    """
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        logger.warning("WhatsApp no configurado — upload_media omitido")
        return None

    url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/media"
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers=headers,
                data={"messaging_product": "whatsapp", "type": mime_type},
                files={"file": ("image.png", image_bytes, mime_type)},
            )
            resp.raise_for_status()
            media_id = resp.json().get("id")
            logger.info("upload_media: media_id=%s mime=%s bytes=%d", media_id, mime_type, len(image_bytes))
            return media_id
    except Exception as exc:
        logger.error("upload_media error: %s", exc)
        return None


async def send_image(to: str, media_id: str, caption: str = "") -> str | None:
    """Envía una imagen subida a Meta (referenciada por media_id)."""
    image_obj: dict = {"id": media_id}
    if caption:
        image_obj["caption"] = caption
    payload = {**_base_payload(to), "type": "image", "image": image_obj}
    return await _post(payload)


async def send_message(to: str, text: str) -> str | None:
    """Envía un mensaje de texto plano. Retorna el message_id."""
    payload = {**_base_payload(to), "type": "text", "text": {"body": text, "preview_url": False}}
    return await _post(payload)


async def send_buttons(to: str, text: str, buttons: list) -> str | None:
    """
    Envía un mensaje con hasta 3 botones de respuesta rápida.
    `buttons` es una lista de objetos Btn(id, title).
    """
    payload = {
        **_base_payload(to),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b.id, "title": b.title[:20]}}
                    for b in buttons
                ]
            },
        },
    }
    return await _post(payload)


async def send_list(to: str, text: str, button_label: str, sections: list) -> str | None:
    """
    Envía un mensaje de lista desplegable con hasta 10 opciones.
    `sections` es una lista de objetos ListSection.
    """
    payload = {
        **_base_payload(to),
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text},
            "action": {
                "button": button_label[:20],
                "sections": [
                    {
                        "title": sec.title[:24],
                        "rows": [
                            {
                                "id": row.id,
                                "title": row.title[:24],
                                **({"description": row.description[:72]} if row.description else {}),
                            }
                            for row in sec.rows
                        ],
                    }
                    for sec in sections
                ],
            },
        },
    }
    return await _post(payload)


async def send_bot_message(to: str, msg) -> str | None:
    """
    Despacha el mensaje correcto según el tipo de BotMessage / ImageMessage / str.
    Retorna el message_id para permitir borrado posterior.
    """
    from app.integrations.whatsapp.messages import BotMessage, ImageMessage

    if isinstance(msg, str):
        return await send_message(to, msg)

    elif isinstance(msg, ImageMessage):
        media_id = await upload_media(msg.image_bytes, msg.mime_type)
        if not media_id:
            return await send_message(to, "⚠️ No se pudo generar el QR. Intenta de nuevo.")
        return await send_image(to, media_id, msg.caption)

    elif isinstance(msg, BotMessage):
        if msg.is_buttons:
            return await send_buttons(to, msg.text, msg.buttons)
        elif msg.is_list:
            return await send_list(to, msg.text, msg.list_button_label, msg.sections)
        else:
            return await send_message(to, msg.text)

    else:
        logger.error("send_bot_message: tipo desconocido %s", type(msg))
        return None
