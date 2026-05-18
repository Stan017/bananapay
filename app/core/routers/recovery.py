"""
Flujo de recuperación de cuenta — cuando el usuario pierde/cambia su número.

Flujo de 3 pasos:
  1. Cédula    → busca la cuenta por cédula
  2. Birthdate → verifica fecha de nacimiento registrada
  3. PIN       → verifica PIN actual como último factor

Si los 3 coinciden: actualiza el teléfono al número desde el que escribe.
"""

import re as _re

from app.core.session import ConversationState, session_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ─── Entry point ──────────────────────────────────────────────────────────────

async def handle_recovery_start(phone: str) -> str:
    """El usuario escribe 'recuperar cuenta' — arranca el flujo."""
    await session_manager.set_state(phone, ConversationState.AWAITING_RECOVERY_CEDULA)
    return (
        "🔑 *Recuperar cuenta BananaPay*\n\n"
        "Voy a verificar tu identidad en 3 pasos.\n\n"
        "Paso 1/3 — ¿Cuál es tu número de *cédula*?"
    )


# ─── Paso 1: cédula ───────────────────────────────────────────────────────────

async def handle_recovery_cedula(phone: str, text: str, session: dict) -> str:
    cedula = _re.sub(r"\D", "", text.strip())
    if len(cedula) != 10:
        return "❌ La cédula debe tener 10 dígitos. Inténtalo de nuevo:"

    from app.integrations.supabase_client import get_supabase
    db     = get_supabase()
    result = db.table("users").select("id,name,phone,cedula,birth_date,pin_hash,is_active") \
                              .eq("cedula", cedula).limit(1).execute()
    user   = result.data[0] if result.data else None

    if not user:
        # No revelar si la cédula existe o no — mensaje genérico
        return (
            "❌ No pude verificar tu identidad con esos datos.\n\n"
            "Escribe *recuperar cuenta* para intentar de nuevo o "
            "*soporte* para hablar con un agente."
        )

    if not user.get("is_active"):
        logger.warning("recovery: cuenta inactiva cedula=%s", cedula)
        return (
            "⚠️ Tu cuenta está desactivada. Escribe *soporte* "
            "para que un agente te ayude."
        )

    if not user.get("birth_date"):
        # Sin fecha de nacimiento → no podemos verificar, deriva a soporte
        logger.warning("recovery: sin birth_date cedula=%s", cedula)
        return (
            "⚠️ Tu cuenta no tiene fecha de nacimiento registrada.\n"
            "Escribe *soporte* para que un agente te ayude a recuperarla."
        )

    await session_manager.set_state(
        phone,
        ConversationState.AWAITING_RECOVERY_BIRTHDATE,
        context={"recovery_user_id": user["id"], "recovery_cedula": cedula},
    )
    return (
        "✅ Paso 1 verificado.\n\n"
        "Paso 2/3 — ¿Cuál es tu *fecha de nacimiento*?\n"
        "Formato: *DD/MM/AAAA*"
    )


# ─── Paso 2: fecha de nacimiento ─────────────────────────────────────────────

async def handle_recovery_birthdate(phone: str, text: str, session: dict) -> str:
    ctx = session.get("context", {})

    match = _re.search(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", text.strip())
    if not match:
        return "No reconocí la fecha. Escríbela así: *15/03/1990*"

    day, month, year = match.group(1).zfill(2), match.group(2).zfill(2), match.group(3)
    input_date = f"{year}-{month}-{day}"   # formato ISO para comparar con Supabase

    from app.integrations.supabase_client import get_supabase
    db     = get_supabase()
    user_id = ctx.get("recovery_user_id")
    result  = db.table("users").select("birth_date,pin_hash,name") \
                               .eq("id", user_id).limit(1).execute()
    user    = result.data[0] if result.data else None

    if not user:
        await session_manager.clear(phone)
        return "❌ Error al verificar. Escribe *recuperar cuenta* para intentar de nuevo."

    stored_date = (user.get("birth_date") or "").strip()[:10]  # "YYYY-MM-DD"

    if stored_date != input_date:
        # Intentos fallidos — limpiar sesión por seguridad
        await session_manager.clear(phone)
        return (
            "❌ La fecha de nacimiento no coincide.\n\n"
            "Escribe *recuperar cuenta* para intentar de nuevo o "
            "*soporte* para hablar con un agente."
        )

    await session_manager.set_state(
        phone,
        ConversationState.AWAITING_RECOVERY_PIN,
        context=ctx,
    )
    return (
        "✅ Paso 2 verificado.\n\n"
        "Paso 3/3 — Ingresa tu *PIN de 6 dígitos* para confirmar:"
    )


# ─── Paso 3: PIN ─────────────────────────────────────────────────────────────

async def handle_recovery_pin(phone: str, text: str, session: dict) -> str:
    ctx     = session.get("context", {})
    pin_raw = _re.sub(r"\D", "", text.strip())

    if len(pin_raw) != 6:
        return "El PIN debe tener 6 dígitos. Inténtalo de nuevo:"

    from app.integrations.supabase_client import get_supabase
    from app.core.security import verify_pin

    db      = get_supabase()
    user_id = ctx.get("recovery_user_id")
    result  = db.table("users").select("pin_hash,name,phone").eq("id", user_id).limit(1).execute()
    user    = result.data[0] if result.data else None

    if not user or not verify_pin(pin_raw, user.get("pin_hash", "")):
        await session_manager.clear(phone)
        return (
            "❌ PIN incorrecto.\n\n"
            "Escribe *recuperar cuenta* para intentar de nuevo o "
            "*soporte* para hablar con un agente."
        )

    old_phone = user["phone"]
    if old_phone == phone:
        await session_manager.clear(phone)
        return (
            "ℹ️ Tu cuenta ya está vinculada a este número.\n\n"
            "Escribe *hola* para acceder."
        )

    # Actualizar teléfono
    db.table("users").update({"phone": phone}).eq("id", user_id).execute()
    await session_manager.clear(phone)

    first_name = user["name"].strip().split()[0]
    logger.info(
        "recovery: cuenta recuperada user_id=%s old_phone=%s new_phone=%s",
        user_id, old_phone, phone,
    )

    return (
        f"✅ *¡Cuenta recuperada, {first_name}!*\n\n"
        "Tu cuenta BananaPay ha sido vinculada a este número.\n\n"
        "Escribe *hola* para acceder a tu cuenta. 🍌"
    )
