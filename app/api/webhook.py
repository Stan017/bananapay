"""Webhook de Meta Cloud API — recibe y procesa mensajes de WhatsApp."""

import asyncio
import json
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.core.command_router import route
from app.core.limiter import limiter
from app.core.session import session_manager
from app.core.claude_intent import parse_intent_with_claude
from app.core.security import verify_whatsapp_signature
from app.integrations.supabase_client import get_supabase
from app.integrations.whatsapp.client import send_bot_message
from app.integrations.whatsapp.messages import BUTTON_ID_TO_TEXT, MAIN_MENU_SECTIONS, BotMessage
from app.utils.logger import get_logger
from app.utils.phone import normalize_phone

router = APIRouter(tags=["webhook"])
logger = get_logger(__name__)

# Máximo de mensajes por usuario por minuto — protege contra spam y bucles infinitos
_MAX_MSG_PER_MINUTE = 30


async def _check_phone_rate(phone: str) -> bool:
    """
    Limita mensajes por número de teléfono usando Redis.
    Retorna True si se puede procesar, False si se excedió el límite.
    Falla abierta si Redis no está disponible.
    """
    try:
        from app.integrations.redis_client import get_redis
        r   = await get_redis()
        key = f"bp:msg_rate:{phone}:{int(time.time() // 60)}"   # bucket por minuto
        count = await r.incr(key)
        await r.expire(key, 90)   # 90s para que el bucket expire después del minuto
        if count > _MAX_MSG_PER_MINUTE:
            logger.warning("webhook: rate limit por teléfono phone=%s count=%d", phone, count)
            return False
        return True
    except Exception:
        return True   # Redis caído → falla abierta, no bloqueamos al usuario


def _log_message_sync(phone: str, direction: str, content: str) -> None:
    """Inserción síncrona — siempre llamar desde asyncio.to_thread."""
    get_supabase().table("message_log").insert({
        "phone":     phone,
        "direction": direction,
        "content":   content,
    }).execute()


async def _log_message(phone: str, direction: str, content: str) -> None:
    """
    Guarda un mensaje en message_log sin bloquear el event loop.
    Fire-and-forget — no lanza excepciones al caller.
    """
    try:
        await asyncio.to_thread(_log_message_sync, phone, direction, content)
    except Exception:
        logger.warning("No se pudo guardar en message_log: phone=%s dir=%s", phone, direction)


@router.get("/webhook")
async def webhook_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    """Verificación del webhook por Meta (paso inicial del setup)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("Webhook verificado por Meta")
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verificación fallida")


@router.post("/webhook")
@limiter.limit("300/minute")   # límite global por IP — bloquea flood masivo
async def webhook_receive(request: Request, background: BackgroundTasks) -> dict:
    """Recibe mensajes entrantes. Responde 200 inmediato, procesa en background."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_whatsapp_signature(body, signature):
        logger.warning("Firma HMAC inválida — posible request fraudulento")
        raise HTTPException(status_code=403, detail="Firma inválida")

    payload = json.loads(body)
    background.add_task(_process_payload, payload)
    return {"status": "ok"}


async def _is_duplicate(message_id: str) -> bool:
    """
    Retorna True si este message_id ya fue procesado (Meta puede reenviar webhooks).
    Guarda el ID en Redis por 5 minutos — ventana suficiente para deduplicar reintentos.
    Falla abierta: si Redis no está disponible, deja pasar el mensaje.
    """
    try:
        from app.integrations.redis_client import get_redis
        r = await get_redis()
        # SET NX (solo si no existe) + EX 300s — atómico
        inserted = await r.set(f"bp:wh:{message_id}", 1, ex=300, nx=True)
        return inserted is None   # None = la key ya existía = duplicado
    except Exception as exc:
        logger.warning("dedup: Redis no disponible, procesando igual — %s", exc)
        return False


