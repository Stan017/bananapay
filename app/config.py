"""Configuración centralizada via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    api_base_url: str = "https://api.bananapay.ec"

    # Meta / WhatsApp
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""  # App Secret para validar firma HMAC del webhook

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # Redis (Upstash en cloud)
    redis_url: str = "redis://localhost:6379"

    # Crypto custodial
    binance_api_key: str = ""
    binance_secret: str = ""
    coinbase_api_key: str = ""
    coinbase_secret: str = ""

    # Self custody — AES-256 para encriptar private keys
    wallet_encryption_key: str = ""

    # Banking Ecuador
    deuna_api_key: str = ""
    deuna_merchant_id: str = ""

    # Cuenta bancaria de BananaPay (para mostrar a usuarios al depositar)
    bananapay_bank_name: str = ""
    bananapay_account_number: str = ""
    bananapay_account_holder: str = ""
    bananapay_account_type: str = "Ahorros"

    # Número WhatsApp del admin para recibir alertas
    admin_whatsapp: str = ""

    # Almacenamiento local de medios (comprobantes de depósito, etc.)
    # Vacío = no guarda localmente (solo referencia WhatsApp, expira 30 días)
    # Local:  C:\Users\stanley\Desktop\BananaPay\media
    # NAS:    \\192.168.1.100\bananapay\media
    media_storage_path: str = ""

    # TronGrid (USDT TRC-20 listener)
    trongrid_api_key: str = ""

    # Anthropic / Claude
    anthropic_api_key: str = ""

    # Sentry
    sentry_dsn: str = ""

    # Worker — poner en True en producción cuando el listener corre como proceso separado
    # (Railway worker: python worker.py). Así el web process no duplica el listener.
    deposit_listener_worker: bool = False

    # IP whitelist para el panel admin (separadas por coma, vacío = sin restricción)
    # Ejemplo: ADMIN_IP_WHITELIST=203.0.113.10,198.51.100.5
    # En desarrollo dejar vacío. En producción poner la IP de tu oficina/VPN.
    admin_ip_whitelist: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
