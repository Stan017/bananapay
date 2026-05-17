"""
deposit_listener.py — Listener de depósitos TRC-20 (USDT + USDC)
═════════════════════════════════════════════════════════════════
Loop de polling que corre en background cuando arranca el servidor.
Cada POLL_INTERVAL segundos consulta TronGrid por nuevas transacciones
TRC-20 entrantes a las wallets de los usuarios registrados.

Tokens escuchados: USDT y USDC (misma wallet TRC-20, distintos contratos).

Flujo por depósito detectado:
  1. Verifica que (tx_hash, currency) no haya sido procesado antes
  2. Acredita el monto en el wallet del token correspondiente
  3. Registra en crypto_deposits y transactions
  4. Notifica al usuario por WhatsApp
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal

from app.utils.logger import get_logger

logger = get_logger(__name__)

POLL_INTERVAL = 15               # segundos entre cada ciclo de polling
LOOKBACK_MS   = 60 * 60 * 1000  # mirar 1 hora atrás al arrancar


async def _get_all_wallets() -> list[dict]:
    """Retorna todos los usuarios que tienen wallet_address asignada."""
    from app.integrations.supabase_client import get_supabase
    db = get_supabase()
    result = (
        db.table("users")
        .select("id, phone, name, wallet_address")
        .not_.is_("wallet_address", "null")
        .execute()
    )
    return result.data or []


def _is_already_processed(tx_hash: str, currency: str) -> bool:
    """
    Retorna True si (tx_hash, currency) ya está en crypto_deposits.
    Usamos ambos campos porque en teoría un tx podría contener múltiples tokens.
    """
    from app.integrations.supabase_client import get_supabase
    db = get_supabase()
    result = (
        db.table("crypto_deposits")
        .select("id")
        .eq("tx_hash", tx_hash)
        .eq("currency", currency)
        .limit(1)
        .execute()
    )
    return bool(result.data)


async def _credit_deposit(
    user: dict,
    tx_hash: str,
    from_address: str,
    to_address: str,
    amount: float,
    currency: str,
    block_number: int | None,
    timestamp_ms: int,
) -> bool:
    """
    Acredita el depósito al usuario:
    1. Inserta en crypto_deposits (idempotente por tx_hash + currency UNIQUE)
    2. Suma al wallet del token correspondiente (USDT o USDC)
    3. Registra en transactions
    4. Notifica por WhatsApp
    """
    from app.integrations.supabase_client import get_supabase
    from app.integrations.whatsapp.client import send_message
    from app.utils.db_ops import credit_wallet

    db      = get_supabase()
    user_id = user["id"]
    amt     = Decimal(str(amount))

    try:
        # 1. Registrar en crypto_deposits — falla si ya existe (UNIQUE tx_hash + currency)
        db.table("crypto_deposits").insert({
            "tx_hash":      tx_hash,
            "user_id":      user_id,
            "from_address": from_address,
            "to_address":   to_address,
            "amount_usdt":  float(amt),   # columna legacy — guarda el monto independiente del token
            "currency":     currency,
            "block_number": block_number,
        }).execute()

    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            logger.info("deposit_listener: tx ya procesada (race) %s [%s]", tx_hash[:12], currency)
            return False
        logger.error("deposit_listener: error insertando crypto_deposit — %s", exc)
        return False

    try:
        # 2. Acreditar en wallet — UPDATE atómico (sin race condition)
        new_balance = await credit_wallet(user_id, currency, amt)

        # 3. Registrar transacción
        db.table("transactions").insert({
            "to_user_id": user_id,
            "amount":     float(amt),
            "currency":   currency,
            "tx_type":    "deposit",
            "status":     "completed",
            "fee":        0.0,
        }).execute()

        logger.info(
            "deposit_listener: acreditado %.6f %s -> user=%s tx=%s",
            amt, currency, user_id, tx_hash[:12],
        )

        # 4. Notificar al usuario por WhatsApp
        tronscan_url = f"https://tronscan.org/#/transaction/{tx_hash}"
        await send_message(
            user["phone"],
            f"*Recibiste {amt:.2f} {currency}*\n\n"
            f"Tu saldo {currency}: *{new_balance:.2f} {currency}*\n\n"
            f"TX: `{tx_hash[:16]}...`\n"
            f"Ver en blockchain: {tronscan_url}\n\n"
            f"Escribe *menu* para ver tus opciones."
        )
        return True

    except Exception as exc:
        logger.error("deposit_listener: error acreditando %s [%s] — %s", tx_hash[:12], currency, exc)
        return False


async def _poll_wallet(
    user: dict,
    address: str,
    contract_address: str,
    currency: str,
    min_timestamp_ms: int,
) -> int:
    """
    Revisa un token específico para una wallet.
    Retorna el timestamp más reciente encontrado.
    """
    from app.modules.crypto.trongrid import get_incoming_trc20

    latest_ts = min_timestamp_ms
    try:
        txs = await get_incoming_trc20(
            address=address,
            contract_address=contract_address,
            min_timestamp_ms=min_timestamp_ms,
            limit=10,
        )
        for tx in txs:
            ts = tx["timestamp_ms"]
            if ts > latest_ts:
                latest_ts = ts

            if _is_already_processed(tx["tx_hash"], currency):
                logger.debug("deposit_listener: tx ya conocida, skip — %s [%s]",
                             tx["tx_hash"][:16], currency)
                continue

            logger.info(
                "deposit_listener: nueva tx detectada -> %.6f %s para %s",
                tx["amount"], currency, address[:12],
            )
            await _credit_deposit(
                user=user,
                tx_hash=tx["tx_hash"],
                from_address=tx["from_address"],
                to_address=tx["to_address"],
                amount=tx["amount"],
                currency=currency,
                block_number=tx["block_number"],
                timestamp_ms=tx["timestamp_ms"],
            )
    except Exception as exc:
        logger.error("deposit_listener: error procesando wallet %s [%s] — %s",
                     address[:12], currency, exc)

    return latest_ts


async def _poll_once(min_timestamp_ms: int) -> int:
    """
    Un ciclo de polling: revisa todas las wallets para USDT y USDC.
    Retorna el timestamp más reciente encontrado entre todos los tokens.
    """
    from app.modules.crypto.trongrid import USDT_CONTRACT, USDC_CONTRACT

    WATCHED = {
        "USDT": USDT_CONTRACT,
        "USDC": USDC_CONTRACT,
    }

    wallets = await _get_all_wallets()
    if not wallets:
        return min_timestamp_ms

    latest_ts = min_timestamp_ms

    for user in wallets:
        address = user["wallet_address"]

        for currency, contract in WATCHED.items():
            ts = await _poll_wallet(user, address, contract, currency, min_timestamp_ms)
            if ts > latest_ts:
                latest_ts = ts

            # Pausa entre tokens para no exceder rate limit de TronGrid
            await asyncio.sleep(0.3)

        # Pausa entre wallets
        await asyncio.sleep(0.3)

    return latest_ts


async def run_deposit_listener() -> None:
    """
    Loop principal. Corre indefinidamente mientras el servidor está up.
    Escucha USDT y USDC en todas las wallets registradas.
    Arrancar desde main.py (dev) o worker.py (producción).
    """
    logger.info("deposit_listener: iniciando listener TRC-20 (USDT + USDC)...")

    min_ts = int(time.time() * 1000) - LOOKBACK_MS

    while True:
        try:
            new_ts = await _poll_once(min_ts)
            if new_ts > min_ts:
                min_ts = new_ts + 1
        except Exception as exc:
            logger.error("deposit_listener: error en ciclo principal — %s", exc)

        await asyncio.sleep(POLL_INTERVAL)
