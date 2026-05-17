"""Operaciones de retiros en Supabase."""

import datetime
from decimal import Decimal

from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── Límites de negocio ───────────────────────────────────────────────────────

MAX_SINGLE_WITHDRAWAL  = Decimal("300.00")   # Máximo por retiro
MAX_DAILY_WITHDRAWAL   = Decimal("500.00")   # Máximo acumulado por día
COOLDOWN_MINUTES       = 30                  # Minutos entre retiros


async def check_withdrawal_limits(user_id: str, amount: Decimal) -> str | None:
    """
    Valida los límites de retiro antes de continuar el flujo.
    Retorna un mensaje de error si hay alguna restricción, o None si todo OK.
    """
    db = get_supabase()

    # 1. Límite por retiro individual
    if amount > MAX_SINGLE_WITHDRAWAL:
        return (
            f"❌ El máximo por retiro es *${MAX_SINGLE_WITHDRAWAL:.2f}*.\n"
            f"Para montos mayores contáctanos: escribe *soporte*."
        )

    # 2. Retiro pendiente existente
    pending = (
        db.table("withdrawals")
        .select("id, amount, created_at")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .limit(1)
        .execute()
    )
    if pending.data:
        p = pending.data[0]
        return (
            f"⏳ Ya tienes un retiro pendiente de *${float(p['amount']):.2f}* en proceso.\n"
            "Espera a que sea procesado antes de solicitar otro."
        )

    # 3. Cooldown entre retiros
    since = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=COOLDOWN_MINUTES)
    ).isoformat()
    recent = (
        db.table("withdrawals")
        .select("id, created_at")
        .eq("user_id", user_id)
        .in_("status", ["pending", "approved"])
        .gte("created_at", since)
        .limit(1)
        .execute()
    )
    if recent.data:
        return (
            f"⏱️ Debes esperar *{COOLDOWN_MINUTES} minutos* entre retiros.\n"
            "Es una medida de seguridad para proteger tu cuenta."
        )

    # 4. Límite diario acumulado
    today_start = datetime.datetime.now(datetime.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    today_wd = (
        db.table("withdrawals")
        .select("amount")
        .eq("user_id", user_id)
        .in_("status", ["pending", "approved"])
        .gte("created_at", today_start)
        .execute()
    )
    daily_total = Decimal("0")
    for row in (today_wd.data or []):
        daily_total += Decimal(str(row["amount"]))

    if daily_total + amount > MAX_DAILY_WITHDRAWAL:
        remaining = MAX_DAILY_WITHDRAWAL - daily_total
        return (
            f"📊 Límite diario alcanzado.\n"
            f"Ya retiraste *${daily_total:.2f}* hoy. "
            f"Puedes retirar hasta *${max(remaining, 0):.2f}* más hoy.\n"
            f"El límite se reinicia a medianoche."
        )

    return None  # Todo OK


def check_holder_name(user_name: str, account_holder: str) -> bool:
    """
    Verifica si el titular de la cuenta tiene al menos 1 apellido en común
    con el nombre registrado en KYC. Retorna False si hay discrepancia.
    """
    user_words    = {w.lower() for w in user_name.split() if len(w) > 2}
    holder_words  = {w.lower() for w in account_holder.split() if len(w) > 2}
    return bool(user_words & holder_words)


async def create_withdrawal(
    user_id: str,
    amount: Decimal,
    fee: Decimal,
    amount_received: Decimal,
    withdrawal_type: str,
    bank_name: str,
    account_type: str,
    account_number: str,
    account_holder: str,
    recipient_phone: str | None = None,
    recipient_cedula: str | None = None,
) -> dict:
    """
    Crea un retiro pendiente llamando a la RPC create_withdrawal() en PostgreSQL.

    La RPC ejecuta los 3 pasos en UNA SOLA transacción DB:
      1. UPDATE wallets SET balance = balance - amount WHERE balance >= amount  (atómico)
      2. INSERT INTO withdrawals                                                (mismo commit)
      3. INSERT INTO transactions                                               (mismo commit)

    Si cualquier paso falla → rollback total. Nunca queda dinero debitado
    sin registro de retiro, ni un retiro sin transacción asociada.
    """
    import asyncio
    db = get_supabase()

    try:
        result = await asyncio.to_thread(
            lambda: db.rpc("create_withdrawal", {
                "p_user_id":          user_id,
                "p_amount":           float(amount),
                "p_fee":              float(fee),
                "p_amount_received":  float(amount_received),
                "p_withdrawal_type":  withdrawal_type,
                "p_bank_name":        bank_name,
                "p_account_type":     account_type,
                "p_account_number":   account_number,
                "p_account_holder":   account_holder,
                "p_recipient_phone":  recipient_phone,
                "p_recipient_cedula": recipient_cedula,
            }).execute()
        )
        data = result.data
        withdrawal_id = data.get("withdrawal_id") if data else None

        if not withdrawal_id:
            raise RuntimeError("create_withdrawal RPC no retornó withdrawal_id")

        # Retornar el withdrawal completo para el flujo del handler
        wd_result = await asyncio.to_thread(
            lambda: db.table("withdrawals").select("*").eq("id", withdrawal_id).limit(1).execute()
        )
        withdrawal = wd_result.data[0]
        logger.info(
            "Retiro creado: id=%s user=%s amount=%.2f type=%s",
            withdrawal_id, user_id, amount, withdrawal_type,
        )
        return withdrawal

    except Exception as exc:
        msg = str(exc)
        if "insufficient_funds" in msg:
            raise ValueError("Saldo insuficiente") from exc
        if "wallet_not_found" in msg:
            raise ValueError("Wallet no encontrado") from exc
        logger.error("create_withdrawal RPC error: %s", exc)
        raise


async def get_pending_withdrawals() -> list[dict]:
    """Retorna todos los retiros pendientes para el admin."""
    db = get_supabase()
    result = (
        db.table("withdrawals")
        .select("*, user:users(name, phone)")
        .eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


async def get_user_bank_account(user_id: str) -> dict | None:
    """Retorna la cuenta bancaria guardada del usuario (la default)."""
    db = get_supabase()
    result = (
        db.table("user_bank_accounts")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_default", True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def save_bank_account(
    user_id: str,
    bank_name: str,
    account_type: str,
    account_number: str,
    account_holder: str,
) -> dict:
    """Guarda o actualiza la cuenta bancaria del usuario."""
    db = get_supabase()

    # Desactivar cuentas anteriores
    db.table("user_bank_accounts").update({"is_default": False}).eq("user_id", user_id).execute()

    result = db.table("user_bank_accounts").insert({
        "user_id":        user_id,
        "bank_name":      bank_name,
        "account_type":   account_type,
        "account_number": account_number,
        "account_holder": account_holder,
        "is_default":     True,
    }).execute()
    return result.data[0]
