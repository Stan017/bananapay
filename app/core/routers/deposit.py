"""
Handlers de depósitos: fiat bancario y USDT TRC-20.
"""

from app.core.session import ConversationState, session_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _handle_deposit_start(phone: str) -> str:
    """Ofrece dos métodos de depósito: banco o USDT."""
    from app.integrations.whatsapp.messages import BotMessage, Btn
    from app.modules.auth.register import get_user_by_phone

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    return BotMessage(
        text="📥 *Cargar saldo*\n\nElige cómo quieres depositar:",
        buttons=[
            Btn("btn_deposit_bank", "🏦 Transferencia bancaria"),
            Btn("btn_deposit_usdt", "🪙 Depositar USDT"),
        ],
    )


async def _handle_deposit_bank(phone: str) -> str:
    """Flujo de depósito fiat — muestra datos de la cuenta y pide monto."""
    from app.config import settings

    bank    = settings.bananapay_bank_name      or "_(próximamente)_"
    account = settings.bananapay_account_number or "_(próximamente)_"
    holder  = settings.bananapay_account_holder or "BananaPay"
    actype  = settings.bananapay_account_type   or "Ahorros"

    await session_manager.set_state(phone, ConversationState.AWAITING_DEPOSIT_AMOUNT)
    return (
        "📥 *Depósito bancario — paso a paso:*\n\n"
        "1️⃣ Abre tu app bancaria\n"
        "2️⃣ Transfiere a esta cuenta:\n\n"
        f"   🏦 Banco: *{bank}*\n"
        f"   💳 Tipo: *{actype}*\n"
        f"   🔢 Cuenta: *{account}*\n"
        f"   👤 A nombre de: *{holder}*\n\n"
        "3️⃣ Guarda el comprobante\n\n"
        "¿Cuánto vas a depositar? (ej: *50* o *$50*)"
    )


async def _handle_deposit_usdt(phone: str) -> str:
    """Muestra la dirección TRC-20 del usuario para recibir USDT."""
    from app.modules.auth.register import get_user_by_phone
    from app.modules.crypto.wallet_manager import assign_wallet_to_user

    user = await get_user_by_phone(phone)
    if not user:
        return "No encontré tu cuenta. Escribe *hola* para registrarte."

    wallet  = await assign_wallet_to_user(user["id"])
    address = wallet["address"]

    return (
        "🪙 *Depositar USDT / USDC (TRC-20)*\n\n"
        "Envía USDT o USDC a tu dirección personal BananaPay:\n\n"
        f"`{address}`\n\n"
        "⚡ El saldo se acredita *automáticamente* al detectar la transacción.\n\n"
        "✅ *Tokens aceptados:* USDT y USDC\n"
        "⚠️ *Solo red TRC-20* — otras redes (ERC-20, BEP-20, etc.) "
        "pueden perderse permanentemente.\n\n"
        "_¿Necesitas ayuda? Escribe *soporte*_"
    )


async def _handle_deposit_amount(phone: str, text: str, session: dict) -> str:
    """Recibe el monto declarado y pide el comprobante."""
    from decimal import Decimal
    from app.utils.currency import parse_amount

    amount = parse_amount(text)
    if not amount or amount < Decimal("1.00"):
        return "Monto inválido. Escribe el monto que vas a depositar, ej: *50*"

    await session_manager.set_state(
        phone,
        ConversationState.AWAITING_DEPOSIT_VOUCHER,
        context={"deposit_amount": str(amount)},
    )
    return (
        f"✅ Monto: *${amount:.2f}*\n\n"
        "Ahora *envía la foto del comprobante* de la transferencia 📸\n\n"
        "_(La imagen que te da tu banco al hacer la transferencia)_"
    )


