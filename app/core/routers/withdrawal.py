"""
Handlers de retiros fiat (USD → cuenta bancaria ecuatoriana).
"""

from decimal import Decimal

from app.core.session import ConversationState, session_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────────────

_BANK_OPTIONS = {
    "opt_bank_pichincha":  "Banco Pichincha",
    "opt_bank_guayaquil":  "Banco Guayaquil",
    "opt_bank_pacifico":   "Banco Pacífico",
    "opt_bank_produbanco": "Produbanco",
}


# ─── UI helpers ───────────────────────────────────────────────────────────────

def _bank_list_message(header: str = "🏦 ¿En qué banco tienes tu cuenta?"):
    from app.integrations.whatsapp.messages import BotMessage, ListSection, ListRow
    return BotMessage(
        text=header,
        sections=[
            ListSection(
                title="Bancos disponibles",
                rows=[
                    ListRow("opt_bank_pichincha",  "🏦 Banco Pichincha", ""),
                    ListRow("opt_bank_guayaquil",  "🏦 Banco Guayaquil", ""),
                    ListRow("opt_bank_pacifico",   "🏦 Banco Pacífico",  ""),
                    ListRow("opt_bank_produbanco", "🏦 Produbanco",       ""),
                ],
            )
        ],
        list_button_label="Seleccionar banco",
    )


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def _handle_withdraw_start(phone: str, parsed=None) -> str:
    """Muestra selección de método: USD a banco o USDT a wallet."""
    from app.integrations.whatsapp.messages import BotMessage, Btn
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_balances

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    balances = await get_balances(user["id"])
    fiat = balances["fiat"]
    usdt = balances["usdt"]

    return BotMessage(
        text=(
            f"📤 *Retirar — elige método:*\n\n"
            f"🏦 Fiat disponible:  *${fiat:.2f} USD*\n"
            f"🪙 USDT disponible: *${usdt:.2f} USDT*"
        ),
        buttons=[
            Btn("btn_withdraw_fiat", "💵 Retirar USD"),
            Btn("btn_withdraw_usdt", "🪙 Retirar USDT"),
        ],
    )


async def _handle_withdraw_fiat_start(phone: str, parsed=None) -> str:
    """Entrada al flujo fiat: pide monto o lo toma de parsed."""
    from app.integrations.whatsapp.messages import BotMessage, Btn
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_balance
    from app.core.fees import fee_options_text, INSTANT_MINIMUM, EXPRESS_FEE

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    amount = parsed.amount if parsed else None
    if not amount:
        await session_manager.set_state(phone, ConversationState.AWAITING_WITHDRAW_AMOUNT)
        balance = await get_balance(user["id"])
        return f"💸 ¿Cuánto quieres retirar?\n\nTu saldo disponible: *${balance:.2f} USD*"

    if amount < 10:
        return "El monto mínimo de retiro es *$10.00*."

    balance = await get_balance(user["id"])
    if balance < amount:
        return f"❌ Saldo insuficiente. Tienes *${balance:.2f} USD*."

    if amount < INSTANT_MINIMUM:
        receives = amount - EXPRESS_FEE
        await session_manager.set_state(
            phone, ConversationState.AWAITING_WITHDRAW_BANK,
            context={"withdraw_amount": str(amount), "withdraw_type": "express"},
        )
        return _bank_list_message(
            header=f"💸 Retiro *${amount:.2f}* · Fee ${EXPRESS_FEE:.2f} · Recibes *${receives:.2f}*"
        )

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_TYPE,
        context={"withdraw_amount": str(amount)},
    )
    return BotMessage(
        text=fee_options_text(amount),
        buttons=[
            Btn("btn_normal",  "🕐 Normal (Gratis)"),
            Btn("btn_instant", "⚡ Instantáneo"),
            Btn("btn_cancel",  "❌ Cancelar"),
        ],
    )


