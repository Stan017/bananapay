"""
Endpoints de depósito desde la app móvil.
- GET  /app/deposit/info        → datos bancarios + wallet TRC-20 del usuario
- POST /app/deposit/fiat        → crea depósito USD pendiente (admin lo aprueba)
"""
from decimal import Decimal, InvalidOperation

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.integrations.supabase_client import get_supabase
from app.modules.fiat.deposits import create_deposit
from app.utils.logger import get_logger

router = APIRouter(prefix="/app/deposit", tags=["app-deposit"])
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


# ─── Info de depósito ─────────────────────────────────────────────────────────

@router.get("/info")
async def get_deposit_info(user_id: str = Depends(_get_user_id)) -> dict:
    """
    Devuelve:
    - Datos bancarios de BananaPay para depósitos USD
    - Dirección TRC-20 del usuario para depósitos USDT/USDC
    """
    db = get_supabase()

    # Wallet TRC-20 del usuario
    user = (
        db.table("users")
        .select("wallet_address")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not user.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {
        "bank": {
            "name":    settings.bananapay_bank_name      or None,
            "account": settings.bananapay_account_number or None,
            "holder":  settings.bananapay_account_holder or None,
            "type":    settings.bananapay_account_type   or "Ahorros",
        },
        "wallet_address": user.data.get("wallet_address"),
    }


# ─── Depósito fiat ────────────────────────────────────────────────────────────

class FiatDepositRequest(BaseModel):
    amount:           float
    bank_name:        str
    reference_number: str


@router.post("/fiat")
async def request_fiat_deposit(
    body:    FiatDepositRequest,
    user_id: str = Depends(_get_user_id),
) -> dict:
    """
    El usuario declara cuánto transfirió y desde qué banco.
    Crea un registro 'pending' — el admin lo aprueba en el panel.
    """
    # Validar monto
    try:
        amount = Decimal(str(body.amount))
        if amount < Decimal("1.00"):
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Monto mínimo: $1.00")

    if not body.bank_name.strip():
        raise HTTPException(status_code=400, detail="Indica el banco desde el que transferiste.")

    if not body.reference_number.strip():
        raise HTTPException(status_code=400, detail="Indica el número de referencia de la transferencia.")

    deposit = await create_deposit(
        user_id=user_id,
        amount=amount,
        bank_name=body.bank_name.strip(),
        reference_number=body.reference_number.strip(),
    )

    logger.info("Depósito fiat solicitado: user=%s amount=%.2f ref=%s", user_id[:8], amount, body.reference_number)

    return {
        "ok":         True,
        "deposit_id": deposit["id"],
        "amount":     float(amount),
        "status":     "pending",
    }