async def _process_payload(payload: dict) -> None:
    """Extrae mensajes del payload de Meta y los procesa."""
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    msg_type = message.get("type")
                    phone    = normalize_phone(message["from"]) or message["from"]

                    # Deduplicación — Meta puede reenviar el mismo webhook
                    msg_id = message.get("id", "")
                    if msg_id and await _is_duplicate(msg_id):
                        logger.debug("webhook: mensaje duplicado ignorado id=%s phone=%s", msg_id, phone)
                        continue

                    # Rate limit por teléfono — 30 mensajes/minuto por usuario
                    if not await _check_phone_rate(phone):
                        logger.warning("webhook: flood detectado, ignorando phone=%s", phone)
                        continue

                    # ── Mensaje de texto normal ────────────────────────────────
                    if msg_type == "text":
                        text: str = message["text"]["body"]

                    # ── Clic en botón o selección de lista ────────────────────
                    elif msg_type == "interactive":
                        interactive = message.get("interactive", {})
                        itype = interactive.get("type")

                        if itype == "button_reply":
                            btn_id = interactive["button_reply"]["id"]
                            text = BUTTON_ID_TO_TEXT.get(btn_id, interactive["button_reply"]["title"])
                        elif itype == "list_reply":
                            row_id = interactive["list_reply"]["id"]
                            text = BUTTON_ID_TO_TEXT.get(row_id, interactive["list_reply"]["title"])
                        else:
                            continue

                    # ── Imagen: comprobante de depósito o QR de cobro ─────────
                    elif msg_type == "image":
                        from app.core.session import ConversationState
                        from app.core.command_router import handle_deposit_voucher
                        session_data = await session_manager.get(phone)
                        state    = session_data.get("state")
                        media_id = message.get("image", {}).get("id", "")
                        await _log_message(phone, "in", "[imagen]")

                        if state == ConversationState.AWAITING_DEPOSIT_VOUCHER:
                            response = await handle_deposit_voucher(phone, media_id)
                            await send_bot_message(phone, response)
                            out_text = response.text if isinstance(response, BotMessage) else str(response)
                            await _log_message(phone, "out", out_text)
                        else:
                            # Intentar leer como QR de cobro BananaPay
                            qr_response = await _handle_bananapay_qr(phone, media_id)
                            if qr_response:
                                await send_bot_message(phone, qr_response)
                                out_text = qr_response.text if isinstance(qr_response, BotMessage) else str(qr_response)
                                await _log_message(phone, "out", out_text)
                            else:
                                msg = "Para subir un comprobante primero escribe *depositar*. 📥"
                                await send_bot_message(phone, msg)
                                await _log_message(phone, "out", msg)
                        continue

                    # ── Ignorar audio, stickers, etc. ─────────────────────────
                    else:
                        logger.debug("Tipo de mensaje ignorado: %s from=%s", msg_type, phone)
                        continue

                    logger.info("Mensaje recibido: from=%s text=%r", phone, text[:50])
                    await _log_message(phone, "in", text)

                    # Caso especial: botón "Ver más" → enviar lista con saldo real
                    if text == "__menu_more__":
                        from app.modules.auth.register import get_user_by_phone
                        from app.modules.fiat.wallet import get_balances
                        user = await get_user_by_phone(phone)
                        if user:
                            bal  = await get_balances(user["id"])
                            fiat, usdt, usdc = bal["fiat"], bal["usdt"], bal["usdc"]
                            if usdt > 0 or usdc > 0:
                                lines = [f"🏦 USD:  *${fiat:.2f}*"]
                                if usdt > 0:
                                    lines.append(f"🪙 USDT: *{usdt:.2f}*")
                                if usdc > 0:
                                    lines.append(f"🔵 USDC: *{usdc:.2f}*")
                                saldo_txt = "\n".join(lines)
                            else:
                                saldo_txt = f"Saldo actual: *${fiat:.2f} USD*"
                            menu_text = f"🍌 *BananaPay — Menú*\n{saldo_txt}"
                        else:
                            menu_text = "🍌 *BananaPay — Menú*"
                        menu = BotMessage(
                            text=menu_text,
                            sections=MAIN_MENU_SECTIONS,
                            list_button_label="📋 Ver opciones",
                        )
                        await send_bot_message(phone, menu)
                        await _log_message(phone, "out", menu.text)
                        continue

                    session_data = await session_manager.get(phone)
                    parsed = await parse_intent_with_claude(text, session_data, phone=phone)
                    response = await route(phone, text, parsed)
                    message_id = await send_bot_message(phone, response)

                    # Si la imagen tiene un mensaje de seguimiento (ej. botones post-QR),
                    # enviarlo como segundo mensaje — WhatsApp no permite botones en imágenes
                    from app.integrations.whatsapp.messages import ImageMessage
                    if isinstance(response, ImageMessage) and response.follow_up:
                        await send_bot_message(phone, response.follow_up)

                    # Auto-borrar mensajes sensibles después de 5 minutos
                    from app.core.intent_engine import Intent
                    from app.utils.auto_delete import schedule_delete
                    _SENSITIVE_INTENTS = {Intent.BALANCE, Intent.HISTORY}
                    if parsed.intent in _SENSITIVE_INTENTS and message_id:
                        schedule_delete(message_id)

                    # Guardar respuesta del bot (puede ser BotMessage o str)
                    out_text = response.text if isinstance(response, BotMessage) else str(response)
                    await _log_message(phone, "out", out_text)

    except Exception:
        logger.exception("Error procesando payload de WhatsApp")


