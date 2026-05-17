"""
fraud.py — Detección de fraude para BananaPay
══════════════════════════════════════════════
Chequeos que se ejecutan ANTES de crear depósitos y retiros.
Guarda alertas en la tabla fraud_alerts de Supabase.

Niveles de riesgo:
    low    → solo log, no bloquea
    medium → alerta visible en panel admin, no bloquea
    high   → bloquea la operación + alerta en panel admin
"""

import asyncio
import datetime
import time
from decimal import Decimal

from app.config import settings
from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _notify_admin_fraud(alert_type: str, risk_level: str, user_id: str, details: dict) -> None:
    """Envía WhatsApp al admin cuando se detecta fraude de riesgo alto o medio."""
    if not settings.admin_whatsapp:
        return
    try:
        from app.integrations.whatsapp.client import send_message
        emoji   = "🚨" if risk_level == "high" else "⚠️"
        tipo    = alert_type.replace("_", " ").title()
        detalle = " | ".join(f"{k}: {v}" for k, v in list(details.items())[:3])
        msg = (
            f"{emoji} *Alerta de fraude — {risk_level.upper()}*\n\n"
            f"📋 Tipo: `{tipo}`\n"
            f"👤 Usuario: `{user_id[:8]}…`\n"
            f"📊 {detalle}\n\n"
            f"Revisa el panel admin → Fraude → Alertas"
        )
        await send_message(settings.admin_whatsapp, msg)
    except Exception as exc:
        logger.warning("No se pudo notificar al admin sobre fraude: %s", exc)

# ─── Umbrales de negocio (fallback si la BD no tiene config) ─────────────────

_DEFAULT_CONFIG = {
    "high_deposit_amount":    "500.00",
    "high_withdrawal_amount": "200.00",
    "max_rejected_per_hour":  "3",
    "new_user_hours":         "24",
    "new_user_max_deposit":   "100.00",
}

# ─── Caché en memoria con TTL ─────────────────────────────────────────────────
# Evita golpear la BD en cada check de fraude (se llama 2-3 veces por operación).
# TTL de 60s: si un admin cambia umbrales en BD tardan máx 1 minuto en aplicar.

_CONFIG_CACHE: dict | None = None
_CONFIG_CACHE_AT: float    = 0.0
_CONFIG_TTL: float         = 60.0   # segundos


def get_fraud_config() -> dict:
    """
    Lee los límites de fraude desde fraud_config en Supabase.
    Resultado cacheado en memoria por 60 segundos — una sola query por minuto
    sin importar cuántas operaciones ocurran en paralelo.
    Si falla o no hay tabla, usa los valores por defecto hardcodeados.
    """
    global _CONFIG_CACHE, _CONFIG_CACHE_AT

    # Servir desde caché si no expiró
    if _CONFIG_CACHE is not None and (time.monotonic() - _CONFIG_CACHE_AT) < _CONFIG_TTL:
        return _CONFIG_CACHE

    try:
        db = get_supabase()
        rows = db.table("fraud_config").select("key, value").execute()
        cfg = dict(_DEFAULT_CONFIG)
        for row in (rows.data or []):
            cfg[row["key"]] = row["value"]
    except Exception as exc:
        logger.warning("fraud_config: usando defaults — %s", exc)
        cfg = dict(_DEFAULT_CONFIG)

    _CONFIG_CACHE = {
        "high_deposit_amount":      Decimal(cfg["high_deposit_amount"]),
        "high_withdrawal_amount":   Decimal(cfg["high_withdrawal_amount"]),
        "max_rejected_per_hour":    int(cfg["max_rejected_per_hour"]),
        "new_user_hours":           int(cfg["new_user_hours"]),
        "new_user_max_deposit":     Decimal(cfg["new_user_max_deposit"]),
        "max_deposits_per_hour":    int(cfg.get("max_deposits_per_hour", "5")),
        "max_withdrawals_per_hour": int(cfg.get("max_withdrawals_per_hour", "3")),
    }
    _CONFIG_CACHE_AT = time.monotonic()
    return _CONFIG_CACHE


# ─── Resultado del chequeo ───────────────────────────────────────────────────

class FraudResult:
    """Resultado de una verificación anti-fraude."""

    def __init__(self, blocked: bool, risk: str, reason: str, alert_type: str):
        self.blocked    = blocked     # True = no procesar la operación
        self.risk       = risk        # "low" | "medium" | "high"
        self.reason     = reason      # Descripción para admin/log
        self.alert_type = alert_type  # slug del tipo de alerta

    @property
    def ok(self) -> bool:
        return not self.blocked

    def __repr__(self) -> str:
        return f"<FraudResult blocked={self.blocked} risk={self.risk} type={self.alert_type}>"


