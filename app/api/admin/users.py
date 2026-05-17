"""Rutas admin para gestión de usuarios — búsqueda, detalle y edición."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.admin.auth import verify_token
from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger


def _require_super_admin(token: dict) -> None:
    """Lanza 403 si el operador no es super_admin."""
    if token.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo super_admin puede realizar esta acción",
        )

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
logger = get_logger(__name__)


class UserPatch(BaseModel):
    name:    str | None = None
    phone:   str | None = None
    email:   str | None = None
    dactilar: str | None = None


@router.get("/search")
async def search_users(q: str = "", token: dict = Depends(verify_token)) -> list:
    """
    Busca usuarios por cédula, teléfono o nombre.
    q mínimo 3 caracteres.
    """
    q = q.strip()
    if len(q) < 3:
        return []

    db = get_supabase()

    # Busca por cédula exacta primero, luego por teléfono, luego por nombre parcial
    results = []

    # Cédula exacta
    r = db.table("users").select("id, name, phone, email, cedula, created_at") \
        .eq("cedula", q).limit(10).execute()
    results.extend(r.data or [])

    # Teléfono (contiene)
    if not results:
        r = db.table("users").select("id, name, phone, email, cedula, created_at") \
            .ilike("phone", f"%{q}%").limit(10).execute()
        results.extend(r.data or [])

    # Nombre parcial
    if not results:
        r = db.table("users").select("id, name, phone, email, cedula, created_at") \
            .ilike("name", f"%{q}%").limit(10).execute()
        results.extend(r.data or [])

    return results


@router.get("/{user_id}")
async def get_user(user_id: str, token: dict = Depends(verify_token)) -> dict:
    """Retorna info completa del usuario + saldo + historial de transacciones."""
    db = get_supabase()

    # Info básica
    u = db.table("users").select(
        "id, name, phone, email, cedula, dactilar, birth_date, custody_mode, created_at"
    ).eq("id", user_id).limit(1).execute()
    if not u.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user = u.data[0]

    # Saldo
    w = db.table("wallets").select("balance, currency") \
        .eq("user_id", user_id).execute()
    user["wallets"] = w.data or []

    # Depósitos (últimos 30)
    deps = db.table("deposits") \
        .select("id, amount, bank_name, reference_number, status, created_at") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True).limit(30).execute()
    user["deposits"] = deps.data or []

    # Retiros (últimos 30)
    wds = db.table("withdrawals") \
        .select("id, amount, fee, amount_received, bank_name, account_number, account_holder, withdrawal_type, status, created_at") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True).limit(30).execute()
    user["withdrawals"] = wds.data or []

    # Transferencias enviadas
    sent = db.table("transactions") \
        .select("id, amount, fee, currency, status, created_at, to_user:to_user_id(name, phone)") \
        .eq("from_user_id", user_id).eq("tx_type", "transfer") \
        .order("created_at", desc=True).limit(30).execute()
    user["transfers_sent"] = sent.data or []

    # Transferencias recibidas
    recv = db.table("transactions") \
        .select("id, amount, fee, currency, status, created_at, from_user:from_user_id(name, phone)") \
        .eq("to_user_id", user_id).eq("tx_type", "transfer") \
        .order("created_at", desc=True).limit(30).execute()
    user["transfers_received"] = recv.data or []

    return user


@router.patch("/{user_id}")
async def update_user(user_id: str, body: UserPatch, token: dict = Depends(verify_token)) -> dict:
    """Edita teléfono, email o nombre del usuario. Solo super_admin."""
    _require_super_admin(token)

    db = get_supabase()

    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    result = db.table("users").update(patch).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Audit log — cambios a usuarios son sensibles
    try:
        db.table("audit_log").insert({
            "operator_id":  token["sub"],
            "action":       "edit_user",
            "target_table": "users",
            "target_id":    user_id,
            "notes":        f"campos modificados: {list(patch.keys())}",
        }).execute()
    except Exception:
        pass

    logger.info("Admin editó usuario %s: campos=%s by=%s", user_id, list(patch.keys()), token["sub"])
    return result.data[0]
