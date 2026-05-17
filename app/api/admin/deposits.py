"""Rutas admin para gestión de depósitos pendientes."""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.admin.auth import verify_token
from app.integrations.supabase_client import get_supabase
from app.integrations.whatsapp.client import fetch_media_bytes, send_message
from app.modules.fiat.deposits import approve_deposit, get_pending_deposits, reject_deposit
from app.modules.fiat.wallet import get_balance
from app.utils.logger import get_logger

_VOUCHER_TOKEN_TTL = 300  # 5 minutos

router = APIRouter(prefix="/admin/deposits", tags=["admin-deposits"])
logger = get_logger(__name__)


class RejectBody(BaseModel):
    notes: str = ""


def _audit(operator_id: str, action: str, target_id: str, notes: str = "") -> None:
    try:
        get_supabase().table("audit_log").insert({
            "operator_id":  operator_id,
            "action":       action,
            "target_table": "deposits",
            "target_id":    target_id,
            "notes":        notes,
        }).execute()
    except Exception:
        logger.warning("audit_log insert failed: action=%s target=%s", action, target_id)


async def _notify_user(phone: str, message: str) -> None:
    try:
        await send_message(phone, message)
    except Exception as e:
        logger.warning("No se pudo notificar al usuario %s: %s", phone, e)


@router.get("/pending")
async def list_pending(token: dict = Depends(verify_token)) -> list:
    return await get_pending_deposits()


@router.post("/{deposit_id}/voucher-token")
async def create_voucher_token(deposit_id: str, token: dict = Depends(verify_token)) -> dict:
    """
    Genera un token efímero de un solo uso para ver el comprobante.
    Válido 5 minutos, se destruye al usarse. El JWT real nunca va en la URL.
    """
    from app.integrations.redis_client import get_redis
    r = await get_redis()
    one_time = secrets.token_urlsafe(32)
    redis_key = f"bp:voucher:{one_time}"
    await r.set(redis_key, deposit_id, ex=_VOUCHER_TOKEN_TTL)
    return {"voucher_token": one_time, "expires_in": _VOUCHER_TOKEN_TTL}


@router.get("/{deposit_id}/voucher")
async def get_voucher(deposit_id: str, voucher_token: str = "") -> Response:
    """
    Descarga el comprobante usando el token efímero de un solo uso.
    El token se destruye inmediatamente después de usarse.
    """
    if not voucher_token:
        raise HTTPException(status_code=401, detail="voucher_token requerido")

    from app.integrations.redis_client import get_redis
    r = await get_redis()
    redis_key = f"bp:voucher:{voucher_token}"

    # Leer y destruir en una operación atómica (GETDEL) — un solo uso garantizado
    stored_deposit_id = await r.getdel(redis_key)
    if not stored_deposit_id:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    # Validar que el token corresponde al deposit_id solicitado
    stored = stored_deposit_id.decode() if isinstance(stored_deposit_id, bytes) else stored_deposit_id
    if stored != deposit_id:
        raise HTTPException(status_code=403, detail="Token no corresponde a este depósito")

    db = get_supabase()
    result = db.table("deposits").select("voucher_media_id").eq("id", deposit_id).limit(1).execute()
    if not result.data or not result.data[0].get("voucher_media_id"):
        raise HTTPException(status_code=404, detail="Sin comprobante")
    try:
        content, mime_type = await fetch_media_bytes(result.data[0]["voucher_media_id"])
    except Exception as e:
        logger.warning("Error descargando voucher %s: %s", deposit_id, e)
        raise HTTPException(status_code=502, detail="No se pudo obtener el comprobante")
    return Response(content=content, media_type=mime_type)


@router.post("/{deposit_id}/approve")
async def approve(deposit_id: str, token: dict = Depends(verify_token)) -> dict:
    result = await approve_deposit(deposit_id, approved_by=token["sub"])
    if not result:
        raise HTTPException(status_code=404, detail="Depósito no encontrado")
    _audit(token["sub"], "approve_deposit", deposit_id)

    # Notificar al usuario (WhatsApp + push a la app)
    try:
        from app.utils.push import notify_deposit_approved
        db = get_supabase()
        user_res = db.table("users").select("phone, id").eq("id", result["user_id"]).single().execute()
        user = user_res.data
        if user:
            balance = await get_balance(user["id"])
            amount = float(result["amount"])
            await _notify_user(
                user["phone"],
                f"✅ *¡Depósito acreditado!*\n\n"
                f"💰 *${amount:.2f} USD* han sido añadidos a tu saldo.\n"
                f"📊 Tu nuevo saldo: *${balance:.2f} USD*\n\n"
                "¡Ya puedes usar tu plata! 🍌"
            )
            # Push notification a la app móvil
            await notify_deposit_approved(user_id=user["id"], amount=amount)
    except Exception as e:
        logger.warning("Error notificando depósito aprobado: %s", e)

    return result


@router.post("/{deposit_id}/reject")
async def reject(deposit_id: str, body: RejectBody, token: dict = Depends(verify_token)) -> dict:
    result = await reject_deposit(deposit_id, notes=body.notes, approved_by=token["sub"])
    if not result:
        raise HTTPException(status_code=404, detail="Depósito no encontrado")
    _audit(token["sub"], "reject_deposit", deposit_id, notes=body.notes)

    # Notificar al usuario
    try:
        db = get_supabase()
        user_res = db.table("users").select("phone").eq("id", result["user_id"]).single().execute()
        user = user_res.data
        if user:
            amount = float(result["amount"])
            motivo = body.notes or "Comprobante no válido"
            await _notify_user(
                user["phone"],
                f"❌ *Depósito no procesado*\n\n"
                f"Tu depósito de *${amount:.2f}* no pudo ser verificado.\n"
                f"📋 Motivo: _{motivo}_\n\n"
                "Escribe *depositar* para intentar de nuevo\n"
                "o contáctanos si crees que es un error."
            )
    except Exception as e:
        logger.warning("Error notificando depósito rechazado: %s", e)

    return result
