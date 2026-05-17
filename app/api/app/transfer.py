"""
Endpoints de transferencia P2P desde la app móvil.
Fee entre usuarios BananaPay: 0%
"""
from decimal import Decimal, InvalidOperation

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.core.limiter import limiter
from app.core.security import verify_pin
from app.integrations.supabase_client import get_supabase
from app.utils.db_ops import transfer_wallets
from app.utils.logger import get_logger
from app.utils.phone import normalize_phone

router = APIRouter(prefix="/app/transfer", tags=["app-transfer"])
logger = get_logger(__name__)

_bearer = HTTPBearer()

CURRENCIES = {"USD", "USDT", "USDC"}


def _get_user_id(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")


# ─── Validar destinatario ─────────────────────────────────────────────────────

@router.get("/validate")
@limiter.limit("30/minute")   # búsqueda de destinatario — no necesita más
async def validate_recipient(
    request: Request,
    cedula: str,
    phone:  str,
    user_id: str = Depends(_get_user_id),
) -> dict:
    """
    Busca al destinatario por cédula + teléfono.
    Devuelve su nombre si existe.
    """
    db = get_supabase()

    normalized = normalize_phone(phone.strip())
    if not normalized:
        raise HTTPException(status_code=400, detail="Número de teléfono inválido")

    result = (
        db.table("users")
        .select("id, name")
        .eq("cedula", cedula.strip())
        .eq("phone",  normalized)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="No encontramos ninguna cuenta con esa cédula y teléfono.",
        )

    if result.data["id"] == user_id:
        raise HTTPException(status_code=400, detail="No puedes enviarte dinero a ti mismo.")

    return {"name": result.data["name"]}


# ─── Ejecutar transferencia ───────────────────────────────────────────────────

class TransferRequest(BaseModel):
    to_cedula: str
    to_phone:  str
    amount:    float
    currency:  str   # USD | USDT | USDC
    pin:       str


@router.post("/send")
@limiter.limit("10/minute")   # transferencias reales — límite estricto anti-flood
async def send_transfer(
    request: Request,
    body:    TransferRequest,
    user_id: str = Depends(_get_user_id),
) -> dict:
    """Ejecuta una transferencia P2P. Atómica, 0% de comisión."""
    db = get_supabase()

    # ── Validaciones básicas ──────────────────────────────────────────────────
    if body.currency not in CURRENCIES:
        raise HTTPException(status_code=400, detail="Moneda inválida. Usa USD, USDT o USDC.")

    try:
        amount = Decimal(str(body.amount))
        if amount <= 0:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Monto inválido.")

    # ── Obtener sender y verificar PIN ────────────────────────────────────────
    sender = (
        db.table("users")
        .select("id, name, pin_hash")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not sender.data:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    if not verify_pin(body.pin, sender.data["pin_hash"]):
        raise HTTPException(status_code=401, detail="PIN incorrecto.")

    # ── Buscar destinatario ───────────────────────────────────────────────────
    normalized = normalize_phone(body.to_phone.strip())
    if not normalized:
        raise HTTPException(status_code=400, detail="Teléfono del destinatario inválido.")

    recipient = (
        db.table("users")
        .select("id, name")
        .eq("cedula", body.to_cedula.strip())
        .eq("phone",  normalized)
        .single()
        .execute()
    )
    if not recipient.data:
        raise HTTPException(status_code=404, detail="Destinatario no encontrado.")

    if recipient.data["id"] == user_id:
        raise HTTPException(status_code=400, detail="No puedes enviarte dinero a ti mismo.")

    # ── Transferencia atómica ─────────────────────────────────────────────────
    try:
        await transfer_wallets(
            user_id,
            recipient.data["id"],
            body.currency,
            amount,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")
    except RuntimeError as exc:
        logger.error("transfer_wallets error: %s", exc)
        raise HTTPException(status_code=500, detail="Error al procesar la transferencia.")

    # La RPC transfer_between_users ya registra en transactions dentro de la
    # misma transacción DB. No insertamos aquí para evitar duplicados.
    logger.info(
        "Transfer OK: %s → %s %s %.4f",
        user_id[:8], recipient.data["id"][:8], body.currency, amount,
    )

    # Push notification al receptor (fire-and-forget)
    try:
        from app.utils.push import notify_transfer_received
        sender_name = sender.data["name"].split()[0]  # solo el primer nombre
        await notify_transfer_received(
            recipient_user_id=recipient.data["id"],
            sender_name=sender_name,
            amount=float(amount),
            currency=body.currency,
        )
    except Exception as exc:
        logger.warning("push transfer: %s", exc)

    return {
        "ok":       True,
        "to_name":  recipient.data["name"],
        "amount":   float(amount),
        "currency": body.currency,
    }