async def _handle_bananapay_qr(phone: str, media_id: str):
    """
    Descarga la imagen, intenta decodificar un QR BananaPay y lanza el flujo
    de transferencia automáticamente.

    Retorna una respuesta de bot si es un QR válido, None si no lo es.
    El None hace que webhook.py muestre el mensaje genérico de "sube comprobante".
    """
    import urllib.parse
    from decimal import Decimal, InvalidOperation

    from app.integrations.whatsapp.client import fetch_media_bytes
    from app.utils.qr_reader import decode_qr
    from app.integrations.supabase_client import get_supabase
    from app.core.session import ConversationState
    from app.core.routers.transfer import _short_name, _fmt

    try:
        image_bytes, _ = await fetch_media_bytes(media_id)
    except Exception as exc:
        logger.warning("_handle_bananapay_qr: no se pudo descargar imagen — %s", exc)
        return None

    qr_data = decode_qr(image_bytes)
    if not qr_data or not qr_data.startswith("bananapay://pay"):
        return None   # no es un QR BananaPay

    logger.info("QR BananaPay detectado: phone=%s data=%r", phone, qr_data[:80])

    # ── Parsear URI ────────────────────────────────────────────────────────────
    try:
        parsed_uri = urllib.parse.urlparse(qr_data)
        params     = urllib.parse.parse_qs(parsed_uri.query)
        cedula     = params.get("cedula", [None])[0]
        amount_str = params.get("amount", [None])[0]
    except Exception:
        return None

    if not cedula:
        return None

    # ── Buscar destinatario por cédula ─────────────────────────────────────────
    try:
        db     = get_supabase()
        result = db.table("users").select("id, name, phone").eq("cedula", cedula).limit(1).execute()
    except Exception as exc:
        logger.warning("_handle_bananapay_qr: error BD — %s", exc)
        return None

    if not result.data:
        return f"❌ El usuario de ese QR no está registrado en BananaPay."

    recipient      = result.data[0]
    to_phone       = recipient["phone"]
    to_short       = _short_name(recipient["name"])

    # No puede pagarse a sí mismo
    if to_phone == phone:
        return "⚠️ Ese es tu propio QR — compártelo con alguien para que te pague."

    # ── Parsear monto ──────────────────────────────────────────────────────────
    amount: Decimal | None = None
    if amount_str:
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                amount = None
        except InvalidOperation:
            pass

    # ── Con monto → directo al PIN ─────────────────────────────────────────────
    if amount:
        await session_manager.set_state(
            phone,
            ConversationState.AWAITING_TRANSFER_PIN,
            context={
                "transfer_recipient":     to_phone,
                "transfer_raw_recipient": to_short,
                "transfer_amount":        str(amount),
                "transfer_currency":      "USD",
                "transfer_pin_attempts":  0,
            },
        )
        return (
            f"💳 *Solicitud de pago de {to_short}*\n\n"
            f"💵 Monto: *{_fmt(amount, 'USD')}*\n\n"
            f"🔐 Ingresa tu PIN para confirmar:"
        )

    # ── Sin monto → pedir cuánto ───────────────────────────────────────────────
    await session_manager.set_state(
        phone,
        ConversationState.AWAITING_TRANSFER_AMOUNT,
        context={
            "awaiting_field":         "amount",
            "transfer_recipient":     to_phone,
            "transfer_raw_recipient": to_short,
            "transfer_currency":      "USD",
            "transfer_pin_attempts":  0,
        },
    )
    return (
        f"💳 *Solicitud de pago de {to_short}*\n\n"
        f"💵 ¿Cuánto quieres enviarle?"
    )
