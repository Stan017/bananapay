"""Auth del panel admin: login con email + contraseña + PIN → JWT."""

import datetime

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.core.limiter import limiter
from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])
logger = get_logger(__name__)

_bearer = HTTPBearer()

JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 12


# ─── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str
    pin: str


class LoginResponse(BaseModel):
    token: str
    operator_id: str
    name: str
    role: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _create_token(operator: dict) -> str:
    payload = {
        "sub":  operator["id"],
        "name": operator["name"],
        "role": operator["role"],
        "exp":  datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def _decode_token(raw: str) -> dict:
    try:
        return jwt.decode(raw, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """Dependency — valida JWT desde header Authorization Bearer."""
    return _decode_token(credentials.credentials)


def verify_token_query(token: str = "") -> dict:
    """Dependency — valida JWT desde query param ?token=... (solo para endpoints de media)."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token requerido")
    return _decode_token(token)


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")          # 5 intentos/minuto por IP → 429
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    db = get_supabase()
    result = (
        db.table("operators")
        .select("*")
        .eq("email", body.email.lower().strip())
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    op = result.data[0]

    if not bcrypt.checkpw(body.password.encode(), op["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not bcrypt.checkpw(body.pin.encode(), op["pin_hash"].encode()):
        raise HTTPException(status_code=401, detail="PIN incorrecto")

    token = _create_token(op)
    logger.info("Admin login: operator=%s role=%s", op["name"], op["role"])
    return LoginResponse(
        token=token,
        operator_id=op["id"],
        name=op["name"],
        role=op["role"],
    )
