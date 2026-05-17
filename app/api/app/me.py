"""
Endpoints del usuario autenticado en la app mobile.
Todos requieren Bearer JWT emitido por /app/auth/login.
"""

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.core.limiter import limiter
from app.integrations.supabase_client import get_supabase
from app.modules.fiat.wallet import get_balances, get_history
from app.utils.logger import get_logger

router = APIRouter(prefix="/app/me", tags=["app-me"])
logger = get_logger(__name__)

# Campos seguros que puede ver el usuario — pin_hash NUNCA incluido
_PROFILE_SAFE_FIELDS = {
    "id", "name", "phone", "cedula", "email",
    "kyc_level", "custody_mode", "wallet_address", "created_at",
}

_bearer = HTTPBearer()


def _get_user_id(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")


@router.get("/balance")
@limiter.limit("60/minute")     # 1 req/seg — más que suficiente para refresh automático
async def get_balance(request: Request, user_id: str = Depends(_get_user_id)) -> dict:
    """Saldo USD, USDT y USDC del usuario."""
    balances = await get_balances(user_id)
    return {
        "fiat":  float(balances["fiat"]),
        "usdt":  float(balances["usdt"]),
        "usdc":  float(balances["usdc"]),
        "total": float(balances["total"]),
    }


@router.get("/history")
@limiter.limit("30/minute")     # historial no necesita refresh tan frecuente
async def get_tx_history(
    request: Request,
    limit: int = 20,
    user_id: str = Depends(_get_user_id),
) -> list:
    """Últimas transacciones del usuario (máx 50)."""
    limit = min(limit, 50)
    txs = await get_history(user_id, limit=limit)

    result = []
    for tx in txs:
        es_recibido = tx["to_user_id"] == user_id
        result.append({
            "id":          tx["id"],
            "type":        tx.get("tx_type", "transfer"),
            "currency":    tx.get("currency", "USD"),
            "amount":      float(tx["amount"]),
            "fee":         float(tx.get("fee") or 0),
            "direction":   "in" if es_recibido else "out",
            "other_name":  tx.get("other_name") or "BananaPay",
            "status":      tx.get("status", "completed"),
            "created_at":  tx.get("created_at", ""),
        })
    return result


@router.get("/profile")
@limiter.limit("20/minute")
async def get_profile(request: Request, user_id: str = Depends(_get_user_id)) -> dict:
    """Datos del perfil del usuario incluyendo wallet address."""
    db = get_supabase()
    result = (
        db.table("users")
        .select("id, name, phone, cedula, email, kyc_level, custody_mode, wallet_address, created_at")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    # Filtrar explícitamente — nunca retornar pin_hash ni campos internos
    return {k: v for k, v in result.data.items() if k in _PROFILE_SAFE_FIELDS}


# ─── Push token ───────────────────────────────────────────────────────────────

class PushTokenBody(BaseModel):
    token: str   # ExpoToken formato: ExponentPushToken[xxxxxx] o token nativo


@router.patch("/push-token")
@limiter.limit("10/minute")
async def update_push_token(
    request:  Request,
    body:     PushTokenBody,
    user_id:  str = Depends(_get_user_id),
) -> dict:
    """
    Registra o actualiza el Expo push token del dispositivo.
    La app lo llama al iniciar sesión y cada vez que el token se regenera.
    """
    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token vacío")

    db = get_supabase()
    db.table("users").update({"push_token": token}).eq("id", user_id).execute()
    logger.info("push_token actualizado user_id=%s token=%s…", user_id[:8], token[:20])
    return {"ok": True}
