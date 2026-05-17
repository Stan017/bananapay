"""
Autenticación mobile — cédula + teléfono + PIN → JWT.
"""

import datetime

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.core.limiter import limiter
from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

router = APIRouter(prefix="/app/auth", tags=["app-auth"])
logger = get_logger(__name__)

_JWT_ALGORITHM = "HS256"
_TOKEN_TTL_DAYS = 30


class LoginBody(BaseModel):
    cedula:  str
    phone:   str      # formato E.164: +593XXXXXXXXX  o solo 09XXXXXXXX
    pin:     str      # 6 dígitos numéricos


class LoginResponse(BaseModel):
    token:   str
    user_id: str
    name:    str
    phone:   str


def _normalize_phone(phone: str) -> str:
    """Acepta 0997097262 o +593997097262 y devuelve +593997097262."""
    phone = phone.strip()
    if phone.startswith("0") and not phone.startswith("00"):
        return "+593" + phone[1:]
    return phone


def _make_token(user: dict) -> str:
    payload = {
        "sub":   user["id"],
        "phone": user["phone"],
        "exp":   datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=_TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[_JWT_ALGORITHM])


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")         # 10 intentos/minuto por IP → 429
async def login(request: Request, body: LoginBody) -> LoginResponse:
    db    = get_supabase()
    phone = _normalize_phone(body.phone)

    # 1. Buscar usuario por teléfono
    result = (
        db.table("users")
        .select("id, name, phone, cedula, pin_hash, is_active")
        .eq("phone", phone)
        .limit(1)
        .execute()
    )
    user = (result.data or [None])[0]

    if not user:
        logger.warning("app/login: teléfono no encontrado phone=%s", phone)
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # 2. Verificar cuenta activa
    if not user.get("is_active", True) is False:
        pass  # is_active puede ser None en registros viejos → permitir
    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    # 3. Verificar cédula
    if user.get("cedula", "").strip() != body.cedula.strip():
        logger.warning("app/login: cédula incorrecta phone=%s", phone)
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # 4. Verificar PIN (strip() previene fallos por espacios invisibles)
    if not user.get("pin_hash"):
        raise HTTPException(status_code=401, detail="Cuenta sin PIN configurado")

    pin_clean = body.pin.strip()
    if not bcrypt.checkpw(pin_clean.encode(), user["pin_hash"].encode()):
        logger.warning("app/login: PIN incorrecto phone=%s", phone)
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = _make_token(user)
    logger.info("app/login: OK phone=%s", phone)

    return LoginResponse(
        token=token,
        user_id=user["id"],
        name=user["name"] or "",
        phone=user["phone"],
    )
