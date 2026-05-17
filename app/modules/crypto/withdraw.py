"""
withdraw.py — Retiro USDT TRC-20 on-chain
==========================================
Firma y transmite una transferencia USDT desde la wallet
custodial del usuario hacia una dirección externa TRC-20.

Fee fijo: $1.50 USDT (cubre TRX energy + margen BananaPay)
Mínimo:   $5.00 USDT
"""

from __future__ import annotations

import asyncio
import re
from decimal import Decimal

from app.utils.logger import get_logger

logger = get_logger(__name__)

CONTRACTS = {
    "USDT": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
    "USDC": "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8",
}
USDT_CONTRACT  = CONTRACTS["USDT"]   # alias de compatibilidad
WITHDRAW_FEE   = Decimal("1.50")
WITHDRAW_MIN   = Decimal("5.00")
FEE_LIMIT_SUN  = 20_000_000   # 20 TRX máximo para fees de red

# Regex base58 para dirección TRC-20 (empieza con T, 34 chars)
_TRC20_RE = re.compile(r"^T[A-HJ-NP-Za-km-z1-9]{33}$")


def is_valid_trc20_address(address: str) -> bool:
    return bool(_TRC20_RE.match(address.strip()))


def _send_sync(
    private_key_hex: str,
    from_address: str,
    to_address: str,
    amount: Decimal,
    currency: str = "USDT",
) -> str:
    """
    Ejecuta la transferencia TRC-20 de forma síncrona.
    Soporta USDT y USDC. Retorna tx_hash.
    """
    from tronpy import Tron
    from tronpy.keys import PrivateKey

    contract_address = CONTRACTS.get(currency)
    if not contract_address:
        raise ValueError(f"Moneda no soportada: {currency}")

    client     = Tron(network="mainnet")
    priv       = PrivateKey(bytes.fromhex(private_key_hex))
    amount_sun = int(amount * 1_000_000)   # 6 decimales en TRC-20

    contract = client.get_contract(contract_address)
    txn = (
        contract.functions.transfer(to_address, amount_sun)
        .with_owner(from_address)
        .fee_limit(FEE_LIMIT_SUN)
        .build()
        .sign(priv)
        .broadcast()
    )
    tx_hash = txn.get("txid") or txn.get("transaction", {}).get("txID", "")
    if not tx_hash:
        raise ValueError(f"broadcast no retornó txid: {txn}")

    logger.info("withdraw: tx enviada %s -> %s %.6f %s tx=%s",
                from_address[:10], to_address[:10], amount, currency, tx_hash[:12])
    return tx_hash


async def send_crypto_onchain(
    private_key_hex: str,
    from_address: str,
    to_address: str,
    amount: Decimal,
    currency: str = "USDT",
) -> str:
    """Wrapper async para no bloquear el event loop. Retorna tx_hash."""
    return await asyncio.to_thread(
        _send_sync, private_key_hex, from_address, to_address, amount, currency
    )


# Alias de compatibilidad con el flujo WhatsApp existente
async def send_usdt_onchain(
    private_key_hex: str,
    from_address: str,
    to_address: str,
    amount_usdt: Decimal,
) -> str:
    return await send_crypto_onchain(private_key_hex, from_address, to_address, amount_usdt, "USDT")