async def _handle_withdraw_amount_input(phone: str, text: str, session: dict) -> str:
    """Recibe el monto cuando el usuario no lo escribió junto al comando."""
    import re
    from decimal import InvalidOperation
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_balance
    from app.modules.fiat.withdrawals import check_withdrawal_limits
    from app.modules.fiat.fraud import check_withdrawal_velocity, check_blacklist
    from app.core.fees import INSTANT_MINIMUM, EXPRESS_FEE, fee_options_text
    from app.integrations.whatsapp.messages import BotMessage, Btn

    match = re.search(r"[\$]?\s*(\d+(?:[.,]\d{1,2})?)", text)
    if not match:
        await session_manager.clear(phone)
        return await _handle_withdraw_start(phone)

    try:
        amount = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return "Monto inválido. Escribe solo el número, por ejemplo: *50*"

    if amount < 10:
        return "El monto mínimo de retiro es *$10.00*."

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta."

    balance = await get_balance(user["id"])
    if balance < amount:
        return f"❌ Saldo insuficiente.\n\nQuieres retirar *${amount:.2f}* pero tienes *${balance:.2f} USD*."

    bl = check_blacklist(phone=user.get("phone"), cedula=user.get("cedula"))
    if bl.blocked:
        return "❌ Tu cuenta tiene una restricción activa. Escribe *soporte* para más información."

    vel = check_withdrawal_velocity(user)
    if vel.blocked:
        return (
            "⏳ *Demasiados intentos en poco tiempo.*\n\n"
            "Por seguridad, espera un momento antes de solicitar otro retiro."
        )

    limit_error = await check_withdrawal_limits(user["id"], amount)
    if limit_error:
        return limit_error

    # check_withdrawal_fraud se llama en _handle_withdraw_pin cuando ya
    # tenemos cuenta bancaria y titular reales — no antes con datos vacíos.

    if amount < INSTANT_MINIMUM:
        receives = amount - EXPRESS_FEE
        await session_manager.set_state(
            phone, ConversationState.AWAITING_WITHDRAW_BANK,
            context={"withdraw_amount": str(amount), "withdraw_type": "express"},
        )
        return _bank_list_message(
            header=f"💸 Retiro *${amount:.2f}* · Fee ${EXPRESS_FEE:.2f} · Recibes *${receives:.2f}*"
        )

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_TYPE,
        context={"withdraw_amount": str(amount)},
    )
    return BotMessage(
        text=fee_options_text(amount),
        buttons=[
            Btn("btn_normal",  "🕐 Normal (Gratis)"),
            Btn("btn_instant", "⚡ Instantáneo"),
            Btn("btn_cancel",  "❌ Cancelar"),
        ],
    )


async def _handle_withdraw_type(phone: str, text: str, session: dict) -> str:
    from app.core.fees import WithdrawalType, calculate_fee, fee_options_text
    from app.integrations.whatsapp.messages import BotMessage, Btn

    ctx = session.get("context", {})
    t   = text.strip().lower()

    if t in ("no", "cancelar", "cancel"):
        await session_manager.clear(phone)
        return "❌ Retiro cancelado."

    if t in ("1", "normal", "btn_normal"):
        wtype = WithdrawalType.NORMAL
    elif t in ("2", "instantáneo", "instantaneo", "instant", "btn_instant"):
        wtype = WithdrawalType.INSTANT
    else:
        amount_ctx = Decimal(ctx.get("withdraw_amount", "0"))
        return BotMessage(
            text=fee_options_text(amount_ctx),
            buttons=[
                Btn("btn_normal",  "🕐 Normal (Gratis)"),
                Btn("btn_instant", "⚡ Instantáneo"),
                Btn("btn_cancel",  "❌ Cancelar"),
            ],
        )

    amount = Decimal(ctx.get("withdraw_amount", "0"))
    fee    = calculate_fee(amount, wtype)

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_BANK,
        context={"withdraw_type": wtype.value, "withdraw_fee": str(fee)},
    )
    return _bank_list_message()


async def _handle_withdraw_bank(phone: str, text: str, session: dict) -> str:
    from app.integrations.whatsapp.messages import BotMessage, Btn

    bank = _BANK_OPTIONS.get(text.strip().lower()) or text.strip().title()
    if len(bank) < 3:
        return _bank_list_message()

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_ACCOUNT_TYPE,
        context={"withdraw_bank": bank},
    )
    return BotMessage(
        text=f"¿Qué tipo de cuenta tienes en *{bank}*?",
        buttons=[
            Btn("btn_savings",  "💚 Ahorros"),
            Btn("btn_checking", "💼 Corriente"),
        ],
    )


