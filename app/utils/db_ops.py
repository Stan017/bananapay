"""
db_ops.py — Operaciones atómicas de balance vía Supabase RPC.
══════════════════════════════════════════════════════════════
Reemplaza el patrón SELECT+UPDATE (race condition) por llamadas RPC
que ejecutan el UPDATE directamente en el motor de BD (PostgreSQL),
garantizando atomicidad sin importar cuántas instancias corran en paralelo.

Requiere haber ejecutado migrations/001_atomic_balance_ops.sql en Supabase.

Uso:
    from app.utils.db_ops import credit_wallet, debit_wallet, transfer_wallets

    new_balance = await credit_wallet(user_id, "USD", Decimal("50.00"))
    new_balance = await debit_wallet(user_id, "USDT", Decimal("10.00"))
    from_bal, to_bal = await transfer_wallets(from_id, to_id, "USD", Decimal("25.00"))
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _rpc_credit(user_id: str, currency: str, amount: Decimal) -> Decimal:
    """Síncrono — llamar vía asyncio.to_thread desde contexto async."""
    from app.integrations.supabase_client import get_supabase
    db = get_supabase()
    result = db.rpc("credit_wallet", {
        "p_user_id":  user_id,
        "p_currency": currency,
        "p_amount":   float(amount),
    }).execute()
    return Decimal(str(result.data))


def _rpc_debit(user_id: str, currency: str, amount: Decimal) -> Decimal:
    """Síncrono — llamar vía asyncio.to_thread desde contexto async."""
    from app.integrations.supabase_client import get_supabase
    db = get_supabase()
    result = db.rpc("debit_wallet", {
        "p_user_id":  user_id,
        "p_currency": currency,
        "p_amount":   float(amount),
    }).execute()
    return Decimal(str(result.data))


def _rpc_transfer(
    from_user_id: str,
    to_user_id: str,
    currency: str,
    amount: Decimal,
) -> tuple[Decimal, Decimal]:
    """Síncrono — llamar vía asyncio.to_thread desde contexto async."""
    from app.integrations.supabase_client import get_supabase
    db = get_supabase()
    result = db.rpc("transfer_between_users", {
        "p_from_user_id": from_user_id,
        "p_to_user_id":   to_user_id,
        "p_currency":     currency,
        "p_amount":       float(amount),
    }).execute()
    row = result.data[0]
    return Decimal(str(row["from_balance"])), Decimal(str(row["to_balance"]))


# ─── API async pública ────────────────────────────────────────────────────────

async def credit_wallet(user_id: str, currency: str, amount: Decimal) -> Decimal:
    """
    Acredita `amount` al wallet (currency) del usuario de forma atómica.
    Retorna el nuevo saldo.
    Lanza RuntimeError si el wallet no existe.
    """
    try:
        new_balance = await asyncio.to_thread(_rpc_credit, user_id, currency, amount)
        logger.debug("credit_wallet: user=%s %s +%.6f → %.6f", user_id[:8], currency, amount, new_balance)
        return new_balance
    except Exception as exc:
        msg = str(exc)
        if "wallet_not_found" in msg:
            raise RuntimeError(f"Wallet no encontrado: user_id={user_id} currency={currency}") from exc
        raise


async def debit_wallet(user_id: str, currency: str, amount: Decimal) -> Decimal:
    """
    Debita `amount` del wallet (currency) del usuario de forma atómica.
    Retorna el nuevo saldo.
    Lanza ValueError si saldo insuficiente.
    Lanza RuntimeError si el wallet no existe.
    """
    try:
        new_balance = await asyncio.to_thread(_rpc_debit, user_id, currency, amount)
        logger.debug("debit_wallet: user=%s %s -%.6f → %.6f", user_id[:8], currency, amount, new_balance)
        return new_balance
    except Exception as exc:
        msg = str(exc)
        if "insufficient_funds" in msg:
            raise ValueError("Saldo insuficiente") from exc
        if "wallet_not_found" in msg:
            raise RuntimeError(f"Wallet no encontrado: user_id={user_id} currency={currency}") from exc
        raise


async def transfer_wallets(
    from_user_id: str,
    to_user_id: str,
    currency: str,
    amount: Decimal,
) -> tuple[Decimal, Decimal]:
    """
    Transfiere `amount` de un wallet a otro en una sola transacción BD.
    Retorna (from_new_balance, to_new_balance).
    Lanza ValueError si el sender no tiene saldo.
    """
    try:
        from_bal, to_bal = await asyncio.to_thread(
            _rpc_transfer, from_user_id, to_user_id, currency, amount
        )
        logger.debug(
            "transfer_wallets: %s → %s %s %.6f",
            from_user_id[:8], to_user_id[:8], currency, amount,
        )
        return from_bal, to_bal
    except Exception as exc:
        msg = str(exc)
        if "insufficient_funds" in msg:
            raise ValueError("Saldo insuficiente") from exc
        if "wallet_not_found" in msg:
            raise RuntimeError(f"Wallet destino no encontrado: to_user_id={to_user_id}") from exc
        raise