async def execute_crypto_withdrawal(
    user_id: str,
    to_address: str,
    amount: Decimal,
    currency: str = "USDT",
) -> dict:
    """
    Pipeline completo de retiro on-chain (USDT o USDC):
      1. Verifica saldo del usuario
      2. Descifra private key
      3. Envía on-chain
      4. Descuenta balance en BD (atómico)
      5. Registra en transactions

    Retorna {"ok": True, "tx_hash": "...", "new_balance": float}
         o  {"ok": False, "error": "..."}
    """
    from app.integrations.supabase_client import get_supabase
    from app.modules.crypto.wallet_manager import decrypt_private_key
    from app.modules.fiat.wallet import get_usdt_balance, get_usdc_balance
    from app.utils.db_ops import debit_wallet

    if currency not in CONTRACTS:
        return {"ok": False, "error": f"Moneda no soportada: {currency}"}

    db = get_supabase()

    # ── 1. Obtener wallet ─────────────────────────────────────────────────────
    user_row = (
        db.table("users")
        .select("wallet_address, wallet_private_key_enc")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not user_row.data:
        return {"ok": False, "error": "No encontré tu wallet."}

    from_address = user_row.data.get("wallet_address")
    enc_key      = user_row.data.get("wallet_private_key_enc")

    if not from_address or not enc_key:
        return {"ok": False, "error": "No tienes una wallet TRC-20 asignada."}

    # ── 2. Verificar saldo ────────────────────────────────────────────────────
    balance      = await (get_usdt_balance(user_id) if currency == "USDT" else get_usdc_balance(user_id))
    total_needed = amount + WITHDRAW_FEE

    if balance < total_needed:
        return {
            "ok":    False,
            "error": f"Saldo insuficiente. Tienes {balance:.2f} {currency} y necesitas {total_needed:.2f} (incluye fee ${WITHDRAW_FEE}).",
        }

    # ── 3. Descifrar private key ──────────────────────────────────────────────
    try:
        private_key_hex = decrypt_private_key(enc_key)
    except Exception as exc:
        logger.error("withdraw: error descifrando key user=%s — %s", user_id, exc)
        return {"ok": False, "error": "Error interno al procesar el retiro."}

    # ── 4. Reservar balance ANTES de enviar (debit primero) ──────────────────
    # Patrón correcto: reservar → broadcast → si broadcast falla, revertir.
    # Esto garantiza que nunca haya dinero salido de blockchain sin que el
    # balance del usuario también haya bajado.
    try:
        new_balance = await debit_wallet(user_id, currency, total_needed)
    except ValueError:
        # Saldo insuficiente — no debería ocurrir si el check del paso 2 fue
        # correcto, pero puede pasar con retiros concurrentes.
        return {"ok": False, "error": f"Saldo insuficiente. Verifica tu saldo {currency}."}
    except Exception as exc:
        logger.error("withdraw: error al debitar pre-broadcast user=%s — %s", user_id, exc)
        return {"ok": False, "error": "Error interno al reservar el saldo. Intenta de nuevo."}

    # ── 5. Enviar on-chain ────────────────────────────────────────────────────
    try:
        tx_hash = await send_crypto_onchain(
            private_key_hex=private_key_hex,
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            currency=currency,
        )
    except Exception as exc:
        # Broadcast falló → revertir el debit para no perder los fondos del usuario
        logger.error("withdraw: error on-chain user=%s currency=%s — %s", user_id, currency, exc)
        try:
            from app.utils.db_ops import credit_wallet
            await credit_wallet(user_id, currency, total_needed)
            logger.info("withdraw: rollback OK — saldo restaurado user=%s", user_id)
        except Exception as rev_exc:
            logger.error("withdraw: ALERTA rollback falló user=%s — %s", user_id, rev_exc)

        err_str = str(exc).lower()
        if "429" in err_str or "too many" in err_str:
            msg = "La red TRON está ocupada. Intenta en unos minutos."
        elif "balance" in err_str or "energy" in err_str or "bandwidth" in err_str:
            msg = "Fondos insuficientes para el fee de red. Intenta con un monto menor."
        else:
            msg = "No se pudo procesar el retiro. Intenta de nuevo."
        return {"ok": False, "error": msg}

    # ── 6. Registrar transacción ──────────────────────────────────────────────
    db.table("transactions").insert({
        "from_user_id": user_id,
        "amount":       float(amount),
        "currency":     currency,
        "tx_type":      "withdrawal",
        "status":       "completed",
        "fee":          float(WITHDRAW_FEE),
    }).execute()

    logger.info("withdraw: OK user=%s %.6f %s -> %s tx=%s",
                user_id, amount, currency, to_address[:12], tx_hash[:12])

    return {"ok": True, "tx_hash": tx_hash, "new_balance": float(new_balance)}


# Alias de compatibilidad con el flujo WhatsApp existente
async def execute_usdt_withdrawal(
    user_id: str,
    to_address: str,
    amount_usdt: Decimal,
) -> dict:
    return await execute_crypto_withdrawal(user_id, to_address, amount_usdt, "USDT")
