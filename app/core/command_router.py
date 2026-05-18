"""
Command router — dispatcher principal.
Solo enruta mensajes al handler correcto. Sin lógica de negocio aquí.

Estructura de routers:
  app/core/routers/onboarding.py       — registro y re-autenticación
  app/core/routers/transfer.py         — transferencias P2P
  app/core/routers/deposit.py          — depósitos fiat y USDT
  app/core/routers/withdrawal.py       — retiros fiat a banco
  app/core/routers/crypto_withdrawal.py — retiros USDT on-chain
  app/core/routers/queries.py          — saldo, historial, soporte, misc
"""

import time as _time

from app.core.intent_engine import Intent, ParsedIntent
from app.core.session import ConversationState, session_manager
from app.utils.logger import get_logger

# ─── Routers de dominio ───────────────────────────────────────────────────────
from app.core.routers.onboarding import (
    REGISTRATION_STATES,
    _check_confusion,
    _handle_registration_name,
    _handle_registration_cedula,
    _handle_registration_birth_date,
    _handle_registration_dactilar,
    _handle_registration_email,
    _handle_pin_set,
    _handle_pin_confirm,
    _handle_custody_mode,
    _handle_reauth_cedula,
    _handle_reauth_pin,
    _handle_pin_setup_start,
)
from app.core.routers.transfer import (
    _handle_transfer_start,
    _handle_transfer_amount,
    _handle_transfer_recipient_confirm,
    _handle_transfer_pin,
    _handle_transfer_confirm,
)
from app.core.routers.recovery import (
    handle_recovery_start,
    handle_recovery_cedula,
    handle_recovery_birthdate,
    handle_recovery_pin,
)
from app.core.routers.deposit import (
    _handle_deposit_start,
    _handle_deposit_bank,
    _handle_deposit_usdt,
    _handle_deposit_amount,
    handle_deposit_voucher,   # público — importado por webhook.py
)
from app.core.routers.withdrawal import (
    _handle_withdraw_start,
    _handle_withdraw_fiat_start,
    _handle_withdraw_amount_input,
    _handle_withdraw_type,
    _handle_withdraw_bank,
    _handle_withdraw_account_type,
    _handle_withdraw_account_number,
    _handle_withdraw_account_number_confirm,
    _handle_withdraw_account_holder,
    _handle_withdraw_own_or_third,
    _handle_withdraw_recipient_cedula,
    _handle_withdraw_recipient_phone,
    _handle_withdraw_pin,
    _handle_withdraw_account,
    _handle_withdraw_confirm,
)
from app.core.routers.crypto_withdrawal import (
    _handle_usdt_withdraw_start,
    _handle_usdt_withdraw_amount,
    _handle_usdt_withdraw_address,
    _handle_usdt_withdraw_pin,
)
from app.core.routers.queries import (
    _handle_balance,
    _handle_history,
    _handle_greeting,
    _handle_support,
    _handle_crypto_price,
    _handle_crypto_buy,
    _handle_crypto_wallet,
    _msg_help,
    _msg_unknown,
)
from app.core.routers.receive import (
    _handle_receive_start,
    _handle_receive_bp,
    _handle_receive_usdt,
    _handle_receive_usdc,
    _handle_receive_amount,
)

logger = get_logger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────────────

INACTIVITY_SECONDS = 8 * 60   # 8 minutos sin actividad → reauth

_NON_CANCELLABLE = (
    ConversationState.AWAITING_NAME,
    ConversationState.AWAITING_CEDULA,
    ConversationState.AWAITING_BIRTH_DATE,
    ConversationState.AWAITING_DACTILAR,
    ConversationState.AWAITING_EMAIL,
    ConversationState.AWAITING_CUSTODY_MODE,
    ConversationState.AWAITING_REAUTH_CEDULA,
    ConversationState.AWAITING_REAUTH_PIN,
)


# ─── Dispatcher principal ─────────────────────────────────────────────────────

