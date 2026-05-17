"""
Endpoints de retiro desde la app móvil.
- GET  /app/withdraw/info      → cuenta bancaria guardada + límites
- POST /app/withdraw/fiat      → retiro USD a cuenta bancaria
- POST /app/withdraw/crypto    → retiro USDT / USDC on-chain
"""
from decimal import Decimal, InvalidOperation

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.core.fees import WithdrawalType, calculate_fee
from app.core.security import verify_pin
from app.integrations.supabase_client import get_supabase
from app.modules.crypto.withdraw import (
    WITHDRAW_FEE,
    WITHDRAW_MIN,
    execute_crypto_withdrawal,
    is_valid_trc20_address,
)
from app.modules.fiat.withdrawals import (
    check_withdrawal_limits,
    create_withdrawal,
    get_user_bank_account,
    save_bank_account,
)
from app.utils.logger import get_logger

router = APIRouter(prefix="/app/withdraw", tags=["app-withdraw"])
logger = get_logger(__name__)

_bearer = HTTPBearer()


def _get_user_id(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")


# ─── Info ─────────────────────────────────────────────────────────────────────

@router.get("/info")
async def get_withdraw_info(user_id: str = Depends(_get_user_id)) -> dict:
    """Devuelve cuenta bancaria guardada del usuario y límites de retiro."""
    saved = await get_user_bank_account(user_id)
    return {
        "saved_bank": saved,
        "limits": {
            "max_single":       300.00,
            "max_daily":        500.00,
            "min_fiat":         10.00,
            "cooldown_minutes": 30,
            "min_crypto":       float(WITHDRAW_MIN),
            "crypto_fee":       float(WITHDRAW_FEE),
        },
    }


# ─── Retiro fiat ──────────────────────────────────────────────────────────────

class FiatWithdrawRequest(BaseModel):
    amount:          float
    withdrawal_type: str        # "normal" | "instant"
    bank_name:       str
    account_type:    str        # "Ahorros" | "Corriente"
    account_number:  str
    account_holder:  str
    pin:             str


@router.post("/fiat")
async def withdraw_fiat(
    body:    FiatWithdrawRequest,
    user_id: str = Depends(_get_user_id),
) -> dict:
    """Crea un retiro USD pendiente. Descuenta saldo inmediatamente."""
    db = get_supabase()

    # ── Validar monto ─────────────────────────────────────────────────────────
    try:
        amount = Decimal(str(body.amount))
        if amount <= 0:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Monto inválido.")

    # ── Validar tipo ──────────────────────────────────────────────────────────
    try:
        wtype = WithdrawalType(body.withdrawal_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Tipo de retiro inválido. Usa 'normal' o 'instant'.")

    # ── Validar campos bancarios ──────────────────────────────────────────────
    if not body.bank_name.strip():
        raise HTTPException(status_code=400, detail="Indica el banco.")
    if body.account_type not in ("Ahorros", "Corriente"):
        raise HTTPException(status_code=400, detail="Tipo de cuenta debe ser Ahorros o Corriente.")
    if not body.account_number.strip().isdigit() or len(body.account_number.strip()) < 10:
        raise HTTPException(status_code=400, detail="Número de cuenta inválido (mínimo 10 dígitos).")
    if not body.account_holder.strip():
        raise HTTPException(status_code=400, detail="Indica el titular de la cuenta.")

    # ── Verificar PIN ─────────────────────────────────────────────────────────
    user = db.table("users").select("pin_hash").eq("id", user_id).single().execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if not verify_pin(body.pin, user.data["pin_hash"]):
        raise HTTPException(status_code=401, detail="PIN incorrecto.")

    # ── Verificar límites ─────────────────────────────────────────────────────
    limit_error = await check_withdrawal_limits(user_id, amount)
    if limit_error:
        # El mensaje viene con markdown de WhatsApp — limpiarlo para la app
        clean = limit_error.replace("*", "").replace("_", "")
        raise HTTPException(status_code=400, detail=clean)

    # ── Calcular fee ──────────────────────────────────────────────────────────
    try:
        fee      = calculate_fee(amount, wtype)
        receives = amount - fee
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # ── Crear retiro ──────────────────────────────────────────────────────────
    try:
        withdrawal = await create_withdrawal(
            user_id=user_id,
            amount=amount,
            fee=fee,
            amount_received=receives,
            withdrawal_type=wtype.value,
            bank_name=body.bank_name.strip(),
            account_type=body.account_type,
            account_number=body.account_number.strip(),
            account_holder=body.account_holder.strip(),
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")
    except Exception as exc:
        logger.error("withdraw_fiat error: %s", exc)
        raise HTTPException(status_code=500, detail="Error al procesar el retiro.")

    # Guardar cuenta bancaria para la próxima vez
    try:
        await save_bank_account(user_id, body.bank_name.strip(), body.account_type,
                                body.account_number.strip(), body.account_holder.strip())
    except Exception:
        pass

    logger.info("Retiro fiat: user=%s amount=%.2f type=%s", user_id[:8], amount, wtype.value)

    return {
        "ok":             True,
        "withdrawal_id":  withdrawal["id"],
        "amount":         float(amount),
        "fee":            float(fee),
        "amount_received": float(receives),
        "withdrawal_type": wtype.value,
        "status":         "pending",
    }


# ─── Retiro crypto ────────────────────────────────────────────────────────────

class CryptoWithdrawRequest(BaseModel):
    currency:   str     # "USDT" | "USDC"
    amount:     float
    to_address: str
    pin:        str


@router.post("/crypto")
async def withdraw_crypto(
    body:    CryptoWithdrawRequest,
    user_id: str = Depends(_get_user_id),
) -> dict:
    """Retiro on-chain USDT o USDC a una dirección TRC-20 externa."""
    db = get_supabase()

    # ── Validaciones ──────────────────────────────────────────────────────────
    if body.currency not in ("USDT", "USDC"):
        raise HTTPException(status_code=400, detail="Moneda inválida. Usa USDT o USDC.")

    try:
        amount = Decimal(str(body.amount))
        if amount < WITHDRAW_MIN:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail=f"Monto mínimo: {WITHDRAW_MIN} {body.currency}.")

    if not is_valid_trc20_address(body.to_address):
        raise HTTPException(status_code=400, detail="Dirección TRC-20 inválida. Debe empezar con T y tener 34 caracteres.")

    # ── Verificar PIN ─────────────────────────────────────────────────────────
    user = db.table("users").select("pin_hash").eq("id", user_id).single().execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if not verify_pin(body.pin, user.data["pin_hash"]):
        raise HTTPException(status_code=401, detail="PIN incorrecto.")

    # ── Ejecutar retiro on-chain ──────────────────────────────────────────────
    result = await execute_crypto_withdrawal(
        user_id=user_id,
        to_address=body.to_address.strip(),
        amount=amount,
        currency=body.currency,
    )

    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])

    logger.info("Retiro crypto OK: user=%s %.4f %s -> %s",
                user_id[:8], amount, body.currency, body.to_address[:12])

    return {
        "ok":          True,
        "tx_hash":     result["tx_hash"],
        "amount":      float(amount),
        "fee":         float(WITHDRAW_FEE),
        "currency":    body.currency,
        "new_balance": result["new_balance"],
    }
