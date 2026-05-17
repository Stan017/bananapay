"""Cliente Supabase singleton. Usa service_role key — bypasa RLS para operaciones backend."""

from supabase import Client, create_client

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        if not settings.supabase_url or not settings.supabase_service_key:
            raise RuntimeError("Supabase no configurado — revisa SUPABASE_URL y SUPABASE_SERVICE_KEY en .env")
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
        logger.info("Supabase conectado: %s", settings.supabase_url)
    return _client
