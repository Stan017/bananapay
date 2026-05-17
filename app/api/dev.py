"""
dev.py — Endpoints de prueba (solo disponibles en APP_ENV=development)
Permiten simular eventos sin necesitar fondos reales ni blockchain.
"""

import time
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/dev", tags=["dev"])


def _guard():
    """Bloquea estos endpoints en producción."""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")


# ─── Simular depósito USDT ────────────────────────────────────────────────────

class SimulateDepositBody(BaseModel):
    phone: str          # ej: "+593991234567"
    amount_usdt: float  # ej: 10.5


@router.post("/simulate-usdt-deposit")
async def simulate_usdt_deposit(body: SimulateDepositBody):
    """
    Simula que el listener TronGrid detectó un depósito USDT.
    Llama a _credit_deposit() directamente — mismo código que en producción.
    Útil para probar sin tener USDT real.
    """
    _guard()

    from app.modules.auth.register import get_user_by_phone
    from app.modules.crypto.wallet_manager import assign_wallet_to_user
    from app.modules.crypto.deposit_listener import _credit_deposit

    user = await get_user_by_phone(body.phone)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Asignar wallet si no tiene
    wallet = await assign_wallet_to_user(user["id"])
    address = wallet["address"]

    # Tx hash falso pero único
    fake_tx_hash = "TEST_" + uuid.uuid4().hex.upper()

    ok = await _credit_deposit(
        user={**user, "wallet_address": address},
        tx_hash=fake_tx_hash,
        from_address="TFakeFromAddressForTesting000000000",
        to_address=address,
        amount_usdt=body.amount_usdt,
        block_number=None,
        timestamp_ms=int(time.time() * 1000),
    )

    if not ok:
        raise HTTPException(status_code=500, detail="Error al acreditar (revisa logs)")

    return {
        "ok": True,
        "tx_hash": fake_tx_hash,
        "phone": body.phone,
        "amount_usdt": body.amount_usdt,
        "wallet_address": address,
        "message": "Deposito simulado. El usuario debio recibir notificacion por WhatsApp.",
    }


# ─── Simular retiro USDT ──────────────────────────────────────────────────────

class SimulateWithdrawBody(BaseModel):
    phone: str          # ej: "+593991234567"
    amount_usdt: float  # ej: 20.0
    to_address: str = "TFakeDestinationAddress000000000000"


@router.post("/simulate-usdt-withdraw")
async def simulate_usdt_withdraw(body: SimulateWithdrawBody):
    """
    Simula un retiro USDT sin enviar nada on-chain.
    Descuenta el saldo + fee igual que en producción, pero el tx_hash es falso.
    """
    _guard()

    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_usdt_balance
    from app.modules.crypto.withdraw import WITHDRAW_FEE, WITHDRAW_MIN
    from app.integrations.supabase_client import get_supabase

    user = await get_user_by_phone(body.phone)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    amount  = Decimal(str(body.amount_usdt))
    balance = await get_usdt_balance(user["id"])

    if amount < WITHDRAW_MIN:
        raise HTTPException(status_code=400, detail=f"Mínimo {WITHDRAW_MIN} USDT")

    total = amount + WITHDRAW_FEE
    if balance < total:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo insuficiente: tienes {balance:.2f}, necesitas {total:.2f}"
        )

    db = get_supabase()
    new_balance = balance - total

    # Descontar saldo
    db.table("wallets").update({
        "balance": float(new_balance),
    }).eq("user_id", user["id"]).eq("currency", "USDT").execute()

    # Registrar transacción
    fake_tx = "TEST_WD_" + uuid.uuid4().hex.upper()
    db.table("transactions").insert({
        "from_user_id": user["id"],
        "amount":       float(amount),
        "currency":     "USDT",
        "tx_type":      "withdrawal",
        "status":       "completed",
        "fee":          float(WITHDRAW_FEE),
    }).execute()

    # Notificar al usuario por WhatsApp
    from app.integrations.whatsapp.client import send_message
    tronscan = f"https://tronscan.org/#/transaction/{fake_tx}"
    try:
        await send_message(
            user["phone"],
            f"✅ *¡USDT enviado!*\n\n"
            f"🪙 *{amount:.2f} USDT* en camino a tu wallet\n\n"
            f"TX: `{fake_tx[:20]}...`\n"
            f"🔍 {tronscan}\n\n"
            f"💰 Saldo restante: *{float(new_balance):.2f} USDT*\n\n"
            f"_Confirmación en la blockchain en ~1 minuto_"
        )
    except Exception as e:
        pass

    return {
        "ok": True,
        "tx_hash": fake_tx,
        "amount_usdt": float(amount),
        "fee": float(WITHDRAW_FEE),
        "new_balance": float(new_balance),
        "to_address": body.to_address,
        "message": "Retiro simulado. Saldo descontado sin transaccion on-chain.",
    }