# Resultado limpio — sin alertas
RESULT_OK = FraudResult(blocked=False, risk="low", reason="", alert_type="none")


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _user_age_hours(user: dict) -> float:
    """Retorna la antigüedad de la cuenta en horas."""
    created_str = user.get("created_at", "")
    if not created_str:
        return 999.0
    try:
        created = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        return (now - created).total_seconds() / 3600
    except Exception:
        return 999.0


def _save_alert(
    user_id: str,
    alert_type: str,
    risk_level: str,
    details: dict,
    entity_id: str | None = None,
    entity_type: str | None = None,
) -> None:
    """
    Guarda una alerta de fraude en Supabase.
    Síncrona para ser compatible con el cliente Supabase existente.
    Falla silenciosamente — nunca interrumpe el flujo principal.
    """
    try:
        db = get_supabase()
        payload = {
            "user_id":    user_id,
            "alert_type": alert_type,
            "risk_level": risk_level,
            "details":    details,
        }
        if entity_id:
            payload["entity_id"]   = entity_id
        if entity_type:
            payload["entity_type"] = entity_type

        db.table("fraud_alerts").insert(payload).execute()
        logger.warning(
            "🚨 fraud_alert: user=%s type=%s risk=%s | %s",
            user_id, alert_type, risk_level, details,
        )

        # Notificar al admin en tiempo real para alertas medium y high
        if risk_level in ("medium", "high"):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    _notify_admin_fraud(alert_type, risk_level, user_id, details)
                )
            except RuntimeError:
                pass  # Sin event loop activo (tests, scripts)

    except Exception as exc:
        logger.error("No se pudo guardar alerta de fraude: %s", exc)


# ─── Chequeo de depósitos ─────────────────────────────────────────────────────

def check_deposit_fraud(
    user: dict,
    amount: Decimal,
    voucher_media_id: str | None = None,
) -> FraudResult:
    """
    Verifica señales de fraude en un depósito.
    Llamar ANTES de create_deposit().

    Checks:
        1. Comprobante duplicado (mismo voucher_media_id)
        2. Demasiados depósitos rechazados en la última hora
        3. Monto muy alto → siempre revisión manual
        4. Usuario nuevo con monto elevado → alerta media
    """
    cfg     = get_fraud_config()
    db      = get_supabase()
    user_id = user["id"]

    # ── 1. Comprobante duplicado ───────────────────────────────────────────────
    if voucher_media_id:
        dup = (
            db.table("deposits")
            .select("id, amount, created_at")
            .eq("voucher_media_id", voucher_media_id)
            .neq("status", "rejected")
            .limit(1)
            .execute()
        )
        if dup.data:
            prev = dup.data[0]
            _save_alert(user_id, "duplicate_voucher", "high", {
                "voucher_media_id":   voucher_media_id,
                "previous_deposit_id": prev["id"],
                "amount": float(amount),
            })
            return FraudResult(
                blocked=True,
                risk="high",
                reason=f"Comprobante ya utilizado en depósito {prev['id'][:8]}…",
                alert_type="duplicate_voucher",
            )

    # ── 2. Demasiados depósitos rechazados en 1 hora ──────────────────────────
    one_hour_ago = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    ).isoformat()
    rejected = (
        db.table("deposits")
        .select("id")
        .eq("user_id", user_id)
        .eq("status", "rejected")
        .gte("created_at", one_hour_ago)
        .execute()
    )
    rejected_count = len(rejected.data or [])
    if rejected_count >= cfg["max_rejected_per_hour"]:
        _save_alert(user_id, "too_many_rejected_deposits", "high", {
            "rejected_count": rejected_count,
            "window_minutes": 60,
        })
        return FraudResult(
            blocked=True,
            risk="high",
            reason=f"{rejected_count} depósitos rechazados en la última hora",
            alert_type="too_many_rejected_deposits",
        )

    # ── 3. Monto alto → siempre revisión manual (no bloqueamos, admin decide) ─
    if amount >= cfg["high_deposit_amount"]:
        _save_alert(user_id, "high_amount_deposit", "high", {
            "amount":    float(amount),
            "threshold": float(cfg["high_deposit_amount"]),
        })
        return FraudResult(
            blocked=False,
            risk="high",
            reason=f"Depósito de monto alto: ${amount:.2f} (umbral ${cfg['high_deposit_amount']:.2f})",
            alert_type="high_amount_deposit",
        )

    # ── 4. Usuario nuevo + monto elevado ──────────────────────────────────────
    age_hours = _user_age_hours(user)
    if age_hours < cfg["new_user_hours"] and amount > cfg["new_user_max_deposit"]:
        _save_alert(user_id, "new_user_large_deposit", "medium", {
            "amount":           float(amount),
            "user_age_hours":   round(age_hours, 1),
            "max_for_new_user": float(cfg["new_user_max_deposit"]),
        })
        return FraudResult(
            blocked=False,
            risk="medium",
            reason=f"Usuario nuevo ({age_hours:.0f}h) con depósito de ${amount:.2f}",
            alert_type="new_user_large_deposit",
        )

    return RESULT_OK


