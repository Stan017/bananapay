"""
receive.py — Handler de cobro con QR.

Flujo:
  1. "cobrar"         → selector [BananaPay | USDT | USDC]
  2. Elige tipo       → pregunta monto ("0" o vacío = sin monto fijo)
  3. Ingresa monto    → genera QR y envía como imagen

Atajo directo:
  "cobrar 50 USDT"   → salta al paso 3 directamente
"""

import urllib.parse
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.core.session import ConversationState, session_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDC_CONTRACT = "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8"


# ─── Paso 1: selector de tipo ─────────────────────────────────────────────────

async def _handle_receive_start(phone: str, parsed) -> object:
    """
    Muestra el selector de tipo de QR.
    Si el usuario ya especificó moneda + monto (ej. "cobrar 50 USDT"),
    va directo a generar el QR.
    """
    from app.integrations.whatsapp.messages import BotMessage, Btn
    from app.modules.auth.register import get_user_by_phone

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    currency = (getattr(parsed, "currency", None) or "").upper()
    amount   = getattr(parsed, "amount", None)

    # Atajo: ya tiene moneda crypto + monto → QR directo
    if currency in ("USDT", "USDC") and amount and amount > 0:
        return await _build_crypto_qr(user, currency, amount)

    # Atajo: solo moneda crypto sin monto → pedir monto
    if currency in ("USDT", "USDC"):
        await session_manager.set_state(
            phone, ConversationState.AWAITING_RECEIVE_AMOUNT,
            context={"receive_currency": currency},
        )
        return (
            f"💰 *¿Cuánto quieres cobrar en {currency}?*\n\n"
            f"Escribe el monto (ej: _50_) o *0* si quieres un QR sin monto fijo."
        )

    # Selector de tipo
    primer_nombre = user["name"].strip().split()[0]
    return BotMessage(
        text=(
            f"💳 *Cobrar con QR, {primer_nombre}*\n\n"
            "Genera un código QR para que te paguen.\n\n"
            "🍌 *BananaPay* — entre usuarios de la app\n"
            "🪙 *USDT* — cualquier wallet TRC-20 externa\n"
            "🔵 *USDC* — cualquier wallet TRC-20 externa\n\n"
            "¿Qué tipo de QR necesitas?"
        ),
        buttons=[
            Btn("btn_receive_bp",   "🍌 BananaPay"),
            Btn("btn_receive_usdt", "🪙 USDT"),
            Btn("btn_receive_usdc", "🔵 USDC"),
        ],
    )


# ─── Paso 2: handlers de botones → piden monto ───────────────────────────────

async def _handle_receive_bp(phone: str) -> object:
    """Pide monto antes de generar el QR BananaPay."""
    await session_manager.set_state(
        phone, ConversationState.AWAITING_RECEIVE_AMOUNT,
        context={"receive_currency": "BP"},
    )
    return (
        "🍌 *¿Cuánto quieres cobrar?*\n\n"
        "Escribe el monto en USD (ej: _25_) o *0* para QR sin monto fijo."
    )


async def _handle_receive_usdt(phone: str) -> object:
    """Pide monto antes de generar el QR USDT."""
    await session_manager.set_state(
        phone, ConversationState.AWAITING_RECEIVE_AMOUNT,
        context={"receive_currency": "USDT"},
    )
    return (
        "🪙 *¿Cuánto quieres cobrar en USDT?*\n\n"
        "Escribe el monto (ej: _50_) o *0* para QR sin monto fijo."
    )


async def _handle_receive_usdc(phone: str) -> object:
    """Pide monto antes de generar el QR USDC."""
    await session_manager.set_state(
        phone, ConversationState.AWAITING_RECEIVE_AMOUNT,
        context={"receive_currency": "USDC"},
    )
    return (
        "🔵 *¿Cuánto quieres cobrar en USDC?*\n\n"
        "Escribe el monto (ej: _100_) o *0* para QR sin monto fijo."
    )


# ─── Paso 3: recibe el monto y genera el QR ──────────────────────────────────

async def _handle_receive_amount(phone: str, text: str, session: dict) -> object:
    """
    Procesa el monto ingresado y genera el QR correspondiente.
    Acepta: "50", "50.00", "0" (sin monto), "sin monto".
    """
    from app.modules.auth.register import get_user_by_phone

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta."

    currency = session.get("context", {}).get("receive_currency", "USDT")

    # Parsear monto
    cleaned = text.strip().lower().replace(",", ".")
    amount: Optional[Decimal] = None

    if cleaned not in ("0", "sin monto", "no", "ninguno", "skip", "saltar"):
        try:
            val = Decimal(cleaned)
            if val < 0:
                return "⚠️ El monto no puede ser negativo. Intenta de nuevo:"
            if val > 0:
                amount = val
        except InvalidOperation:
            return (
                "⚠️ No entendí ese monto. Escribe un número como _50_ o _100.50_\n"
                "O escribe *0* para QR sin monto fijo."
            )

    # Volver a estado autenticado
    await session_manager.set_state(phone, ConversationState.AUTHENTICATED)

    if currency == "BP":
        return await _build_bananapay_qr(user, amount)
    return await _build_crypto_qr(user, currency, amount)


