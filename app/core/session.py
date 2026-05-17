"""Manejo de sesiones de conversación por número de teléfono.

En desarrollo usa memoria en proceso. En producción usa Redis (Upstash).
"""

import time
from enum import Enum

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

SESSION_TTL = 60 * 30  # 30 minutos


class ConversationState(str, Enum):
    IDLE = "idle"
    AUTHENTICATED = "authenticated"       # sesión activa y verificada
    # Re-autenticación por inactividad
    AWAITING_REAUTH_CEDULA = "awaiting_reauth_cedula"
    AWAITING_REAUTH_PIN = "awaiting_reauth_pin"
    # Registro
    AWAITING_NAME = "awaiting_name"
    AWAITING_CEDULA = "awaiting_cedula"
    AWAITING_BIRTH_DATE = "awaiting_birth_date"
    AWAITING_DACTILAR = "awaiting_dactilar"
    AWAITING_EMAIL = "awaiting_email"
    AWAITING_PIN_SET = "awaiting_pin_set"
    AWAITING_PIN_CONFIRM = "awaiting_pin_confirm"
    AWAITING_CUSTODY_MODE = "awaiting_custody_mode"
    # Transferencias
    AWAITING_TRANSFER_AMOUNT = "awaiting_transfer_amount"
    AWAITING_TRANSFER_PIN = "awaiting_transfer_pin"
    AWAITING_TRANSFER_CONFIRM = "awaiting_transfer_confirm"
    # Depósito
    AWAITING_DEPOSIT_AMOUNT  = "awaiting_deposit_amount"
    AWAITING_DEPOSIT_VOUCHER = "awaiting_deposit_voucher"
    # Retiro USDT on-chain
    AWAITING_USDT_WITHDRAW_AMOUNT  = "awaiting_usdt_withdraw_amount"
    AWAITING_USDT_WITHDRAW_ADDRESS = "awaiting_usdt_withdraw_address"
    AWAITING_USDT_WITHDRAW_PIN     = "awaiting_usdt_withdraw_pin"
    # Retiro fiat
    AWAITING_WITHDRAW_AMOUNT = "awaiting_withdraw_amount"
    AWAITING_WITHDRAW_TYPE   = "awaiting_withdraw_type"
    AWAITING_WITHDRAW_BANK   = "awaiting_withdraw_bank"
    AWAITING_WITHDRAW_ACCOUNT_TYPE   = "awaiting_withdraw_account_type"
    AWAITING_WITHDRAW_ACCOUNT_NUMBER = "awaiting_withdraw_account_number"
    AWAITING_WITHDRAW_ACCOUNT_HOLDER = "awaiting_withdraw_account_holder"
    AWAITING_WITHDRAW_PIN    = "awaiting_withdraw_pin"
    AWAITING_WITHDRAW_ACCOUNT = "awaiting_withdraw_account"
    AWAITING_WITHDRAW_CONFIRM = "awaiting_withdraw_confirm"
    AWAITING_WITHDRAW_OWN_OR_THIRD   = "awaiting_withdraw_own_or_third"
    AWAITING_WITHDRAW_RECIPIENT_CEDULA = "awaiting_withdraw_recipient_cedula"
    AWAITING_WITHDRAW_RECIPIENT_PHONE  = "awaiting_withdraw_recipient_phone"
    # Cobro con QR
    AWAITING_RECEIVE_AMOUNT = "awaiting_receive_amount"


class SessionManager:
    def __init__(self) -> None:
        # {phone: {"data": dict, "expires_at": float}}
        self._store: dict[str, dict] = {}
        self._redis = None

    def _use_redis(self) -> bool:
        url = settings.redis_url
        return url and url.startswith(("redis://", "rediss://", "unix://"))

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _key(self, phone: str) -> str:
        return f"bp:session:{phone}"

    async def get(self, phone: str) -> dict:
        if self._use_redis():
            import json
            r = await self._get_redis()
            data = await r.get(self._key(phone))
            return json.loads(data) if data else {}

        entry = self._store.get(phone)
        if not entry or entry["expires_at"] < time.time():
            return {}
        return dict(entry["data"])

    async def set_state(
        self,
        phone: str,
        state: ConversationState,
        context: dict | None = None,
    ) -> None:
        existing = await self.get(phone)
        existing["state"] = state.value
        existing["last_activity"] = time.time()
        if context:
            existing.setdefault("context", {}).update(context)

        if self._use_redis():
            import json
            r = await self._get_redis()
            await r.setex(self._key(phone), SESSION_TTL, json.dumps(existing))
        else:
            self._store[phone] = {
                "data": existing,
                "expires_at": time.time() + SESSION_TTL,
            }

    async def clear(self, phone: str) -> None:
        if self._use_redis():
            r = await self._get_redis()
            await r.delete(self._key(phone))
        else:
            self._store.pop(phone, None)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()


session_manager = SessionManager()
