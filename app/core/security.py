"""Seguridad: hashing de PINs, validación de firma HMAC del webhook."""

import hashlib
import hmac

import bcrypt

from app.config import settings


def hash_pin(pin: str) -> str:
    """Hashea un PIN de 6 dígitos con bcrypt. NUNCA almacenar en texto plano."""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Verifica un PIN contra su hash bcrypt."""
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def verify_whatsapp_signature(body: bytes, signature_header: str) -> bool:
    """
    Valida la firma HMAC-SHA256 del webhook de Meta Cloud API.
    Usa el App Secret (whatsapp_app_secret), no el access token.
    https://developers.facebook.com/docs/messenger-platform/webhooks#validate-payloads

    Sin WHATSAPP_APP_SECRET configurado:
      - Producción → rechaza siempre (puerta cerrada por defecto)
      - Desarrollo  → permite con warning (no rompe el flujo local)
    """
    import logging
    _log = logging.getLogger(__name__)

    if not settings.whatsapp_app_secret:
        if settings.is_production:
            _log.error(
                "WHATSAPP_APP_SECRET no configurado en producción — "
                "webhook rechazado. Agrega la variable de entorno."
            )
            return False
        _log.warning("WHATSAPP_APP_SECRET no configurado — firma no verificada (solo desarrollo)")
        return True

    expected = hmac.new(
        settings.whatsapp_app_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