async def _handle_withdraw_account_type(phone: str, text: str, session: dict) -> str:
    from app.integrations.whatsapp.messages import BotMessage, Btn

    t = text.strip().lower()
    if t in ("1", "ahorros", "savings", "btn_savings"):
        account_type = "Ahorros"
    elif t in ("2", "corriente", "checking", "btn_checking"):
        account_type = "Corriente"
    else:
        ctx  = session.get("context", {})
        bank = ctx.get("withdraw_bank", "tu banco")
        return BotMessage(
            text=f"¿Qué tipo de cuenta tienes en *{bank}*?",
            buttons=[
                Btn("btn_savings",  "💚 Ahorros"),
                Btn("btn_checking", "💼 Corriente"),
            ],
        )

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_ACCOUNT_NUMBER,
        context={"withdraw_account_type": account_type},
    )
    return f"✅ Cuenta de *{account_type}*.\n\nEscribe el *número de cuenta* (sin espacios):"


async def _handle_withdraw_account_number(phone: str, text: str, session: dict) -> str:
    account_number = text.strip().replace(" ", "")
    if not account_number.isdigit() or len(account_number) < 10:
        return "El número de cuenta debe tener al menos 10 dígitos. Intenta de nuevo:"

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_ACCOUNT_NUMBER_CONFIRM,
        context={"withdraw_account_number_temp": account_number},
    )
    return (
        "🔄 *Confirma el número de cuenta:*\n\n"
        "Escríbelo de nuevo para asegurarnos de que no haya errores:"
    )


async def _handle_withdraw_account_number_confirm(phone: str, text: str, session: dict) -> str:
    account_number = text.strip().replace(" ", "")
    ctx  = session.get("context", {})
    temp = ctx.get("withdraw_account_number_temp", "")

    if not account_number.isdigit() or len(account_number) < 10:
        return "El número de cuenta debe tener al menos 10 dígitos. Intenta de nuevo:"

    if account_number != temp:
        await session_manager.set_state(
            phone, ConversationState.AWAITING_WITHDRAW_ACCOUNT_NUMBER,
            context={"withdraw_account_number_temp": ""},
        )
        return (
            "❌ *Los números no coinciden.*\n\n"
            "Vuelve a ingresar el número de cuenta bancaria:"
        )

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_ACCOUNT_HOLDER,
        context={
            "withdraw_account_number": account_number,
            "withdraw_account_number_temp": "",
        },
    )
    return (
        "✅ Número confirmado.\n\n"
        "¿A nombre de quién está la cuenta?\n"
        "Escribe el *nombre completo del titular*:"
    )


async def _handle_withdraw_account_holder(phone: str, text: str, session: dict) -> str:
    from app.integrations.whatsapp.messages import BotMessage, Btn

    holder = text.strip().title()
    if len(holder) < 5:
        return "Escribe el nombre completo del titular de la cuenta:"

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_OWN_OR_THIRD,
        context={"withdraw_account_holder": holder},
    )
    return BotMessage(
        text=f"¿La cuenta a nombre de *{holder}* es tuya o de otra persona?",
        buttons=[
            Btn("btn_own_account",   "👤 Es mía"),
            Btn("btn_third_account", "👥 Es de otra persona"),
        ],
    )


async def _handle_withdraw_own_or_third(phone: str, text: str, session: dict) -> str:
    from app.core.fees import calculate_fee, WithdrawalType
    from app.integrations.whatsapp.messages import BotMessage, Btn

    t   = text.strip().lower()
    ctx = session.get("context", {})

    if t in ("btn_own_account", "es mía", "es mia", "mia", "propia", "1"):
        from app.modules.auth.register import get_user_by_phone
        from app.modules.fiat.withdrawals import check_holder_name

        amount   = Decimal(ctx.get("withdraw_amount", "0"))
        wtype    = WithdrawalType(ctx.get("withdraw_type", "normal"))
        fee      = calculate_fee(amount, wtype)
        receives = amount - fee
        bank     = ctx.get("withdraw_bank", "")
        acc_type = ctx.get("withdraw_account_type", "")
        acc_num  = ctx.get("withdraw_account_number", "")
        holder   = ctx.get("withdraw_account_holder", "")

        name_warning = ""
        user = await get_user_by_phone(phone)
        if user and holder and not check_holder_name(user.get("name", ""), holder):
            name_warning = (
                "\n⚠️ _El nombre del titular no coincide con tu cuenta BananaPay. "
                "Asegúrate de que la cuenta es tuya._\n"
            )

        await session_manager.set_state(
            phone, ConversationState.AWAITING_WITHDRAW_PIN,
            context={"is_third_party": False},
        )
        return (
            f"📋 *Resumen del retiro:*\n\n"
            f"💰 Retiras:  *${amount:.2f}*\n"
            f"💸 Fee:      *${fee:.2f}*\n"
            f"✅ Recibes:  *${receives:.2f}*\n\n"
            f"🏦 {bank} — {acc_type}\n"
            f"🔢 Cuenta: *{acc_num}*\n"
            f"👤 Titular: *{holder}*\n"
            f"{name_warning}\n"
            "🔐 Ingresa tu PIN para confirmar:"
        )

    elif t in ("btn_third_account", "es de otra persona", "tercero", "otra persona", "2"):
        await session_manager.set_state(
            phone, ConversationState.AWAITING_WITHDRAW_RECIPIENT_CEDULA,
            context={"is_third_party": True},
        )
        return "Ingresa el número de *cédula del titular* de la cuenta\n(10 dígitos):"

    else:
        holder = ctx.get("withdraw_account_holder", "el titular")
        return BotMessage(
            text=f"¿La cuenta a nombre de *{holder}* es tuya o de otra persona?",
            buttons=[
                Btn("btn_own_account",   "👤 Es mía"),
                Btn("btn_third_account", "👥 Es de otra persona"),
            ],
        )


