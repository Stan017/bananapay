"""
Handlers de registro y re-autenticación.
Cubre el flujo completo de onboarding (nombre → cédula → fecha → dactilar →
email → PIN → custody) y la reautenticación por inactividad.
"""

import re as _re
import time as _time

from app.core.session import ConversationState, session_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── Estados de registro (usados como constante compartida) ───────────────────

REGISTRATION_STATES = (
    ConversationState.AWAITING_NAME,
    ConversationState.AWAITING_CEDULA,
    ConversationState.AWAITING_BIRTH_DATE,
    ConversationState.AWAITING_DACTILAR,
    ConversationState.AWAITING_EMAIL,
    ConversationState.AWAITING_PIN_SET,
    ConversationState.AWAITING_PIN_CONFIRM,
    ConversationState.AWAITING_CUSTODY_MODE,
)

# ─── Ayuda contextual dentro de flujos ───────────────────────────────────────

_CONFUSED = _re.compile(
    r"qu[eé]\s+es|qu[eé]\s+es\s+eso|qu[eé]\s+significa|qu[eé]\s+pongo|qu[eé]\s+debo|"
    r"cu[aá]l\s+es|"
    r"no\s+entend|no\s+entiendo|no\s+s[eé]|no\s+tengo|no\s+encuentro|"
    r"no\s+lo\s+veo|no\s+recuerdo|no\s+comprendo|no\s+me\s+queda|"
    r"explic[a-z]*|repite|rep[ií]teme|"
    r"c[oó]mo\s+as[ií]|c[oó]mo\s+que|c[oó]mo\s+lo|d[oó]nde|en\s+qu[eé]|"
    r"ayuda|help|socorro|"
    r"ya\.+\?|ya\s*\?+|no\s+ya|a\s+ver|haber\s+\?|"
    r"c[oó]mo\s+as[ií]|no\s+cacho|no\s+entiendo\s+nada",
    _re.IGNORECASE,
)

_STATE_HINTS: dict = {
    ConversationState.AWAITING_NAME: (
        "Necesito tus *dos nombres y dos apellidos* tal como aparecen en tu cédula.\n\n"
        "Ejemplo: _Juan Carlos Pérez López_\n\n"
        "Escríbelos de nuevo:"
    ),
    ConversationState.AWAITING_CEDULA: (
        "La *cédula* es el número de 10 dígitos de tu documento de identidad ecuatoriano.\n\n"
        "Ejemplo: _0928732494_\n\n"
        "Escríbela sin espacios ni guiones:"
    ),
    ConversationState.AWAITING_BIRTH_DATE: (
        "Tu *fecha de nacimiento* en formato *DD/MM/AAAA*.\n\n"
        "Ejemplo: si naciste el 15 de marzo de 1990 escribe: _15/03/1990_\n\n"
        "Escríbela de nuevo:"
    ),
    ConversationState.AWAITING_DACTILAR: (
        "🪪 *¿Qué es el código dactilar?*\n\n"
        "Es un código que está al *reverso de tu cédula física* "
        "(la tarjetita azul que te dio el Registro Civil).\n\n"
        "Búscalo en la *esquina superior derecha* del reverso. "
        "Son *10 caracteres: 2 letras y 8 números* mezclados.\n\n"
        "Ejemplo: *E4443V2442*\n\n"
        "Si tienes tu cédula a mano, escribe el código tal como aparece. "
        "Si no la tienes ahora, escribe *después* y te lo pedimos luego."
    ),
    ConversationState.AWAITING_EMAIL: (
        "El *correo electrónico* es tu email personal (ej: tucorreo@gmail.com).\n\n"
        "Lo usaremos para enviarte recibos y para recuperar tu PIN.\n\n"
        "Si no quieres agregar correo ahora, escribe *omitir*."
    ),
    ConversationState.AWAITING_PIN_SET: (
        "El *PIN* es tu contraseña secreta de 6 dígitos para usar BananaPay.\n\n"
        "⚠️ Elige uno que no sea obvio:\n"
        "❌ Mal: 123456, 000000, tu fecha de nacimiento\n"
        "✅ Bien: cualquier combinación que solo tú recuerdes\n\n"
        "Escribe 6 dígitos:"
    ),
    ConversationState.AWAITING_PIN_CONFIRM: (
        "Escribe el mismo PIN de 6 dígitos que elegiste justo antes, "
        "para confirmar que lo recuerdas bien:"
    ),
    ConversationState.AWAITING_CUSTODY_MODE: (
        "Elige cómo quieres guardar tus criptomonedas (si algún día usas esa función):\n\n"
        "1️⃣ *Custodial* — Más fácil. Tus cryptos se guardan en Binance o Coinbase. "
        "Ellos las cuidan por ti.\n\n"
        "2️⃣ *Self-custody* — Avanzado. Tú guardas tus propias claves. "
        "Más control, más responsabilidad.\n\n"
        "Si no sabes cuál elegir, escribe *1* — puedes cambiarlo después."
    ),
}