async def route(phone: str, text: str, parsed: ParsedIntent) -> str:
    """
    Enruta el mensaje al handler correcto según:
    1. Re-autenticación pendiente
    2. Cancelación universal
    3. Timeout por inactividad
    4. Usuario nuevo (registro)
    5. Estado activo de sesión (flujos multi-step)
    6. Intención detectada (comandos directos)
    """
    from app.modules.auth.register import get_user_by_phone

    session = await session_manager.get(phone)
    state   = session.get("state", ConversationState.IDLE)

    # ── 1. Re-autenticación ────────────────────────────────────────────────────
    if state == ConversationState.AWAITING_REAUTH_CEDULA:
        return await _handle_reauth_cedula(phone, text, session)
    if state == ConversationState.AWAITING_REAUTH_PIN:
        return await _handle_reauth_pin(phone, text, session)

    # ── 2. Cancelación universal ───────────────────────────────────────────────
    if parsed.intent == Intent.CANCEL and state not in _NON_CANCELLABLE:
        await session_manager.set_state(phone, ConversationState.AUTHENTICATED)
        return (
            "✅ *Operación cancelada.*\n\n"
            "¿En qué más te puedo ayudar? Escribe *menú* para ver las opciones."
        )

    # ── 3. Timeout por inactividad ─────────────────────────────────────────────
    last_activity = session.get("last_activity", 0)
    if (
        state == ConversationState.AUTHENTICATED
        and last_activity > 0
        and (_time.time() - last_activity) > INACTIVITY_SECONDS
    ):
        await session_manager.set_state(phone, ConversationState.AWAITING_REAUTH_CEDULA)
        return (
            "🔒 *Sesión cerrada por inactividad.*\n\n"
            "Para continuar, verifica tu identidad.\n\n"
            "Ingresa los *últimos 4 dígitos* de tu cédula:"
        )

    # ── 4. Usuario nuevo ───────────────────────────────────────────────────────
    is_in_registration = state in REGISTRATION_STATES
    if (state == ConversationState.IDLE or not state) and not is_in_registration:
        existing_user = await get_user_by_phone(phone)
        if not existing_user:
            # Antes de arrancar registro, verificar si el intent es recuperar cuenta
            if parsed.intent == Intent.RECOVERY:
                return await handle_recovery_start(phone)

            await session_manager.set_state(phone, ConversationState.AWAITING_NAME)
            return (
                "¡Hola! 🍌 Soy *BananaPay*, tu billetera digital por WhatsApp.\n\n"
                "Envía y recibe plata, retira a tu banco — todo sin salir de WhatsApp.\n\n"
                "Para empezar necesito tu nombre completo.\n"
                "Escribe tus *dos nombres y dos apellidos*:\n"
                "Ejemplo: _Juan Carlos Pérez López_\n\n"
                "_¿Ya tienes cuenta y cambiaste de número? Escribe *recuperar cuenta*._"
            )
        await session_manager.set_state(phone, ConversationState.AWAITING_REAUTH_CEDULA)
        return (
            "🔒 *Bienvenido de vuelta a BananaPay.*\n\n"
            "Ingresa los *últimos 4 dígitos* de tu cédula para continuar:"
        )

    # ── 5. Flujos multi-step ───────────────────────────────────────────────────
    if state in REGISTRATION_STATES:
        if hint := _check_confusion(state, text):
            return hint

    # Registro
    if state == ConversationState.AWAITING_NAME:           return await _handle_registration_name(phone, text, session)
    if state == ConversationState.AWAITING_CEDULA:         return await _handle_registration_cedula(phone, text, session)
    if state == ConversationState.AWAITING_BIRTH_DATE:     return await _handle_registration_birth_date(phone, text, session)
    if state == ConversationState.AWAITING_DACTILAR:       return await _handle_registration_dactilar(phone, text, session)
    if state == ConversationState.AWAITING_EMAIL:          return await _handle_registration_email(phone, text, session)
    if state == ConversationState.AWAITING_PIN_SET:        return await _handle_pin_set(phone, text, session)
    if state == ConversationState.AWAITING_PIN_CONFIRM:    return await _handle_pin_confirm(phone, text, session)
    if state == ConversationState.AWAITING_CUSTODY_MODE:   return await _handle_custody_mode(phone, text, session)

    # Transferencias
    if state == ConversationState.AWAITING_TRANSFER_AMOUNT:             return await _handle_transfer_amount(phone, text, session)
    if state == ConversationState.AWAITING_TRANSFER_RECIPIENT_CONFIRM:  return await _handle_transfer_recipient_confirm(phone, text, session)
    if state == ConversationState.AWAITING_TRANSFER_PIN:                return await _handle_transfer_pin(phone, text, session)
    if state == ConversationState.AWAITING_TRANSFER_CONFIRM:            return await _handle_transfer_confirm(phone, text, session)

    # Recuperación de cuenta
    if state == ConversationState.AWAITING_RECOVERY_CEDULA:    return await handle_recovery_cedula(phone, text, session)
    if state == ConversationState.AWAITING_RECOVERY_BIRTHDATE: return await handle_recovery_birthdate(phone, text, session)
    if state == ConversationState.AWAITING_RECOVERY_PIN:       return await handle_recovery_pin(phone, text, session)

    # Retiro USDT
    if state == ConversationState.AWAITING_USDT_WITHDRAW_AMOUNT:  return await _handle_usdt_withdraw_amount(phone, text, session)
    if state == ConversationState.AWAITING_USDT_WITHDRAW_ADDRESS: return await _handle_usdt_withdraw_address(phone, text, session)
    if state == ConversationState.AWAITING_USDT_WITHDRAW_PIN:     return await _handle_usdt_withdraw_pin(phone, text, session)

    # Cobro QR — monto
    if state == ConversationState.AWAITING_RECEIVE_AMOUNT: return await _handle_receive_amount(phone, text, session)

    # Depósito
    if state == ConversationState.AWAITING_DEPOSIT_AMOUNT: return await _handle_deposit_amount(phone, text, session)
    # AWAITING_DEPOSIT_VOUCHER → manejado en webhook.py (mensaje de imagen)

    # Retiro fiat
    if state == ConversationState.AWAITING_WITHDRAW_AMOUNT:           return await _handle_withdraw_amount_input(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_TYPE:             return await _handle_withdraw_type(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_BANK:             return await _handle_withdraw_bank(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_ACCOUNT_TYPE:     return await _handle_withdraw_account_type(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_ACCOUNT_NUMBER:         return await _handle_withdraw_account_number(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_ACCOUNT_NUMBER_CONFIRM: return await _handle_withdraw_account_number_confirm(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_ACCOUNT_HOLDER:   return await _handle_withdraw_account_holder(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_OWN_OR_THIRD:     return await _handle_withdraw_own_or_third(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_RECIPIENT_CEDULA: return await _handle_withdraw_recipient_cedula(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_RECIPIENT_PHONE:  return await _handle_withdraw_recipient_phone(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_PIN:              return await _handle_withdraw_pin(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_ACCOUNT:          return await _handle_withdraw_account(phone, text, session)
    if state == ConversationState.AWAITING_WITHDRAW_CONFIRM:          return await _handle_withdraw_confirm(phone, text, session)

    # ── Acciones de botones especiales ────────────────────────────────────────
    if text == "__logout__":
        await session_manager.set_state(phone, ConversationState.AWAITING_REAUTH_CEDULA)
        return (
            "🔒 *Sesión cerrada.*\n\n"
            "Para volver a entrar, ingresa los *últimos 4 dígitos* de tu cédula:"
        )

    # Selector de moneda al enviar — botones post "¿En qué moneda?"
    if text in ("__send_usd__", "__send_usdt__", "__send_usdc__"):
        _currency_map = {"__send_usd__": "USD", "__send_usdt__": "USDT", "__send_usdc__": "USDC"}
        _icons        = {"USD": "💵", "USDT": "🪙", "USDC": "🔵"}
        _cur = _currency_map[text]
        await session_manager.set_state(
            phone,
            ConversationState.AWAITING_TRANSFER_AMOUNT,
            context={"awaiting_field": "phone", "transfer_currency": _cur},
        )
        return f"{_icons[_cur]} *Enviar {_cur}*\n\n¿A qué número quieres enviar?\n\nEscríbelo así: *0991234567*"

    if text == "__deposit_bank__":  return await _handle_deposit_bank(phone)
    if text == "__deposit_usdt__":  return await _handle_deposit_usdt(phone)
    if text == "__withdraw_fiat__": return await _handle_withdraw_fiat_start(phone)
    if text == "__withdraw_usdt__": return await _handle_usdt_withdraw_start(phone)
    if text == "__receive_bp__":    return await _handle_receive_bp(phone)
    if text == "__receive_usdt__":  return await _handle_receive_usdt(phone)
    if text == "__receive_usdc__":  return await _handle_receive_usdc(phone)

    # ── Cobrar — fallback directo por texto (por si el intent falla) ──────────
    _RECEIVE_WORDS = {"cobrar", "cobro", "recibir", "generar qr", "mi qr", "qr de cobro", "qr pago"}
    if text.lower().strip() in _RECEIVE_WORDS or parsed.intent == Intent.RECEIVE:
        return await _handle_receive_start(phone, parsed)

    if text == "__menu_more__":
        from app.integrations.whatsapp.messages import BotMessage, MAIN_MENU_SECTIONS
        from app.modules.auth.register import get_user_by_phone
        from app.modules.fiat.wallet import get_balances

        user = await get_user_by_phone(phone)
        if user:
            bal  = await get_balances(user["id"])
            fiat, usdt, usdc = bal["fiat"], bal["usdt"], bal["usdc"]
            if usdt > 0 or usdc > 0:
                lines = [f"🏦 USD:  *${fiat:.2f}*"]
                if usdt > 0:
                    lines.append(f"🪙 USDT: *{usdt:.2f}*")
                if usdc > 0:
                    lines.append(f"🔵 USDC: *{usdc:.2f}*")
                saldo_txt = "\n".join(lines)
            else:
                saldo_txt = f"Saldo actual: *${fiat:.2f} USD*"
            menu_text = f"🍌 *BananaPay — Menú*\n{saldo_txt}"
        else:
            menu_text = "🍌 *BananaPay — Menú*"

        return BotMessage(text=menu_text, sections=MAIN_MENU_SECTIONS)

    # ── 6. Intenciones directas ────────────────────────────────────────────────
    match parsed.intent:
        case Intent.GREETING:     return await _handle_greeting(phone)
        case Intent.HELP:         return _msg_help()
        case Intent.SUPPORT:      return await _handle_support(phone)
        case Intent.BALANCE:      return await _handle_balance(phone)
        case Intent.HISTORY:      return await _handle_history(phone)
        case Intent.TRANSFER:     return await _handle_transfer_start(phone, parsed)
        case Intent.DEPOSIT:      return await _handle_deposit_start(phone)
        case Intent.WITHDRAW:     return await _handle_withdraw_start(phone, parsed)
        case Intent.WITHDRAW_USDT: return await _handle_usdt_withdraw_start(phone)
        case Intent.CRYPTO_PRICE: return await _handle_crypto_price(parsed.currency)
        case Intent.CRYPTO_BUY:   return await _handle_crypto_buy(phone, parsed)
        case Intent.CRYPTO_WALLET: return await _handle_crypto_wallet(phone, parsed.currency)
        case Intent.PIN_SETUP:    return await _handle_pin_setup_start(phone)
        case Intent.RECOVERY:     return await handle_recovery_start(phone)
        case Intent.CANCEL:       return "✅ No hay ninguna operación activa. ¿En qué te puedo ayudar?"
        case _:                   return _msg_unknown()
