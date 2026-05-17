"""
Handlers de consulta: saldo, historial, soporte y mensajes estáticos.
"""

import datetime
from collections import defaultdict

from app.core.session import ConversationState, session_manager
from app.core.routers.transfer import _short_name
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _handle_balance(phone: str):
    from app.integrations.whatsapp.messages import BotMessage, Btn
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_balances, get_history

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    balances = await get_balances(user["id"])
    fiat  = balances["fiat"]
    usdt  = balances["usdt"]
    usdc  = balances["usdc"]
    total = balances["total"]
    txs   = await get_history(user["id"], limit=3)

    has_crypto = usdt > 0 or usdc > 0
    if has_crypto:
        lines = [f"💰 *Saldo BananaPay*\n", f"🏦 Fiat:  *${fiat:.2f} USD*"]
        if usdt > 0:
            lines.append(f"🪙 USDT:  *{usdt:.2f} USDT*")
        if usdc > 0:
            lines.append(f"🔵 USDC:  *{usdc:.2f} USDC*")
        lines += ["──────────────────", f"Total:   *${total:.2f} USD*"]
    else:
        lines = [f"💰 *Saldo: ${total:.2f} USD*"]

    if txs:
        lines.append("")
        today     = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        for tx in txs:
            es_recibido = tx["to_user_id"] == user["id"]
            arrow  = "↙ Recibiste" if es_recibido else "↗ Enviaste"
            monto  = f"${float(tx['amount']):.2f}"
            other  = _short_name(tx.get("other_name", "")) if tx.get("other_name") else "BananaPay"
            preposicion = "de" if es_recibido else "a"
            try:
                created = (tx.get("created_at") or "")[:10]
                when = "hoy" if created == today else ("ayer" if created == yesterday else created[8:10] + "/" + created[5:7])
            except Exception:
                when = ""
            lines.append(f"{arrow} *{monto}* {preposicion} {other}  _{when}_")
        lines.append("\n_Para ver más, toca Menú_ 👇")

    return BotMessage(
        text="\n".join(lines),
        buttons=[
            Btn("btn_send",     "💸 Enviar"),
            Btn("btn_withdraw", "📤 Retirar"),
            Btn("btn_more",     "📋 Menú"),
        ],
    )


async def _handle_history(phone: str) -> str:
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_balances, get_history

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    txs = await get_history(user["id"], limit=10)
    if not txs:
        return "📋 *Historial*\n\nAún no tienes transacciones.\nEscribe _depositar_ para empezar. 🍌"

    balances = await get_balances(user["id"])
    fiat = balances["fiat"]
    usdt = balances["usdt"]
    usdc = balances["usdc"]

    if usdt > 0 or usdc > 0:
        header_parts = [f"📋 *Historial*\n", f"🏦 USD:  *${fiat:.2f}*"]
        if usdt > 0:
            header_parts.append(f"🪙 USDT: *{usdt:.2f}*")
        if usdc > 0:
            header_parts.append(f"🔵 USDC: *{usdc:.2f}*")
        header = "\n".join(header_parts)
    else:
        header = f"📋 *Historial — ${fiat:.2f} USD*"

    TIPO  = {"transfer": "Transferencia", "deposit": "Depósito", "withdrawal": "Retiro"}
    MESES = {
        "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
        "05": "mayo",  "06": "junio",   "07": "julio", "08": "agosto",
        "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre",
    }

    month_totals: dict[str, float] = defaultdict(float)
    for tx in txs:
        ym  = (tx.get("created_at") or "")[:7] or "?"
        amt = float(tx["amount"])
        month_totals[ym] += amt if tx["to_user_id"] == user["id"] else -amt

    lines       = [f"{header}\n"]
    seen_months: set[str] = set()
    today       = datetime.date.today().isoformat()
    yesterday   = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    for tx in txs:
        raw = tx.get("created_at") or ""
        ym  = raw[:7] if len(raw) >= 7 else "?"

        if ym not in seen_months:
            seen_months.add(ym)
            mes_label = MESES.get(ym[5:7], ym[5:7]) if len(ym) >= 7 else ym
            total     = month_totals[ym]
            signo     = "+" if total >= 0 else ""
            lines.append(f"── {mes_label.capitalize()} ({signo}${total:.2f}) ──")

        es_recibido = tx["to_user_id"] == user["id"]
        arrow       = "↙" if es_recibido else "↗"
        monto       = f"${float(tx['amount']):.2f}"
        other       = _short_name(tx.get("other_name", "")) if tx.get("other_name") else "BananaPay"
        preposicion = "de" if es_recibido else "a"
        tipo_label  = TIPO.get(tx.get("tx_type", ""), tx.get("tx_type", ""))

        try:
            if "T" in raw:
                hora  = raw[11:16]
                fecha = raw[:10]
                when  = (
                    f"hoy {hora}" if fecha == today
                    else (f"ayer {hora}" if fecha == yesterday
                    else f"{fecha[8:10]}/{fecha[5:7]} {hora}")
                )
            else:
                when = raw[:10]
        except Exception:
            when = ""

        lines.append(f"{arrow} *{monto}* {preposicion} {other} — {tipo_label}  _{when}_")

    return "\n".join(lines)