# ─── Generadores de QR ────────────────────────────────────────────────────────

async def _build_bananapay_qr(user: dict, amount: Optional[Decimal] = None) -> object:
    """QR para pagos internos BananaPay, con monto opcional."""
    from app.integrations.whatsapp.messages import ImageMessage
    from app.utils.qr_generator import generate_payment_qr

    name   = user["name"].strip()
    cedula = user.get("cedula", "")
    first  = name.split()[0]

    # URI con monto opcional
    qr_data = f"bananapay://pay?cedula={cedula}&name={urllib.parse.quote(first)}"
    if amount and amount > 0:
        qr_data += f"&amount={amount}"
        amt_str     = f"{amount:f}".rstrip("0").rstrip(".")
        subtitle    = f"Cobro BananaPay  ·  ${amt_str} USD"
        amt_caption = f" — *${amt_str} USD*"
    else:
        subtitle    = "Escanea para enviarme dinero"
        amt_caption = ""

    try:
        img_bytes = generate_payment_qr(
            data     = qr_data,
            title    = "🍌 Cobrar con BananaPay",
            subtitle = subtitle,
            username = name,
        )
        # Número local para el comando de texto (0991234567)
        phone_local = user.get("phone", "").replace("+593", "0")
        if amount and amount > 0:
            amt_str_pay = f"{amount:f}".rstrip("0").rstrip(".")
            pay_cmd     = f"enviar {amt_str_pay} a {phone_local}"
        else:
            pay_cmd = f"enviar [monto] a {phone_local}"

        caption = (
            f"🍌 *{name}*{amt_caption}\n\n"
            f"*Opción 1 — Escanear:* reenvía esta imagen al bot y lo procesa solo.\n"
            f"*Opción 2 — Escribir:* `{pay_cmd}`\n\n"
            f"_Solo válido entre usuarios BananaPay._"
        )
        from app.integrations.whatsapp.messages import post_tx_buttons
        return ImageMessage(
            image_bytes=img_bytes,
            caption=caption,
            follow_up=post_tx_buttons("¿Qué hacemos ahora?"),
        )

    except ImportError:
        return (
            f"⚠️ Generador de QR no disponible.\n\n"
            f"Comparte tu cédula directamente:\n"
            f"*Cédula:* `{cedula}`\n*Nombre:* {name}"
        )
    except Exception as exc:
        logger.error("Error generando QR BananaPay user=%s: %s", user.get("id"), exc)
        return "⚠️ No se pudo generar el QR. Intenta de nuevo."


async def _build_crypto_qr(
    user: dict,
    currency: str,
    amount: Optional[Decimal],
) -> object:
    """
    QR para cobro en USDT o USDC (TRC-20).
    Sin monto → dirección pura (compatible con cualquier wallet).
    Con monto → URI tron: estándar (TronLink, TrustWallet, Binance, etc.).
    """
    from app.integrations.whatsapp.messages import ImageMessage
    from app.utils.qr_generator import generate_payment_qr

    wallet_address = user.get("wallet_address")
    if not wallet_address:
        return (
            f"⚠️ No tienes wallet TRC-20 asignada.\n"
            f"Escribe *soporte* y te la configuramos."
        )

    name     = user["name"].strip()
    icon     = "🪙" if currency == "USDT" else "🔵"
    contract = USDT_CONTRACT if currency == "USDT" else USDC_CONTRACT

    # URI TRC-20 estándar
    if amount and amount > 0:
        qr_data  = f"tron:{wallet_address}?amount={amount}&token={contract}"
        amt_text = f"{amount:f}".rstrip("0").rstrip(".")
        subtitle = f"Red TRC-20  ·  {currency}  ·  {amt_text} {currency}"
        amt_caption = f" — *{amt_text} {currency}*"
    else:
        qr_data     = wallet_address
        subtitle    = f"Red TRC-20  ·  {currency}"
        amt_caption = ""

    try:
        img_bytes = generate_payment_qr(
            data     = qr_data,
            title    = f"{icon} Cobrar {currency}",
            subtitle = subtitle,
            username = name,
        )
        caption = (
            f"{icon} *{name}*{amt_caption}\n\n"
            f"📍 *Dirección TRC-20:*\n`{wallet_address}`\n\n"
            f"⚠️ *Solo red TRC-20* — otras redes significan pérdida permanente.\n"
            f"✅ Token: *{currency}*"
        )
        from app.integrations.whatsapp.messages import post_tx_buttons
        return ImageMessage(
            image_bytes=img_bytes,
            caption=caption,
            follow_up=post_tx_buttons("¿Qué hacemos ahora?"),
        )

    except ImportError:
        logger.error("qrcode/Pillow no instalados")
        return (
            f"{icon} *Tu dirección {currency} (TRC-20)*\n\n"
            f"`{wallet_address}`\n\n⚠️ Solo red TRC-20."
        )
    except Exception as exc:
        logger.error("Error generando QR %s user=%s: %s", currency, user.get("id"), exc)
        return (
            f"{icon} *Dirección {currency} (TRC-20)*\n\n"
            f"`{wallet_address}`\n\n⚠️ Solo red TRC-20."
        )
