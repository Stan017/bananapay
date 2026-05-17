"""
Handlers de transferencias P2P entre usuarios BananaPay.
Soporta USD, USDT y USDC.
"""

from app.core.session import ConversationState, session_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ─── Utilidades ───────────────────────────────────────────────────────────────

def _short_name(full_name: str) -> str:
    """
    Convierte "Jacqueline Maria Solórzano Calle" → "Jacqueline S."
    Formato Ecuador: nombre1 nombre2 apellido1 apellido2 (4 palabras)
    """
    parts = full_name.strip().split()
    if not parts:
        return "Usuario"
    if len(parts) == 1:
        return parts[0]
    apellido_idx = 2 if len(parts) >= 4 else 1
    return f"{parts[0]} {parts[apellido_idx][0].upper()}."


def _fmt(amount, currency: str) -> str:
    """Formatea monto con símbolo correcto: $10.00 (USD) o 10.00 USDT."""
    if currency == "USD":
        return f"${amount:.2f}"
    return f"{amount:.2f} {currency}"


def _icon(currency: str) -> str:
    return {"USD": "💵", "USDT": "🪙", "USDC": "🔵"}.get(currency, "💰")


# ─── Paso 1: inicio del flujo ─────────────────────────────────────────────────

async def _handle_transfer_start(phone: str, parsed) -> object:
    """
    Punto de entrada del flujo de transferencia.

    Si el usuario solo dijo "enviar" sin moneda/monto/destinatario,
    y tiene saldo en más de una moneda → muestra selector de moneda.
    Si ya especificó todo o solo hay una moneda → flujo directo.
    """
    from app.integrations.whatsapp.messages import BotMessage, Btn

    raw       = parsed.raw_recipient or ""
    recipient = parsed.recipient or ""
    amount    = parsed.amount
    currency  = parsed.currency or "USD"

    # Sin monto ni destinatario → posible selector de moneda
    if not recipient and not amount:
        from app.modules.auth.register import get_user_by_phone
        from app.modules.fiat.wallet import get_balances

        user = await get_user_by_phone(phone)
        if user:
            bal  = await get_balances(user["id"])
            btns = []
            if bal["fiat"] > 0:
                btns.append(Btn("btn_send_usd",  "💵 USD"))
            if bal["usdt"] > 0:
                btns.append(Btn("btn_send_usdt", "🪙 USDT"))
            if bal["usdc"] > 0:
                btns.append(Btn("btn_send_usdc", "🔵 USDC"))

            if len(btns) > 1:
                # Más de una moneda → pedir que elija
                lines = ["💸 *¿En qué moneda quieres enviar?*\n"]
                if bal["fiat"] > 0:
                    lines.append(f"💵 USD  —  *${bal['fiat']:.2f}*")
                if bal["usdt"] > 0:
                    lines.append(f"🪙 USDT  —  *{bal['usdt']:.2f}*")
                if bal["usdc"] > 0:
                    lines.append(f"🔵 USDC  —  *{bal['usdc']:.2f}*")
                return BotMessage(text="\n".join(lines), buttons=btns[:3])

            # Solo una moneda con saldo → usarla directamente
            if len(btns) == 1:
                currency = "USDT" if "usdt" in btns[0].id else ("USDC" if "usdc" in btns[0].id else "USD")

        await session_manager.set_state(
            phone,
            ConversationState.AWAITING_TRANSFER_AMOUNT,
            context={"awaiting_field": "phone", "transfer_currency": currency},
        )
        return f"{_icon(currency)} *¿A qué número quieres enviar {currency}?*\n\nEscríbelo así: *0991234567*"

    # Tiene nombre/destinatario pero no es número normalizado
    if not recipient.startswith("+"):
        msg = (
            f"Para enviarle dinero a *{raw}*, necesito su número de WhatsApp.\n\n"
            "Escríbelo así: *0991234567*"
        ) if raw else f"{_icon(currency)} *¿A qué número quieres enviar?*\n\nEscríbelo así: *0991234567*"
        await session_manager.set_state(
            phone,
            ConversationState.AWAITING_TRANSFER_AMOUNT,
            context={
                "awaiting_field": "phone",
                "transfer_raw_recipient": raw,
                "transfer_amount": str(amount) if amount else "",
                "transfer_currency": currency,
            },
        )
        return msg

    # Tiene destinatario pero no monto
    if not amount:
        await session_manager.set_state(
            phone,
            ConversationState.AWAITING_TRANSFER_AMOUNT,
            context={
                "awaiting_field": "amount",
                "transfer_recipient": recipient,
                "transfer_raw_recipient": raw or recipient,
                "transfer_currency": currency,
                "transfer_pin_attempts": 0,
            },
        )
        return f"{_icon(currency)} ¿Cuánto {currency} quieres enviar a *{raw or recipient}*?"

    # Tiene todo → pedir PIN directo
    await session_manager.set_state(
        phone,
        ConversationState.AWAITING_TRANSFER_PIN,
        context={
            "transfer_recipient": recipient,
            "transfer_raw_recipient": raw or recipient,
            "transfer_amount": str(amount),
            "transfer_currency": currency,
            "transfer_pin_attempts": 0,
        },
    )
    return (
        f"💸 *Enviar {_fmt(amount, currency)}* a *{raw or recipient}*\n\n"
        "🔐 Ingresa tu PIN para confirmar:"
    )