def _check_confusion(state: ConversationState, text: str) -> str | None:
    """
    Detecta si el usuario está confundido dentro de un flujo activo.
    Retorna el hint del estado actual, o None si el texto parece válido.
    """
    cleaned = text.strip()
    if _re.fullmatch(r"[¿?!¡.\s]+", cleaned):
        return _STATE_HINTS.get(state)
    if 0 < len(cleaned) <= 3 and not cleaned.isdigit():
        return _STATE_HINTS.get(state)
    if _CONFUSED.search(cleaned):
        return _STATE_HINTS.get(state)
    return None


# ─── Registro ─────────────────────────────────────────────────────────────────

async def _handle_registration_name(phone: str, text: str, session: dict) -> str:
    from app.utils.validators import validate_full_name

    name = text.strip().title()
    ok, err = validate_full_name(name)
    if not ok:
        return err

    await session_manager.set_state(
        phone, ConversationState.AWAITING_CEDULA, context={"reg_name": name}
    )
    return (
        f"Mucho gusto *{name}* 🍌\n\n"
        "Ahora necesito tu *número de cédula* ecuatoriana (10 dígitos):"
    )


async def _handle_registration_cedula(phone: str, text: str, session: dict) -> str:
    from app.utils.phone import is_valid_cedula

    cedula = text.strip().replace(" ", "")
    if not is_valid_cedula(cedula):
        return "La cédula no es válida. Escríbela de nuevo (solo los 10 dígitos, sin espacios)."

    await session_manager.set_state(
        phone, ConversationState.AWAITING_BIRTH_DATE, context={"reg_cedula": cedula}
    )
    return "✅ Cédula verificada.\n\n¿Cuál es tu *fecha de nacimiento*?\nEscríbela así: *DD/MM/AAAA*\nEjemplo: _15/03/1990_"


async def _handle_registration_birth_date(phone: str, text: str, session: dict) -> str:
    from app.utils.validators import validate_birth_date

    ok, err, birth = validate_birth_date(text)
    if not ok:
        return err

    await session_manager.set_state(
        phone, ConversationState.AWAITING_DACTILAR,
        context={"reg_birth_date": birth.isoformat()}
    )
    return (
        "✅ Fecha registrada.\n\n"
        "🪪 Ahora necesito tu *código dactilar*.\n\n"
        "Es el código al *reverso de tu cédula física* "
        "(la tarjetita azul del Registro Civil), "
        "en la *esquina superior derecha*.\n\n"
        "Son *10 caracteres: 2 letras y 8 números* mezclados.\n"
        "Ejemplo: *E4443V2442*\n\n"
        "Escríbelo tal como aparece en tu cédula:\n"
        "_(Si no la tienes a mano, escribe *después*)_"
    )


async def _handle_registration_dactilar(phone: str, text: str, session: dict) -> str:
    from app.utils.validators import validate_dactilar

    if text.strip().lower() in ("después", "despues", "luego", "no tengo", "sin cedula", "omitir", "skip"):
        await session_manager.set_state(
            phone, ConversationState.AWAITING_EMAIL,
            context={"reg_dactilar": None}
        )
        return (
            "✅ Sin problema, puedes agregarlo después desde tu perfil.\n\n"
            "¿Cuál es tu *correo electrónico*?\n"
            "_(Escribe *omitir* si prefieres no agregar correo ahora)_"
        )

    ok, err = validate_dactilar(text)
    if not ok:
        return err

    await session_manager.set_state(
        phone, ConversationState.AWAITING_EMAIL,
        context={"reg_dactilar": text.strip().upper()}
    )
    return (
        "✅ Identidad verificada 🔒\n\n"
        "¿Cuál es tu *correo electrónico*?\n\n"
        "Lo usaremos para:\n"
        "📧 Enviarte recibos de cada transacción\n"
        "🔑 Recuperar tu PIN si lo olvidas\n"
        "📊 Extracto mensual de tu cuenta\n\n"
        "_(Escribe *omitir* si prefieres no agregar correo ahora)_"
    )


