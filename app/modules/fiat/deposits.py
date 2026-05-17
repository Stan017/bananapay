"""Operaciones de depósitos en Supabase."""

from decimal import Decimal

from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_deposit(
    user_id: str,
    amount: Decimal,
    bank_name: str | None = None,
    reference_number: str | None = None,
    voucher_media_id: str | None = None,
    voucher_hash: str | None = None,
    voucher_local_path: str | None = None,
    vision_verdict: str | None = None,
    vision_confidence: float | None = None,
    vision_reason: str | None = None,
) -> dict:
    """Crea un depósito en estado 'pending' y lo retorna."""
    db = get_supabase()
    payload = {
        "user_id": user_id,
        "amount": float(amount),
        "status": "pending",
    }
    if bank_name:
        payload["bank_name"] = bank_name
    if reference_number:
        payload["reference_number"] = reference_number
    if voucher_media_id:
        payload["voucher_media_id"] = voucher_media_id
    if voucher_hash:
        payload["voucher_hash"] = voucher_hash
    if voucher_local_path:
        payload["voucher_local_path"] = voucher_local_path
    if vision_verdict:
        payload["vision_verdict"] = vision_verdict
    if vision_confidence is not None:
        payload["vision_confidence"] = vision_confidence
    if vision_reason:
        payload["vision_reason"] = vision_reason

    result = db.table("deposits").insert(payload).execute()
    deposit = result.data[0]
    logger.info("Depósito creado: id=%s user=%s amount=%.2f", deposit["id"], user_id, amount)
    return deposit


async def get_pending_deposits() -> list[dict]:
    """Retorna todos los depósitos pendientes (para el admin)."""
    db = get_supabase()
    result = (
        db.table("deposits")
        .select("*, user:users(name, phone, cedula)")
        .eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


async def approve_deposit(deposit_id: str, approved_by: str = "admin") -> dict | None:
    """
    Aprueba un depósito llamando a la RPC approve_deposit() en PostgreSQL.

    La RPC ejecuta los 3 pasos en UNA SOLA transacción DB:
      1. UPDATE deposits SET status='approved' WHERE status='pending'  (atómico)
      2. UPDATE wallets SET balance = balance + amount                 (atómico)
      3. INSERT INTO transactions                                      (mismo commit)

    Si cualquier paso falla → rollback total. Nunca queda un depósito aprobado
    sin crédito, ni un crédito sin registro en transactions.
    """
    import asyncio
    db = get_supabase()

    try:
        result = await asyncio.to_thread(
            lambda: db.rpc("approve_deposit", {
                "p_deposit_id":  deposit_id,
                "p_approved_by": approved_by,
            }).execute()
        )
        data = result.data
        if not data:
            return None

        logger.info(
            "Depósito aprobado: id=%s user=%s amount=%.2f",
            deposit_id, data.get("user_id"), data.get("amount"),
        )
        # Retornar el depósito completo para el panel admin
        dep_result = await asyncio.to_thread(
            lambda: db.table("deposits").select("*").eq("id", deposit_id).limit(1).execute()
        )
        return dep_result.data[0] if dep_result.data else data

    except Exception as exc:
        msg = str(exc)
        if "deposit_not_pending" in msg:
            # Ya fue procesado por otro admin — retornar estado actual
            dep_result = await asyncio.to_thread(
                lambda: db.table("deposits").select("*").eq("id", deposit_id).limit(1).execute()
            )
            return dep_result.data[0] if dep_result.data else None
        logger.error("approve_deposit RPC error: %s", exc)
        raise


async def reject_deposit(deposit_id: str, notes: str = "", approved_by: str = "admin") -> dict | None:
    """Rechaza un depósito con motivo."""
    db = get_supabase()
    result = db.table("deposits").update({
        "status":      "rejected",
        "notes":       notes,
        "approved_by": approved_by,
        "approved_at": "now()",
    }).eq("id", deposit_id).execute()
    return result.data[0] if result.data else None