# ─── Paso 2: recibe número o monto ───────────────────────────────────────────

async def _handle_transfer_amount(phone: str, text: str, session: dict) -> str:
    import re as _re
    from app.utils.phone import normalize_phone
    from app.utils.currency import parse_amount

    ctx      = session.get("context", {})
    currency = ctx.get("transfer_currency", "USD")

    if ctx.get("awaiting_field") == "phone":
        phone_match = _re.search(r"(?:\+593|0593|593|0)\d{9}", text.strip())
        raw_number  = phone_match.group(0) if phone_match else text.strip()
        recipient   = normalize_phone(raw_number)
        if not recipient:
            return (
                "No reconocí ese número. Escríbelo así: *0991234567* "
                "(con o sin el +593)"
            )

        existing_amount = ctx.get("transfer_amount", "")
        if not existing_amount:
            await session_manager.set_state(
                phone,
                ConversationState.AWAITING_TRANSFER_AMOUNT,
                context={
                    "awaiting_field": "amount",
                    "transfer_recipient": recipient,
                    "transfer_raw_recipient": raw_number,
                    "transfer_currency": currency,
                    "transfer_pin_attempts": 0,
                },
            )
            return f"{_icon(currency)} ¿Cuánto {currency} quieres enviar a *{raw_number}*?"

        await session_manager.set_state(
            phone,
            ConversationState.AWAITING_TRANSFER_PIN,
            context={
                "transfer_recipient": recipient,
                "transfer_raw_recipient": raw_number,
                "transfer_amount": existing_amount,
                "transfer_currency": currency,
                "transfer_pin_attempts": 0,
            },
        )
        return (
            f"💸 *Enviar {existing_amount} {currency}* a *{raw_number}*\n\n"
            "🔐 Ingresa tu PIN para confirmar:"
        )

    # Ingresando monto
    amount_match = _re.search(r"\$?(\d+(?:[.,]\d+)?)", text.strip())
    amount       = parse_amount(amount_match.group(1)) if amount_match else None
    if not amount:
        return "No entendí el monto. Escribe solo el número, por ejemplo: *10* o *50.50*"

    raw_recip = ctx.get("transfer_raw_recipient", ctx.get("transfer_recipient", ""))
    await session_manager.set_state(
        phone,
        ConversationState.AWAITING_TRANSFER_PIN,
        context={
            "transfer_recipient": ctx.get("transfer_recipient", ""),
            "transfer_raw_recipient": raw_recip,
            "transfer_amount": str(amount),
            "transfer_currency": currency,
            "transfer_pin_attempts": 0,
        },
    )
    return (
        f"💸 *Enviar {_fmt(amount, currency)}* a *{raw_recip}*\n\n"
        "🔐 Ingresa tu PIN para confirmar:"
    )