async def _handle_registration_email(phone: str, text: str, session: dict) -> str:
    from app.utils.validators import validate_email

    email = None
    if text.strip().lower() not in ("omitir", "skip", "no"):
        ok, err = validate_email(text)
        if not ok:
            return err
        email = text.strip().lower()

    await session_manager.set_state(
        phone, ConversationState.AWAITING_PIN_SET,
        context={"reg_email": email}
    )
    return (
        "✅ Casi listo.\n\n"
        "Crea tu *PIN de 6 dígitos*.\n\n"
        "Lo usarás en dos momentos:\n"
        "🔐 Al iniciar sesión después de inactividad\n"
        "💸 Para confirmar cada transacción\n\n"
        "⚠️ *Nunca lo compartas.* BananaPay jamás te lo pedirá por otro canal."
    )


async def _handle_pin_set(phone: str, text: str, session: dict) -> str:
    from app.utils.validators import validate_pin_strength

    pin = text.strip()
    if not pin.isdigit() or len(pin) != 6:
        return "El PIN debe tener exactamente *6 dígitos*. Intenta de nuevo:"

    ok, err = validate_pin_strength(pin)
    if not ok:
        return err

    await session_manager.set_state(
        phone, ConversationState.AWAITING_PIN_CONFIRM, context={"reg_pin_temp": pin}
    )
    return "🔒 PIN recibido de forma segura.\n\nAhora escríbelo una vez más para confirmar:"


async def _handle_pin_confirm(phone: str, text: str, session: dict) -> str:
    from app.integrations.whatsapp.messages import BotMessage, Btn

    ctx = session.get("context", {})
    if text.strip() != ctx.get("reg_pin_temp"):
        await session_manager.set_state(phone, ConversationState.AWAITING_PIN_SET)
        return "❌ Los PINs no coinciden.\n\nEscribe tu *PIN de 6 dígitos* de nuevo:"

    await session_manager.set_state(phone, ConversationState.AWAITING_CUSTODY_MODE)
    return BotMessage(
        text=(
            "✅ PIN confirmado y guardado 🔒\n\n"
            "⚠️ *Recomendación:* Borra este chat para proteger tus datos.\n\n"
            "Último paso — ¿cómo quieres guardar tus criptomonedas?\n\n"
            "😊 *Fácil* — BananaPay las guarda por ti (recomendado)\n"
            "🔑 *Avanzado* — Tú controlas tus propias claves"
        ),
        buttons=[
            Btn("btn_custodial",   "😊 Fácil (recomend.)"),
            Btn("btn_selfcustody", "🔑 Avanzado"),
        ],
    )


async def _handle_custody_mode(phone: str, text: str, session: dict) -> str:
    from app.core.security import hash_pin
    from app.modules.auth.register import create_user

    ctx = session.get("context", {})
    mode = "custodial" if text.strip() in ("1", "custodial") else "self_custody"
    pin_hash = hash_pin(ctx.get("reg_pin_temp", ""))

    await create_user(
        phone=phone,
        name=ctx.get("reg_name", ""),
        cedula=ctx.get("reg_cedula", ""),
        pin_hash=pin_hash,
        custody_mode=mode,
        birth_date=ctx.get("reg_birth_date"),
        dactilar_code=ctx.get("reg_dactilar"),
        email=ctx.get("reg_email"),
    )

    first_name = ctx.get("reg_name", "").split()[0]
    await session_manager.set_state(phone, ConversationState.AUTHENTICATED)
    return (
        f"🍌 *¡Listo, {first_name}! Ya eres parte de BananaPay.*\n\n"
        f"📱 Modo crypto: *{'Custodial (Binance/Coinbase)' if mode == 'custodial' else 'Self-custody (tú controlas)'}*\n"
        f"💰 Saldo: *$0.00 USD*\n\n"
        "⚠️ Borra este chat para proteger tus datos de registro.\n\n"
        "Escribe *depositar* para cargar saldo o *ayuda* para ver opciones. 🚀"
    )


# ─── Re-autenticación ─────────────────────────────────────────────────────────

