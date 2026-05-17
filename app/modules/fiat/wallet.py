"""Operaciones de wallet fiat USD en Supabase."""

import re as _re
from decimal import Decimal

from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

# UUID v4 — único formato que Supabase usa como PK
_UUID_RE = _re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    _re.IGNORECASE,
)

logger = get_logger(__name__)

TRANSFER_FEE = Decimal("0.00")   # gratis entre usuarios BananaPay
WITHDRAW_FEE = Decimal("0.50")   # retiro a banco externo


async def get_balance(user_id: str) -> Decimal:
    """Retorna el saldo USD fiat del usuario."""
    db = get_supabase()
    result = db.table("wallets").select("balance").eq("user_id", user_id).eq("currency", "USD").limit(1).execute()
    if result.data:
        return Decimal(str(result.data[0]["balance"]))
    return Decimal("0.00")


async def get_usdt_balance(user_id: str) -> Decimal:
    """Retorna el saldo USDT del usuario."""
    db = get_supabase()
    result = db.table("wallets").select("balance").eq("user_id", user_id).eq("currency", "USDT").limit(1).execute()
    if result.data:
        return Decimal(str(result.data[0]["balance"]))
    return Decimal("0.00")


async def get_usdc_balance(user_id: str) -> Decimal:
    """Retorna el saldo USDC del usuario."""
    db = get_supabase()
    result = db.table("wallets").select("balance").eq("user_id", user_id).eq("currency", "USDC").limit(1).execute()
    if result.data:
        return Decimal(str(result.data[0]["balance"]))
    return Decimal("0.00")


async def get_balances(user_id: str) -> dict:
    """Retorna saldo fiat, USDT y USDC del usuario."""
    fiat = await get_balance(user_id)
    usdt = await get_usdt_balance(user_id)
    usdc = await get_usdc_balance(user_id)
    return {
        "fiat":  fiat,
        "usdt":  usdt,
        "usdc":  usdc,
        "total": fiat + usdt + usdc,
    }


async def transfer(
    from_phone: str,
    to_phone: str,
    amount: Decimal,
    currency: str = "USD",
) -> dict:
    """
    Transfiere USD, USDT o USDC entre dos usuarios BananaPay.
    Usa RPC atómica — no hay race condition aunque dos transfers ocurran al mismo tiempo.
    Retorna {"ok": True} o {"ok": False, "error": "mensaje"}
    """
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.fraud import check_blacklist
    from app.utils.db_ops import transfer_wallets

    db = get_supabase()

    sender = await get_user_by_phone(from_phone)
    if not sender:
        return {"ok": False, "error": "Tu cuenta no existe. Escribe *hola* para registrarte."}

    # Verificar blacklist del sender antes de cualquier operación
    bl = check_blacklist(phone=sender.get("phone"), cedula=sender.get("cedula"))
    if bl.blocked:
        logger.warning("transfer: sender bloqueado phone=%s", from_phone)
        return {"ok": False, "error": "❌ Tu cuenta tiene una restricción activa. Escribe *soporte*."}

    receiver = await get_user_by_phone(to_phone)
    if not receiver:
        return {"ok": False, "error": "El destinatario no tiene cuenta BananaPay todavía."}

    try:
        await transfer_wallets(sender["id"], receiver["id"], currency, amount)
    except ValueError:
        # Mostrar saldo en la moneda correcta
        if currency == "USDT":
            bal = await get_usdt_balance(sender["id"])
            bal_str = f"*{bal:.2f} USDT*"
        elif currency == "USDC":
            bal = await get_usdc_balance(sender["id"])
            bal_str = f"*{bal:.2f} USDC*"
        else:
            bal = await get_balance(sender["id"])
            bal_str = f"*${bal:.2f}*"
        return {"ok": False, "error": f"Saldo insuficiente. Tienes {bal_str}"}
    except RuntimeError as exc:
        logger.error("transfer: wallet no encontrado — %s", exc)
        return {"ok": False, "error": "Error interno al procesar la transferencia."}

    # La RPC transfer_between_users ya registra en transactions dentro de la
    # misma transacción DB. No insertamos aquí para evitar duplicados.
    logger.info("Transferencia: %s → %s %.2f %s", from_phone, to_phone, amount, currency)
    return {"ok": True}


async def get_history(user_id: str, limit: int = 5) -> list[dict]:
    """Retorna las últimas transacciones del usuario con nombres de la contraparte."""
    # Validar formato UUID antes de interpolarlo en la query — evita inyección si
    # user_id llegara a ser un valor inesperado (aunque en la práctica siempre es
    # un UUID de Supabase, validar es defensa en profundidad).
    if not _UUID_RE.match(str(user_id)):
        logger.error("get_history: user_id con formato inválido — %r", user_id)
        return []

    db = get_supabase()
    result = db.table("transactions").select("*").or_(
        f"from_user_id.eq.{user_id},to_user_id.eq.{user_id}"
    ).order("created_at", desc=True).limit(limit).execute()

    txs = result.data or []
    if not txs:
        return []

    # Recopilar IDs únicos de la contraparte para buscar nombres en un solo query
    other_ids = set()
    for tx in txs:
        other_id = tx["to_user_id"] if tx["from_user_id"] == user_id else tx["from_user_id"]
        if other_id:
            other_ids.add(other_id)

    names: dict[str, str] = {}
    if other_ids:
        users_result = db.table("users").select("id, name").in_("id", list(other_ids)).execute()
        for u in (users_result.data or []):
            names[u["id"]] = u["name"]

    # Adjuntar nombre de la contraparte a cada transacción
    for tx in txs:
        other_id = tx["to_user_id"] if tx["from_user_id"] == user_id else tx["from_user_id"]
        tx["other_name"] = names.get(other_id or "", "")

    return txs