# ─── Chequeo de retiros ───────────────────────────────────────────────────────

def check_withdrawal_fraud(
    user: dict,
    amount: Decimal,
    account_number: str,
    account_holder: str,
) -> FraudResult:
    """
    Verifica señales de fraude en un retiro.
    Llamar ANTES de create_withdrawal(), junto a check_withdrawal_limits().

    Checks:
        1. Usuario muy nuevo retirando dinero
        2. Nueva cuenta bancaria (distinta a las usadas antes)
        3. Monto alto → alerta media
    """
    cfg     = get_fraud_config()
    db      = get_supabase()
    user_id = user["id"]

    # ── 1. Usuario muy nuevo ──────────────────────────────────────────────────
    age_hours = _user_age_hours(user)
    if age_hours < cfg["new_user_hours"]:
        _save_alert(user_id, "new_user_withdrawal", "medium", {
            "amount":         float(amount),
            "user_age_hours": round(age_hours, 1),
            "account_number_last4": account_number[-4:] if len(account_number) >= 4 else "****",
        })
        return FraudResult(
            blocked=False,
            risk="medium",
            reason=f"Usuario nuevo ({age_hours:.0f}h) retirando ${amount:.2f}",
            alert_type="new_user_withdrawal",
        )

    # ── 2. Nueva cuenta bancaria ──────────────────────────────────────────────
    previous = (
        db.table("withdrawals")
        .select("account_number")
        .eq("user_id", user_id)
        .in_("status", ["approved", "pending", "completed"])
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    prev_accounts = {r["account_number"] for r in (previous.data or [])}
    if prev_accounts and account_number not in prev_accounts:
        _save_alert(user_id, "new_bank_account", "medium", {
            "new_account_last4":     account_number[-4:] if len(account_number) >= 4 else "****",
            "known_accounts_count":  len(prev_accounts),
            "amount":                float(amount),
        })
        return FraudResult(
            blocked=False,
            risk="medium",
            reason=f"Nueva cuenta bancaria — se conocen {len(prev_accounts)} cuentas anteriores",
            alert_type="new_bank_account",
        )

    # ── 3. Monto alto ─────────────────────────────────────────────────────────
    if amount >= cfg["high_withdrawal_amount"]:
        _save_alert(user_id, "high_amount_withdrawal", "medium", {
            "amount":    float(amount),
            "threshold": float(cfg["high_withdrawal_amount"]),
        })
        return FraudResult(
            blocked=False,
            risk="medium",
            reason=f"Retiro de monto alto: ${amount:.2f}",
            alert_type="high_amount_withdrawal",
        )

    return RESULT_OK


# ─── Blacklist ────────────────────────────────────────────────────────────────

def check_blacklist(phone: str | None = None, cedula: str | None = None) -> FraudResult:
    """
    Verifica si el usuario está en la blacklist.
    Llamar al inicio de CUALQUIER operación (depósito, retiro, transferencia).
    """
    if not phone and not cedula:
        return RESULT_OK
    try:
        db = get_supabase()
        query = db.table("fraud_blacklist").select("id, reason, phone, cedula")
        if phone and cedula:
            # Bloqueado si coincide teléfono O cédula
            query = query.or_(f"phone.eq.{phone},cedula.eq.{cedula}")
        elif phone:
            query = query.eq("phone", phone)
        else:
            query = query.eq("cedula", cedula)

        result = query.limit(1).execute()
        if result.data:
            entry = result.data[0]
            logger.warning(
                "🚫 blacklist: bloqueado phone=%s cedula=%s reason=%s",
                phone, cedula, entry["reason"],
            )
            return FraudResult(
                blocked=True,
                risk="high",
                reason=f"Usuario en blacklist: {entry['reason']}",
                alert_type="blacklisted_user",
            )
    except Exception as exc:
        logger.error("check_blacklist error: %s", exc)
    return RESULT_OK


def add_to_blacklist(
    reason: str,
    phone: str | None = None,
    cedula: str | None = None,
    blocked_by: str = "admin",
) -> bool:
    """Agrega un usuario a la blacklist. Retorna True si OK."""
    try:
        db = get_supabase()
        payload = {"reason": reason, "blocked_by": blocked_by}
        if phone:
            payload["phone"] = phone
        if cedula:
            payload["cedula"] = cedula
        db.table("fraud_blacklist").insert(payload).execute()
        logger.warning("🚫 blacklist: agregado phone=%s cedula=%s by=%s reason=%s",
                       phone, cedula, blocked_by, reason)
        return True
    except Exception as exc:
        logger.error("add_to_blacklist error: %s", exc)
        return False


def remove_from_blacklist(entry_id: str) -> bool:
    """Elimina una entrada de la blacklist. Retorna True si OK."""
    try:
        db = get_supabase()
        db.table("fraud_blacklist").delete().eq("id", entry_id).execute()
        logger.info("🔓 blacklist: eliminado id=%s", entry_id)
        return True
    except Exception as exc:
        logger.error("remove_from_blacklist error: %s", exc)
        return False


def get_blacklist(limit: int = 100) -> list[dict]:
    """Retorna la blacklist completa para el panel admin."""
    try:
        db = get_supabase()
        result = (
            db.table("fraud_blacklist")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("get_blacklist error: %s", exc)
        return []


# ─── Velocity checks ──────────────────────────────────────────────────────────

def check_deposit_velocity(user: dict) -> FraudResult:
    """
    Detecta si el usuario está enviando demasiados depósitos en poco tiempo.
    Llamar ANTES de check_deposit_fraud().
    """
    cfg     = get_fraud_config()
    db      = get_supabase()
    user_id = user["id"]

    one_hour_ago = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    ).isoformat()

    result = (
        db.table("deposits")
        .select("id")
        .eq("user_id", user_id)
        .gte("created_at", one_hour_ago)
        .execute()
    )
    count = len(result.data or [])
    max_allowed = cfg["max_deposits_per_hour"]

    if count >= max_allowed:
        _save_alert(user_id, "deposit_velocity", "high", {
            "deposits_last_hour": count,
            "max_allowed":        max_allowed,
        })
        return FraudResult(
            blocked=True,
            risk="high",
            reason=f"Velocidad excesiva: {count} depósitos en la última hora (máx {max_allowed})",
            alert_type="deposit_velocity",
        )
    return RESULT_OK


def check_withdrawal_velocity(user: dict) -> FraudResult:
    """
    Detecta si el usuario está enviando demasiados retiros en poco tiempo.
    Llamar ANTES de check_withdrawal_fraud().
    """
    cfg     = get_fraud_config()
    db      = get_supabase()
    user_id = user["id"]

    one_hour_ago = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    ).isoformat()

    result = (
        db.table("withdrawals")
        .select("id")
        .eq("user_id", user_id)
        .gte("created_at", one_hour_ago)
        .execute()
    )
    count = len(result.data or [])
    max_allowed = cfg["max_withdrawals_per_hour"]

    if count >= max_allowed:
        _save_alert(user_id, "withdrawal_velocity", "high", {
            "withdrawals_last_hour": count,
            "max_allowed":           max_allowed,
        })
        return FraudResult(
            blocked=True,
            risk="high",
            reason=f"Velocidad excesiva: {count} retiros en la última hora (máx {max_allowed})",
            alert_type="withdrawal_velocity",
        )
    return RESULT_OK


# ─── Utilidades para el panel admin ──────────────────────────────────────────

def get_open_alerts(limit: int = 50) -> list[dict]:
    """Retorna alertas no resueltas para el panel admin, más recientes primero."""
    db = get_supabase()
    result = (
        db.table("fraud_alerts")
        .select("*, user:users(name, phone)")
        .eq("is_resolved", False)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def resolve_alert(alert_id: str, resolved_by: str = "admin") -> bool:
    """Marca una alerta como resuelta. Retorna True si OK."""
    try:
        db = get_supabase()
        db.table("fraud_alerts").update({
            "is_resolved":  True,
            "resolved_by":  resolved_by,
            "resolved_at":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }).eq("id", alert_id).execute()
        return True
    except Exception as exc:
        logger.error("No se pudo resolver alerta %s: %s", alert_id, exc)
        return False