async def _handle_withdraw_recipient_cedula(phone: str, text: str, session: dict) -> str:
    from app.utils.validators import validate_cedula

    cedula = text.strip().replace(" ", "")
    if not validate_cedula(cedula):
        return "Cédula inválida. Ingresa los 10 dígitos correctos:"

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_RECIPIENT_PHONE,
        context={"recipient_cedula": cedula},
    )
    return (
        "¿A qué número de WhatsApp le avisamos cuando llegue el dinero?\n\n"
        "Ejemplo: _0991234567_"
    )


async def _handle_withdraw_recipient_phone(phone: str, text: str, session: dict) -> str:
    import re
    from app.core.fees import calculate_fee, WithdrawalType
    from app.utils.phone import normalize_phone

    match = re.search(r"(?:\+593|0593|593|0)\d{9}", text.strip())
    raw_phone = match.group(0) if match else text.strip()
    try:
        recipient_phone = normalize_phone(raw_phone)
    except Exception:
        return "Número inválido. Escribe el celular del receptor, ej: _0991234567_:"

    ctx      = session.get("context", {})
    amount   = Decimal(ctx.get("withdraw_amount", "0"))
    wtype    = WithdrawalType(ctx.get("withdraw_type", "normal"))
    fee      = calculate_fee(amount, wtype)
    receives = amount - fee
    bank     = ctx.get("withdraw_bank", "")
    acc_type = ctx.get("withdraw_account_type", "")
    acc_num  = ctx.get("withdraw_account_number", "")
    holder   = ctx.get("withdraw_account_holder", "")

    await session_manager.set_state(
        phone, ConversationState.AWAITING_WITHDRAW_PIN,
        context={"recipient_phone": recipient_phone},
    )
    return (
        f"📋 *Resumen del retiro:*\n\n"
        f"💰 Retiras:  *${amount:.2f}*\n"
        f"💸 Fee:      *${fee:.2f}*\n"
        f"✅ Recibes:  *${receives:.2f}*\n\n"
        f"🏦 {bank} — {acc_type}\n"
        f"🔢 Cuenta: *{acc_num}*\n"
        f"👤 Titular: *{holder}*\n"
        f"📱 Notificar a: *{recipient_phone}*\n\n"
        "🔐 Ingresa tu PIN para confirmar:"
    )