async def _handle_greeting(phone: str):
    import random
    from app.integrations.whatsapp.messages import BotMessage, Btn
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.wallet import get_balance

    user = await get_user_by_phone(phone)
    if not user:
        saludos = ["¡Hola!", "¡Hey!", "¡Buenas!"]
        return BotMessage(
            text=(
                f"{random.choice(saludos)} 🍌 Soy *BananaPay*.\n\n"
                "Envía y recibe plata, retira a tu banco — "
                "todo desde WhatsApp, sin descargar nada.\n\n"
                "¿Qué quieres hacer?"
            ),
            buttons=[
                Btn("btn_register", "🚀 Registrarme"),
                Btn("btn_how",      "❓ Cómo funciona"),
            ],
        )

    primer_nombre = user["name"].strip().split()[0]
    saludos = [
        f"¡Hola, {primer_nombre}! 👋",
        f"¡Hey, {primer_nombre}! 🍌",
        f"¡Buenas, {primer_nombre}!",
        f"¡Qué más, {primer_nombre}! 👊",
    ]
    from app.modules.fiat.wallet import get_balances
    balances = await get_balances(user["id"])
    fiat = balances["fiat"]
    usdt = balances["usdt"]
    usdc = balances["usdc"]

    if usdt > 0 or usdc > 0:
        saldo_lines = [f"🏦 USD:  *${fiat:.2f}*"]
        if usdt > 0:
            saldo_lines.append(f"🪙 USDT: *{usdt:.2f}*")
        if usdc > 0:
            saldo_lines.append(f"🔵 USDC: *{usdc:.2f}*")
        saldo_txt = "\n".join(saldo_lines)
    else:
        saldo_txt = f"💰 Saldo: *${fiat:.2f} USD*"

    return BotMessage(
        text=(
            f"{random.choice(saludos)}\n\n"
            f"{saldo_txt}\n\n"
            "¿Qué hacemos hoy?\n\n"
            "🔒 _Por tu seguridad, borra este chat regularmente._"
        ),
        buttons=[
            Btn("btn_send",     "💸 Enviar"),
            Btn("btn_withdraw", "📤 Retirar"),
            Btn("btn_more",     "📋 Menú"),
        ],
    )


async def _handle_support(phone: str) -> str:
    from app.integrations.supabase_client import get_supabase
    from app.modules.auth.register import get_user_by_phone

    user = await get_user_by_phone(phone)
    db   = get_supabase()

    payload = {"phone": phone, "status": "pending"}
    if user:
        payload["user_id"] = user["id"]
        payload["name"]    = user.get("name", "")
        payload["cedula"]  = user.get("cedula", "")

    try:
        db.table("support_requests").insert(payload).execute()
        logger.info("Soporte solicitado: phone=%s", phone)
    except Exception as exc:
        logger.warning("Error guardando support_request: %s", exc)

    name_part = f" {user['name'].split()[0]}" if user else ""
    return (
        f"✅ ¡Recibido{name_part}!\n\n"
        "Un agente de *BananaPay* te contactará pronto por este mismo chat.\n\n"
        "⏱️ Tiempo de respuesta habitual: *menos de 2 horas* en horario laboral.\n\n"
        "Si es urgente escribe: *soporte urgente*"
    )


async def _handle_crypto_price(currency: str) -> str:
    return f"Consultando precio de *{currency}*... 🔄\n_(Próximamente disponible)_"


async def _handle_crypto_buy(phone: str, parsed) -> str:
    return (
        f"Compra de *{parsed.currency}* por *USD {parsed.amount}* — próximamente disponible.\n"
        "Escribe _ayuda_ para ver opciones actuales."
    )


async def _handle_crypto_wallet(phone: str, currency: str) -> str:
    return f"Tu wallet *{currency}* — próximamente disponible."


def _msg_help() -> str:
    return (
        "🍌 *BananaPay — Guía completa*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "💰 *VER TU SALDO*\n"
        "Escribe: *saldo*\n"
        "Te digo cuánta plata tienes y tus últimos movimientos.\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "💸 *ENVIAR PLATA*\n"
        "Escribe: *enviar 10 a 0991234567*\n"
        "Cambia el número por el de la persona. Si no sabes su número, escribe *enviar* y te voy preguntando paso a paso.\n"
        "_Las transferencias entre usuarios BananaPay son GRATIS_ 🎉\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "💳 *COBRAR CON QR*\n"
        "Escribe: *cobrar*\n"
        "Te genero un código QR para que te paguen.\n"
        "• *cobrar* → eliges BananaPay, USDT o USDC\n"
        "• *cobrar 50 USDT* → QR con monto fijo\n"
        "_El QR de BananaPay funciona entre usuarios de la app._\n"
        "_El QR crypto funciona con cualquier wallet TRC-20._\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "📥 *CARGAR SALDO*\n"
        "Escribe: *depositar*\n"
        "Te explico cómo transferir desde tu banco a BananaPay.\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "📤 *RETIRAR A TU BANCO*\n"
        "Escribe: *retirar 50*\n"
        "El dinero llega a tu cuenta bancaria ecuatoriana.\n"
        "_Costo: $0.50 por retiro_\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🔐 *¿OLVIDASTE TU PIN?*\n"
        "Escribe: *cambiar PIN*\n"
        "Te ayudamos a crear uno nuevo.\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "💬 *¿NECESITAS AYUDA?*\n"
        "Escribe: *soporte*\n"
        "Un agente real te atenderá."
    )


def _msg_unknown() -> str:
    return (
        "No entendí bien eso 😅\n\n"
        "Prueba con algo como:\n"
        "• *saldo* — ver tu plata\n"
        "• *enviar 5 a María* — transferir\n"
        "• *ayuda* — ver todo lo que puedo hacer"
    )
