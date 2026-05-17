"""
Handlers de retiros USDT TRC-20 on-chain.
"""

from app.core.session import ConversationState, session_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _handle_usdt_withdraw_start(phone: str) -> str:
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_usdt_balance
    from app.modules.crypto.withdraw import WITHDRAW_FEE, WITHDRAW_MIN

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    balance = await get_usdt_balance(user["id"])
    if balance <= WITHDRAW_MIN:
        return (
            f"No tienes suficiente USDT para retirar.\n\n"
            f"Saldo: *{balance:.2f} USDT*\n"
            f"Mínimo para retirar: *{WITHDRAW_MIN:.2f} USDT* (+ ${WITHDRAW_FEE:.2f} fee de red)"
        )

    await session_manager.set_state(phone, ConversationState.AWAITING_USDT_WITHDRAW_AMOUNT)
    return (
        f"🪙 *Retirar USDT a tu wallet*\n\n"
        f"Saldo disponible: *{balance:.2f} USDT*\n"
        f"Fee de red: *${WITHDRAW_FEE:.2f}*\n"
        f"Mínimo: *{WITHDRAW_MIN:.2f} USDT*\n\n"
        f"¿Cuánto USDT quieres retirar?"
    )


async def _handle_usdt_withdraw_amount(phone: str, text: str, session: dict) -> str:
    import re
    from decimal import Decimal, InvalidOperation
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_usdt_balance
    from app.modules.crypto.withdraw import WITHDRAW_FEE, WITHDRAW_MIN

    match = re.search(r"\$?(\d+(?:[.,]\d{1,2})?)", text.strip())
    if not match:
        return "Escribe el monto en USDT, ej: *50*"

    try:
        amount = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return "Monto inválido. Escribe solo el número, ej: *50*"

    if amount < WITHDRAW_MIN:
        return f"El mínimo de retiro es *{WITHDRAW_MIN:.2f} USDT*."

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta."

    balance      = await get_usdt_balance(user["id"])
    total_needed = amount + WITHDRAW_FEE
    if balance < total_needed:
        return (
            f"Saldo insuficiente.\n\n"
            f"Quieres retirar *{amount:.2f} USDT* + fee *${WITHDRAW_FEE:.2f}*\n"
            f"Total necesario: *{total_needed:.2f} USDT*\n"
            f"Tu saldo: *{balance:.2f} USDT*"
        )

    await session_manager.set_state(
        phone, ConversationState.AWAITING_USDT_WITHDRAW_ADDRESS,
        context={"usdt_withdraw_amount": str(amount)},
    )
    return (
        f"✅ Monto: *{amount:.2f} USDT* (fee ${WITHDRAW_FEE:.2f} incluido)\n\n"
        f"¿A qué dirección TRC-20 quieres enviar?\n\n"
        f"_(Empieza con T, 34 caracteres — de tu Binance, TronLink, etc.)_"
    )


async def _handle_usdt_withdraw_address(phone: str, text: str, session: dict) -> str:
    from decimal import Decimal
    from app.modules.crypto.withdraw import is_valid_trc20_address, WITHDRAW_FEE

    address = text.strip()
    if not is_valid_trc20_address(address):
        return (
            "❌ Dirección TRC-20 inválida.\n\n"
            "Debe empezar con *T* y tener 34 caracteres.\n"
            "Ejemplo: _TZ9Jys9Vnp9iVobav4qakT7JEKMzhfwPyU_\n\n"
            "Escríbela de nuevo:"
        )

    ctx    = session.get("context", {})
    amount = Decimal(ctx.get("usdt_withdraw_amount", "0"))

    await session_manager.set_state(
        phone, ConversationState.AWAITING_USDT_WITHDRAW_PIN,
        context={"usdt_withdraw_address": address},
    )
    return (
        f"📋 *Resumen del retiro:*\n\n"
        f"🪙 Envías:   *{amount:.2f} USDT*\n"
        f"💸 Fee red:  *${WITHDRAW_FEE:.2f} USDT*\n"
        f"✅ Recibes:  *{amount:.2f} USDT* en tu wallet\n\n"
        f"📬 Destino:\n`{address}`\n\n"
        f"⚠️ _Verifica la dirección — las transacciones blockchain son irreversibles._\n\n"
        f"🔐 Ingresa tu PIN para confirmar:"
    )


async def _handle_usdt_withdraw_pin(phone: str, text: str, session: dict) -> str:
    from decimal import Decimal
    from app.core.security import verify_pin
    from app.modules.auth.register import get_user_by_phone
    from app.modules.crypto.withdraw import execute_usdt_withdrawal
    from app.config import settings
    from app.integrations.whatsapp.client import send_message

    ctx      = session.get("context", {})
    attempts = ctx.get("usdt_pin_attempts", 0)

    user = await get_user_by_phone(phone)
    if not user:
        await session_manager.clear(phone)
        return "No encontré tu cuenta."

    if not verify_pin(text.strip(), user["pin_hash"]):
        attempts += 1
        if attempts >= 3:
            await session_manager.clear(phone)
            return "🔒 *Demasiados intentos incorrectos.* Retiro cancelado."
        await session_manager.set_state(
            phone, ConversationState.AWAITING_USDT_WITHDRAW_PIN,
            context={"usdt_pin_attempts": attempts},
        )
        return f"❌ PIN incorrecto. Te quedan *{3 - attempts} {'intento' if 3-attempts == 1 else 'intentos'}*."

    amount  = Decimal(ctx.get("usdt_withdraw_amount", "0"))
    address = ctx.get("usdt_withdraw_address", "")

    await session_manager.clear(phone)

    result = await execute_usdt_withdrawal(
        user_id=user["id"],
        to_address=address,
        amount_usdt=amount,
    )

    if not result["ok"]:
        return f"❌ *Retiro fallido*\n\n{result['error']}\n\nEscribe *retirar usdt* para intentar de nuevo."

    tx_hash     = result["tx_hash"]
    new_balance = result["new_balance"]
    tronscan    = f"https://tronscan.org/#/transaction/{tx_hash}"

    if settings.admin_whatsapp:
        try:
            await send_message(
                settings.admin_whatsapp,
                f"📤 *Retiro USDT procesado*\n\n"
                f"👤 {user['name']} ({user['phone']})\n"
                f"💸 *{amount:.2f} USDT* -> `{address[:16]}...`\n"
                f"TX: `{tx_hash[:20]}...`",
            )
        except Exception as exc:
            logger.warning("No se pudo notificar admin retiro USDT: %s", exc)

    from app.integrations.whatsapp.messages import post_tx_buttons
    return post_tx_buttons(
        f"✅ *¡USDT enviado!*\n\n"
        f"🪙 *{amount:.2f} USDT* en camino a tu wallet\n\n"
        f"TX: `{tx_hash[:20]}...`\n"
        f"🔍 {tronscan}\n\n"
        f"💰 Saldo restante: *{new_balance:.2f} USDT*\n\n"
        f"_Confirmación en la blockchain en ~1 minuto_\n\n"
        "Toca *Menú* para seguir o *Salir* para cerrar tu sesión."
    )