async def _handle_reauth_cedula(phone: str, text: str, session: dict) -> str:
    from app.modules.auth.register import get_user_by_phone

    # ── Bloqueo temporal por intentos fallidos de PIN ─────────────────────────
    ctx = session.get("context", {})
    blocked_until = ctx.get("pin_blocked_until")
    if blocked_until and _time.time() < float(blocked_until):
        remaining_min = max(1, int((float(blocked_until) - _time.time()) / 60) + 1)
        return (
            f"🔴 *Cuenta bloqueada.*\n\n"
            f"Demasiados intentos fallidos de PIN. "
            f"Espera *{remaining_min} minuto(s)* y vuelve a intentarlo.\n\n"
            "Si olvidaste tu PIN, escribe *recuperar PIN*."
        )

    digits = text.strip().replace(" ", "")
    user = await get_user_by_phone(phone)
    if not user or not user.get("cedula"):
        await session_manager.clear(phone)
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    if not user["cedula"].endswith(digits) or len(digits) != 4:
        return "Los dígitos no coinciden. Ingresa los *últimos 4 dígitos* de tu cédula:"

    await session_manager.set_state(
        phone, ConversationState.AWAITING_REAUTH_PIN,
        context={"reauth_user_id": user["id"], "pin_attempts": 0}
    )
    return "✅ Cédula verificada.\n\nAhora ingresa tu *PIN de 6 dígitos*:"


async def _handle_reauth_pin(phone: str, text: str, session: dict) -> str:
    from app.core.security import verify_pin
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_balances
    from app.integrations.whatsapp.messages import BotMessage, Btn

    pin = text.strip()
    user = await get_user_by_phone(phone)
    if not user:
        await session_manager.clear(phone)
        return "No encontré tu cuenta."

    ctx = session.get("context", {})
    attempts = ctx.get("pin_attempts", 0)

    if not verify_pin(pin, user["pin_hash"]):
        attempts += 1
        if attempts >= 3:
            # Persistir bloqueo 30 min en sesión — sobrevive a cualquier mensaje nuevo
            blocked_until = _time.time() + 30 * 60
            await session_manager.set_state(
                phone, ConversationState.AWAITING_REAUTH_CEDULA,
                context={"pin_blocked_until": blocked_until, "pin_attempts": 0},
            )
            logger.warning("reauth: cuenta bloqueada por 30min — phone=%s", phone)
            return (
                "🔴 *Cuenta bloqueada temporalmente.*\n\n"
                "3 intentos fallidos de PIN. Espera *30 minutos* e intenta de nuevo.\n\n"
                "Si olvidaste tu PIN, escribe *recuperar PIN*."
            )
        await session_manager.set_state(
            phone, ConversationState.AWAITING_REAUTH_PIN,
            context={"pin_attempts": attempts}
        )
        return f"❌ PIN incorrecto. Te quedan *{3 - attempts} intento(s)*:"

    await session_manager.set_state(phone, ConversationState.AUTHENTICATED)
    name     = user.get("name", "").split()[0]
    balances = await get_balances(user["id"])
    fiat     = balances["fiat"]
    usdt     = balances["usdt"]
    usdc     = balances["usdc"]

    if usdt > 0 or usdc > 0:
        saldo_parts = [f"🏦 USD:   *${fiat:.2f}*"]
        if usdt > 0:
            saldo_parts.append(f"🪙 USDT: *{usdt:.2f}*")
        if usdc > 0:
            saldo_parts.append(f"🔵 USDC: *{usdc:.2f}*")
        saldo_line = "\n".join(saldo_parts)
    else:
        saldo_line = f"💰 Saldo: *${fiat:.2f} USD*"

    return BotMessage(
        text=(
            f"✅ *¡Bienvenido, {name}!*\n\n"
            f"{saldo_line}\n\n"
            "¿Qué hacemos?\n\n"
            "🔒 _Por tu seguridad, borra este chat regularmente._"
        ),
        buttons=[
            Btn("btn_send",     "💸 Enviar"),
            Btn("btn_withdraw", "📤 Retirar"),
            Btn("btn_more",     "📋 Menú"),
        ],
    )


async def _handle_pin_setup_start(phone: str) -> str:
    await session_manager.set_state(phone, ConversationState.AWAITING_PIN_SET)
    return "Escribe tu nuevo *PIN de 6 dígitos*:"
