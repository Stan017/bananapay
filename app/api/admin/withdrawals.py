"""Rutas admin para gestión de retiros pendientes."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.admin.auth import verify_token
from app.integrations.supabase_client import get_supabase
from app.integrations.whatsapp.client import send_message
from app.modules.fiat.withdrawals import get_pending_withdrawals
from app.utils.logger import get_logger

router = APIRouter(prefix="/admin/withdrawals", tags=["admin-withdrawals"])
logger = get_logger(__name__)


class RejectBody(BaseModel):
    notes: str = ""


def _audit(operator_id: str, action: str, target_id: str, notes: str = "") -> None:
    try:
        get_supabase().table("audit_log").insert({
            "operator_id":  operator_id,
            "action":       action,
            "target_table": "withdrawals",
            "target_id":    target_id,
            "notes":        notes,
        }).execute()
    except Exception:
        logger.warning("audit_log insert failed: action=%s target=%s", action, target_id)


async def _notify(phone: str, message: str) -> None:
    try:
        await send_message(phone, message)
    except Exception as e:
        logger.warning("No se pudo notificar al usuario %s: %s", phone, e)


@router.get("/pending")
async def list_pending(token: dict = Depends(verify_token)) -> list:
    return await get_pending_withdrawals()


@router.post("/{withdrawal_id}/approve")
async def approve(withdrawal_id: str, token: dict = Depends(verify_token)) -> dict:
    db = get_supabase()
    result = db.table("withdrawals").update({
        "status":      "approved",
        "approved_by": token["sub"],
        "approved_at": "now()",
    }).eq("id", withdrawal_id).eq("status", "pending").execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Retiro no encontrado o ya procesado")

    wd = result.data[0]

    # Marcar SOLO la transacción vinculada a este retiro específico
    # Filtramos por metadata->withdrawal_id para no tocar otros retiros del mismo usuario
    db.table("transactions").update({"status": "completed"}).eq(
        "from_user_id", wd["user_id"]
    ).eq("tx_type", "withdrawal").eq("status", "pending").contains(
        "metadata", {"withdrawal_id": withdrawal_id}
    ).execute()

    _audit(token["sub"], "approve_withdrawal", withdrawal_id)
    logger.info("Retiro aprobado: id=%s by=%s", withdrawal_id, token["sub"])

    # Notificar al usuario
    try:
        user_res = db.table("users").select("phone, name").eq("id", wd["user_id"]).single().execute()
        user_phone  = user_res.data["phone"]
        user_name   = user_res.data.get("name", "").split()[0]
        receives    = float(wd["amount_received"])
        bank        = wd["bank_name"]
        acc_num     = wd["account_number"]
        acc_holder  = wd.get("account_holder", "")

        # Notificar al dueño de la cuenta
        await _notify(
            user_phone,
            f"✅ *¡Retiro procesado!*\n\n"
            f"💸 *${receives:.2f} USD* fueron transferidos a:\n"
            f"👤 {acc_holder}\n"
            f"🏦 {bank}\n"
            f"🔢 {acc_num}\n\n"
            f"Si no ves el dinero en 24h escríbenos. 🍌"
        )

        # Si era retiro a terceros, notificar al receptor
        recipient_phone = wd.get("recipient_phone")
        if recipient_phone:
            user_name_res = db.table("users").select("name").eq("id", wd["user_id"]).single().execute()
            sender_name = user_name_res.data["name"].split()[0] if user_name_res.data else "Alguien"
            holder = wd.get("account_holder", "")
            await _notify(
                recipient_phone,
                f"💸 *¡Tienes una transferencia!*\n\n"
                f"*{sender_name}* te ha enviado *${receives:.2f} USD*\n"
                f"🏦 {bank}\n"
                f"🔢 {acc_num}\n\n"
                "Enviado vía BananaPay 🍌"
            )
    except Exception as e:
        logger.warning("Error notificando retiro aprobado: %s", e)

    return wd


@router.post("/{withdrawal_id}/reject")
async def reject(withdrawal_id: str, body: RejectBody, token: dict = Depends(verify_token)) -> dict:
    db = get_supabase()

    wd_result = db.table("withdrawals").select("*").eq("id", withdrawal_id).eq("status", "pending").limit(1).execute()
    if not wd_result.data:
        raise HTTPException(status_code=404, detail="Retiro no encontrado o ya procesado")

    wd = wd_result.data[0]
    amount = Decimal(str(wd["amount"]))

    # Paso 1: marcar como rechazado PRIMERO (atómico — evita doble crédito en retry)
    reject_result = db.table("withdrawals").update({
        "status":      "rejected",
        "notes":       body.notes,
        "approved_by": token["sub"],
        "approved_at": "now()",
    }).eq("id", withdrawal_id).eq("status", "pending").execute()

    if not reject_result.data:
        # Otro admin ya lo rechazó entre el SELECT y este UPDATE
        raise HTTPException(status_code=409, detail="Retiro ya fue procesado por otro operador")

    # Paso 2: devolver saldo con RPC atómica (no hay race condition)
    from app.utils.db_ops import credit_wallet
    await credit_wallet(wd["user_id"], "USD", amount)

    # Paso 3: marcar transacción vinculada como fallida
    db.table("transactions").update({"status": "failed"}).eq(
        "from_user_id", wd["user_id"]
    ).eq("tx_type", "withdrawal").eq("status", "pending").contains(
        "metadata", {"withdrawal_id": withdrawal_id}
    ).execute()

    _audit(token["sub"], "reject_withdrawal", withdrawal_id, notes=body.notes)
    logger.info("Retiro rechazado y saldo devuelto: id=%s user=%s amount=%.2f", withdrawal_id, wd["user_id"], amount)

    # Notificar al usuario
    try:
        user_res = db.table("users").select("phone").eq("id", wd["user_id"]).single().execute()
        user_phone = user_res.data["phone"]
        motivo = body.notes or "Datos bancarios incorrectos"
        await _notify(
            user_phone,
            f"❌ *Retiro no procesado*\n\n"
            f"Tu retiro de *${float(amount):.2f}* fue rechazado.\n"
            f"📋 Motivo: _{motivo}_\n\n"
            "💰 Tu saldo fue devuelto íntegramente.\n"
            "Escribe *retirar* para intentar de nuevo."
        )
    except Exception as e:
        logger.warning("Error notificando retiro rechazado: %s", e)

    return {**wd, "status": "rejected"}