async def handle_deposit_voucher(phone: str, media_id: str) -> str:
    """
    Llamado desde webhook.py cuando llega una imagen en AWAITING_DEPOSIT_VOUCHER.

    Pipeline:
      1. Descarga imagen de WhatsApp
      2. Guarda en disco (si MEDIA_STORAGE_PATH configurado)
      3. SHA-256 → detecta duplicados
      4. Claude Vision analiza el comprobante
      5. Anti-fraude
      6. Crea depósito y notifica al admin
    """
    from decimal import Decimal
    from app.config import settings
    from app.modules.auth.register import get_user_by_phone
    from app.modules.fiat.deposits import create_deposit
    from app.modules.fiat.fraud import check_deposit_fraud, check_deposit_velocity, check_blacklist
    from app.modules.ai.vision import analyze_voucher
    from app.integrations.whatsapp.client import fetch_media_bytes, send_message
    from app.utils.media_storage import save_voucher, check_duplicate_hash

    user = await get_user_by_phone(phone)
    if not user:
        await session_manager.clear(phone)
        return "No encontré tu cuenta."

    session = await session_manager.get(phone)
    ctx     = session.get("context", {})
    amount  = Decimal(ctx.get("deposit_amount", "0"))

    if amount <= 0:
        await session_manager.clear(phone)
        return "Algo salió mal. Escribe *depositar* para intentar de nuevo."

    # ── Blacklist ─────────────────────────────────────────────────────────────
    bl = check_blacklist(phone=user.get("phone"), cedula=user.get("cedula"))
    if bl.blocked:
        await session_manager.clear(phone)
        return "❌ Tu cuenta tiene una restricción activa. Escribe *soporte* para más información."

    # ── Velocity check ────────────────────────────────────────────────────────
    vel = check_deposit_velocity(user)
    if vel.blocked:
        await session_manager.clear(phone)
        return (
            "⏳ *Demasiados intentos en poco tiempo.*\n\n"
            "Por seguridad, espera un momento antes de enviar otro depósito."
        )

    # ── 1. Descargar imagen ───────────────────────────────────────────────────
    try:
        image_bytes, mime_type = await fetch_media_bytes(media_id)
    except Exception as exc:
        logger.error("handle_deposit_voucher: no se pudo descargar imagen — %s", exc)
        image_bytes, mime_type = None, "image/jpeg"

    # ── 2. Guardar + calcular hash ────────────────────────────────────────────
    voucher_local_path: str | None = None
    voucher_hash:       str | None = None

    if image_bytes:
        local_path, file_hash = save_voucher(
            data=image_bytes,
            mime_type=mime_type,
            deposit_id=phone.replace("+", ""),
        )
        voucher_local_path = local_path
        voucher_hash       = file_hash

    # ── 3. Detectar duplicado ─────────────────────────────────────────────────
    if voucher_hash:
        prev_id = check_duplicate_hash(voucher_hash)
        if prev_id:
            await session_manager.clear(phone)
            logger.warning("Comprobante duplicado: phone=%s prev=%s", phone, prev_id)
            return (
                "❌ *Este comprobante ya fue utilizado.*\n\n"
                "Detectamos que esta imagen fue enviada anteriormente. "
                "Si tienes un comprobante diferente, escríbenos a *soporte*."
            )

    # ── 4. Claude Vision ──────────────────────────────────────────────────────
    vision = None
    if image_bytes:
        try:
            vision = analyze_voucher(
                image_bytes=image_bytes,
                mime_type=mime_type,
                declared_amount=amount,
            )
        except Exception as exc:
            logger.error("handle_deposit_voucher: error en Vision — %s", exc)

    if vision and vision.is_rejected:
        await session_manager.clear(phone)
        logger.warning(
            "Depósito bloqueado por Vision: phone=%s reason=%s confidence=%.2f",
            phone, vision.reason, vision.confidence,
        )
        return (
            "❌ *No pudimos verificar tu comprobante.*\n\n"
            "La imagen no corresponde a un comprobante de transferencia válido. "
            "Asegúrate de enviar la captura correcta.\n\n"
            "Si crees que es un error, escribe *soporte*."
        )

    # ── 5. Anti-fraude ────────────────────────────────────────────────────────
    fraud = check_deposit_fraud(user=user, amount=amount, voucher_media_id=media_id)
    if fraud.blocked:
        await session_manager.clear(phone)
        logger.warning("Depósito bloqueado por fraude: phone=%s reason=%s", phone, fraud.reason)
        return (
            "❌ *No pudimos procesar tu depósito.*\n\n"
            "Si crees que es un error, escribe *soporte* para contactar a un agente."
        )

    # ── 6. Crear depósito ─────────────────────────────────────────────────────
    deposit = await create_deposit(
        user_id=user["id"],
        amount=amount,
        voucher_media_id=media_id,
        voucher_hash=voucher_hash,
        voucher_local_path=voucher_local_path,
        vision_verdict=vision.verdict if vision else None,
        vision_confidence=vision.confidence if vision else None,
        vision_reason=vision.reason[:500] if vision else None,
    )

    await session_manager.clear(phone)

    # ── 7. Notificar al admin ─────────────────────────────────────────────────
    if settings.admin_whatsapp:
        vision_line = ""
        if vision:
            icons = {"approved": "✅", "rejected": "❌", "review_needed": "⚠️"}
            icon  = icons.get(vision.verdict, "🔍")
            vision_line = (
                f"\n{icon} *Vision:* {vision.verdict} ({vision.confidence*100:.0f}%)"
                f"\n💬 _{vision.reason[:100]}_"
            )
        from app.integrations.whatsapp.client import send_message
        await send_message(
            settings.admin_whatsapp,
            f"📥 *Nuevo depósito pendiente*\n\n"
            f"👤 {user['name']} ({user['phone']})\n"
            f"💰 *${amount:.2f} USD*\n"
            f"🆔 ID: `{deposit['id']}`"
            f"{vision_line}\n\n"
            f"Verifica en tu cuenta bancaria y aprueba en el panel.",
        )

    if vision and vision.is_approved:
        extra = "\n_✅ Comprobante verificado automáticamente._"
    elif vision and vision.needs_review:
        extra = "\n_🔍 En revisión manual por nuestro equipo._"
    else:
        extra = ""

    return (
        f"✅ *¡Comprobante recibido!*\n\n"
        f"💰 Monto declarado: *${amount:.2f} USD*\n"
        f"{extra}\n"
        "Estamos verificando tu depósito. En cuanto lo confirmemos "
        "te avisamos aquí y el saldo aparecerá en tu cuenta. 🍌\n\n"
        "_Tiempo de revisión: máx 30 minutos en horario laboral_"
    )
