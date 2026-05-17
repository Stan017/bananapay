"""
Envío de push notifications vía Expo Push API.
No requiere infraestructura propia — Expo actúa como gateway hacia APNs (iOS) y FCM (Android).
Documentación: https://docs.expo.dev/push-notifications/sending-notifications/
"""

import asyncio
from typing import Optional

import httpx

from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

logger = get_logger(__name__)

_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push(
    user_id: str,
    title:   str,
    body:    str,
    data:    Optional[dict] = None,
) -> None:
    """
    Envía una push notification al dispositivo del usuario.
    Fire-and-forget — no lanza excepciones al caller.

    Args:
        user_id: UUID del usuario en la tabla users.
        title:   Título de la notificación (negrita en iOS/Android).
        body:    Texto del cuerpo de la notificación.
        data:    Payload JSON opcional (para deep-linking en la app).
    """
    try:
        token = _get_push_token(user_id)
        if not token:
            return   # usuario sin token registrado — no tiene la app o no dio permiso

        await _deliver(token, title, body, data or {})
    except Exception as exc:
        logger.warning("push: error inesperado user_id=%s — %s", user_id, exc)


def _get_push_token(user_id: str) -> Optional[str]:
    """Obtiene el push token del usuario desde la DB (sincrónico, rápido)."""
    try:
        result = (
            get_supabase()
            .table("users")
            .select("push_token")
            .eq("id", user_id)
            .single()
            .execute()
        )
        return result.data.get("push_token") if result.data else None
    except Exception as exc:
        logger.warning("push: no se pudo obtener token user_id=%s — %s", user_id, exc)
        return None


async def _deliver(token: str, title: str, body: str, data: dict) -> None:
    """Llama a la Expo Push API. Registra errores pero no relanza."""
    payload = {
        "to":    token,
        "title": title,
        "body":  body,
        "data":  data,
        "sound": "default",
        # channelId requerido en Android 8+ — creamos el canal en la app
        "channelId": "bananapay",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            _EXPO_PUSH_URL,
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    if resp.status_code != 200:
        logger.warning("push: Expo API respondió %d — %s", resp.status_code, resp.text[:200])
        return

    result = resp.json().get("data", {})
    status = result.get("status")

    if status == "error":
        details = result.get("details", {})
        error   = result.get("message", "unknown")

        # DeviceNotRegistered → el token expiró, lo borramos para no reintentar
        if details.get("error") == "DeviceNotRegistered":
            logger.info("push: token expirado, limpiando — token=%s", token[:20])
            _clear_push_token_by_token(token)
        else:
            logger.warning("push: entrega fallida status=%s error=%s", status, error)


def _clear_push_token_by_token(token: str) -> None:
    """Borra el push token vencido de la DB para no volver a intentar."""
    try:
        get_supabase().table("users").update({"push_token": None}).eq("push_token", token).execute()
    except Exception:
        pass   # no es crítico


# ─── Helpers de dominio ───────────────────────────────────────────────────────
# Llamadas cortas para los puntos de integración del negocio.

async def notify_transfer_received(
    recipient_user_id: str,
    sender_name:       str,
    amount:            float,
    currency:          str,
) -> None:
    """Push al receptor cuando recibe dinero."""
    symbol = "$" if currency == "USD" else ""
    suffix = f" {currency}" if currency != "USD" else ""
    formatted = f"{symbol}{amount:.2f}{suffix}"

    await send_push(
        user_id=recipient_user_id,
        title="💸 ¡Recibiste dinero!",
        body=f"{formatted} de {sender_name} ya está en tu cuenta.",
        data={"screen": "history"},
    )


async def notify_deposit_approved(
    user_id: str,
    amount:  float,
) -> None:
    """Push al usuario cuando el admin aprueba su depósito."""
    await send_push(
        user_id=user_id,
        title="✅ Depósito aprobado",
        body=f"${amount:.2f} USD acreditados en tu cuenta BananaPay.",
        data={"screen": "home"},
    )