async def _handle_withdraw_pin(phone: str, text: str, session: dict) -> str:
    from app.config import settings
    from app.core.security import verify_pin
    from app.core.fees import calculate_fee, WithdrawalType
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.withdrawals import create_withdrawal, save_bank_account
    from app.integrations.whatsapp.client import send_message

    ctx      = session.get("context", {})
    attempts = ctx.get("withdraw_pin_attempts", 0)

    user = await get_user_by_phone(phone)
    if not user:
        await session_manager.clear(phone)
        return "❌ No encontré tu cuenta."

    if not verify_pin(text.strip(), user["pin_hash"]):
        attempts += 1
        if attempts >= 3:
            await session_manager.clear(phone)
            return "🔒 *Demasiados intentos incorrectos.* Retiro cancelado por seguridad."
        await session_manager.set_state(
            phone, ConversationState.AWAITING_WITHDRAW_PIN,
            context={"withdraw_pin_attempts": attempts},
        )
        return f"❌ PIN incorrecto. Te quedan *{3 - attempts} {'intento' if 3 - attempts == 1 else 'intentos'}*."

    amount           = Decimal(ctx.get("withdraw_amount", "0"))
    wtype            = WithdrawalType(ctx.get("withdraw_type", "normal"))
    fee              = calculate_fee(amount, wtype)
    receives         = amount - fee

    if receives <= 0:
        await session_manager.clear(phone)
        return (
            f"❌ El monto *${amount:.2f}* no cubre el fee de *${fee:.2f}*.\n\n"
            "Escribe *retirar* e ingresa un monto mayor."
        )

    bank             = ctx.get("withdraw_bank", "")
    acc_type         = ctx.get("withdraw_account_type", "")
    acc_num          = ctx.get("withdraw_account_number", "")
    holder           = ctx.get("withdraw_account_holder", "")
    recipient_phone  = ctx.get("recipient_phone")
    recipient_cedula = ctx.get("recipient_cedula")

    from app.modules.fiat.fraud import check_withdrawal_fraud
    fraud = check_withdrawal_fraud(user=user, amount=amount, account_number=acc_num, account_holder=holder)
    if fraud.blocked:
        await session_manager.clear(phone)
        logger.warning("Retiro bloqueado por fraude: phone=%s reason=%s", phone, fraud.reason)
        return (
            "❌ *No pudimos procesar tu retiro.*\n\n"
            "Si crees que es un error, escribe *soporte* para contactar a un agente."
        )

    try:
        withdrawal = await create_withdrawal(
            user_id=user["id"],
            amount=amount,
            fee=fee,
            amount_received=receives,
            withdrawal_type=wtype.value,
            bank_name=bank,
            account_type=acc_type,
            account_number=acc_num,
            account_holder=holder,
            recipient_phone=recipient_phone,
            recipient_cedula=recipient_cedula,
        )
    except Exception as exc:
        logger.error("Error creando retiro: user=%s error=%s", phone, exc)
        await session_manager.clear(phone)
        return (
            "❌ Ocurrió un error al procesar tu retiro.\n\n"
            "Tu saldo *no fue afectado*. Escribe *retirar* para intentar de nuevo."
        )

    try:
        await save_bank_account(user["id"], bank, acc_type, acc_num, holder)
    except Exception as exc:
        logger.warning("No se pudo guardar cuenta bancaria: %s", exc)

    await session_manager.clear(phone)

    if settings.admin_whatsapp:
        try:
            tipo_label = {"normal": "Normal (24h)", "instant": "Instantáneo", "express": "Express"}.get(wtype.value, wtype.value)
            await send_message(
                settings.admin_whatsapp,
                f"📤 *Nuevo retiro pendiente*\n\n"
                f"👤 {user['name']} ({user['phone']})\n"
                f"💰 *${amount:.2f}* → recibe *${receives:.2f}* (fee ${fee:.2f})\n"
                f"⚡ Tipo: {tipo_label}\n"
                f"🏦 {bank} — {acc_type}\n"
                f"🔢 Cuenta: {acc_num}\n"
                f"👤 Titular: {holder}\n"
                f"🆔 ID: `{withdrawal['id']}`",
            )
        except Exception as exc:
            logger.warning("No se pudo notificar al admin: %s", exc)

    tiempo = {
        "normal":  "próximas 24 horas",
        "instant": "próximos 5 minutos",
        "express": "próximos 5 minutos",
    }.get(wtype.value, "próximos momentos")

    from app.integrations.whatsapp.messages import post_tx_buttons
    return post_tx_buttons(
        f"✅ *¡Retiro solicitado!*\n\n"
        f"💸 Se transferirán *${receives:.2f}* a {bank}\n"
        f"🔢 {acc_num}\n"
        f"👤 {holder}\n\n"
        f"⏱ Tu transferencia llegará en los *{tiempo}*.\n\n"
        "Toca *Menú* para seguir o *Salir* para cerrar tu sesión. 🍌"
    )


async def _handle_withdraw_account(phone: str, text: str, session: dict) -> str:
    """Fallback legacy — redirige al flujo actual."""
    await session_manager.clear(phone)
    return "Escribe *retirar [monto]* para iniciar un retiro, ej: *retirar 50*"


async def _handle_withdraw_confirm(phone: str, text: str, session: dict) -> str:
    """Fallback legacy — redirige al flujo actual."""
    await session_manager.clear(phone)
    return "Escribe *retirar [monto]* para iniciar un retiro, ej: *retirar 50*"