# ─── Paso 3: PIN y ejecución ──────────────────────────────────────────────────

async def _handle_transfer_pin(phone: str, text: str, session: dict) -> object:
    """Verifica el PIN y ejecuta la transferencia. Máximo 3 intentos."""
    from decimal import Decimal
    from app.core.security import verify_pin
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import transfer, get_balance, get_usdt_balance, get_usdc_balance
    from app.integrations.whatsapp.client import send_message as _send_msg
    from app.integrations.whatsapp.messages import post_tx_buttons

    ctx      = session.get("context", {})
    attempts = ctx.get("transfer_pin_attempts", 0)
    currency = ctx.get("transfer_currency", "USD")

    user = await get_user_by_phone(phone)
    if not user:
        await session_manager.clear(phone)
        return "❌ No encontré tu cuenta. Escribe *hola* para empezar."

    if not verify_pin(text.strip(), user["pin_hash"]):
        attempts += 1
        if attempts >= 3:
            await session_manager.clear(phone)
            return "🔒 *Demasiados intentos incorrectos.*\n\nTransferencia cancelada por seguridad."
        await session_manager.set_state(
            phone,
            ConversationState.AWAITING_TRANSFER_PIN,
            context={**ctx, "transfer_pin_attempts": attempts},
        )
        remaining = 3 - attempts
        return f"❌ PIN incorrecto. Te quedan *{remaining} {'intento' if remaining == 1 else 'intentos'}*."

    to_phone = ctx.get("transfer_recipient", "")
    amount   = Decimal(ctx.get("transfer_amount", "0"))
    raw      = ctx.get("transfer_raw_recipient", to_phone)

    result = await transfer(from_phone=phone, to_phone=to_phone, amount=amount, currency=currency)
    await session_manager.clear(phone)

    if not result["ok"]:
        return (
            f"❌ *Transferencia no completada*\n\n"
            f"No pudimos enviar *{_fmt(amount, currency)}* a *{raw}*.\n\n"
            "💰 Tu saldo *no fue afectado*.\n"
            "Escribe _enviar_ para intentar de nuevo."
        )

    sender      = await get_user_by_phone(phone)
    sender_name = _short_name(sender["name"]) if sender else "Alguien"
    icon        = _icon(currency)

    # Notificar al receptor (WhatsApp + push notification si tiene la app)
    try:
        from app.utils.push import notify_transfer_received
        recipient_user = await get_user_by_phone(to_phone)
        if recipient_user:
            if currency == "USDT":
                new_bal = await get_usdt_balance(recipient_user["id"])
                bal_str = f"{new_bal:.2f} USDT"
            elif currency == "USDC":
                new_bal = await get_usdc_balance(recipient_user["id"])
                bal_str = f"{new_bal:.2f} USDC"
            else:
                new_bal = await get_balance(recipient_user["id"])
                bal_str = f"${new_bal:.2f} USD"

            await _send_msg(
                to_phone,
                f"💸 *¡Recibiste dinero!*\n\n"
                f"{icon} *{_fmt(amount, currency)}* de {sender_name}\n"
                f"📊 Tu nuevo saldo {currency}: *{bal_str}*\n\n"
                "Enviado vía BananaPay 🍌"
            )
            # Push notification a la app móvil (si el receptor la tiene instalada)
            await notify_transfer_received(
                recipient_user_id=recipient_user["id"],
                sender_name=sender_name,
                amount=float(amount),
                currency=currency,
            )
    except Exception as exc:
        logger.warning("No se pudo notificar al receptor %s: %s", to_phone, exc)

    return post_tx_buttons(
        f"✅ *¡Enviado!*\n\n"
        f"{icon} *{_fmt(amount, currency)}* a *{raw}*\n\n"
        "Toca *Menú* para seguir o *Salir* para cerrar tu sesión. 🍌"
    )


async def _handle_transfer_confirm(phone: str, text: str, session: dict) -> str:
    """Fallback legacy — redirige al flujo actual."""
    await session_manager.clear(phone)
    return "Escribe *enviar [monto] a [número]* para iniciar una transferencia."
