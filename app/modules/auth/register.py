"""Operaciones de usuarios en Supabase."""

from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def get_user_by_phone(phone: str) -> dict | None:
    """Retorna el usuario o None si no existe."""
    db = get_supabase()
    result = db.table("users").select("*").eq("phone", phone).limit(1).execute()
    return result.data[0] if result.data else None


async def create_user(
    phone: str,
    name: str,
    cedula: str,
    pin_hash: str,
    custody_mode: str,
    birth_date: str | None = None,
    dactilar_code: str | None = None,
    email: str | None = None,
) -> dict:
    """Crea usuario + wallet USD inicial en una sola operación."""
    db = get_supabase()

    payload = {
        "phone": phone,
        "name": name,
        "pin_hash": pin_hash,
        "custody_mode": custody_mode,
        "cedula": cedula,
        "kyc_level": 1 if dactilar_code else 0,
        "is_active": True,
    }
    if birth_date:
        payload["birth_date"] = birth_date
    if dactilar_code:
        payload["dactilar_code"] = dactilar_code
    if email:
        payload["email"] = email

    # Crear usuario
    user_result = db.table("users").insert(payload).execute()

    user = user_result.data[0]

    # Crear wallets USD, USDT y USDC con saldo 0
    # IMPORTANTE: agregar las 3 monedas aquí — get_usdc_balance() usa .single()
    # que lanza excepción si no existe la fila. Sin USDC wallet, get_balances() crashea.
    db.table("wallets").insert([
        {"user_id": user["id"], "balance": 0.00, "currency": "USD"},
        {"user_id": user["id"], "balance": 0.00, "currency": "USDT"},
        {"user_id": user["id"], "balance": 0.00, "currency": "USDC"},
    ]).execute()

    logger.info("Usuario creado: phone=%s id=%s", phone, user["id"])
    return user


