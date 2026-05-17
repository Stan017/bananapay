"""
Fixtures compartidas para integration tests.
Usa mocks de Supabase — nunca toca la BD real.
"""

import datetime
import pytest
import jwt
from unittest.mock import MagicMock
from httpx import ASGITransport, AsyncClient

from main import app
from app.config import settings
from app.core.security import hash_pin

# ─── Usuario de prueba ────────────────────────────────────────────────────────

TEST_USER_ID  = "550e8400-e29b-41d4-a716-446655440000"
TEST_PIN      = "391047"   # PIN de prueba — fuerte, no usa el PIN real de producción
TEST_PIN_HASH = hash_pin(TEST_PIN)

TEST_USER = {
    "id":             TEST_USER_ID,
    "name":           "Stanley Bolivar Llaguno Caicedo",
    "phone":          "+593997097262",
    "cedula":         "0928732494",
    "pin_hash":       TEST_PIN_HASH,
    "is_active":      True,
    "email":          "stanley@test.com",
    "kyc_level":      1,
    "custody_mode":   "custodial",
    "wallet_address": "TTestWalletAddress123456789",
    "created_at":     "2024-01-01T00:00:00",
    "push_token":     None,
}

# ─── JWT de prueba ────────────────────────────────────────────────────────────

def make_test_token(user_id: str = TEST_USER_ID) -> str:
    """Genera un JWT válido firmado con el secret_key real."""
    payload = {
        "sub":   user_id,
        "phone": TEST_USER["phone"],
        "exp":   datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

# ─── Mock de Supabase ─────────────────────────────────────────────────────────

def make_supabase_mock(data: list | dict | None = None) -> MagicMock:
    """
    Crea un mock de Supabase que responde cualquier cadena fluida:
    .table().select().eq().limit().execute()
    """
    result = MagicMock()
    result.data = data if data is not None else []

    db = MagicMock()
    # Cada método de la cadena retorna el mismo mock que al final tiene .execute()
    chain = MagicMock()
    chain.select.return_value  = chain
    chain.eq.return_value      = chain
    chain.limit.return_value   = chain
    chain.single.return_value  = chain
    chain.order.return_value   = chain
    chain.in_.return_value     = chain
    chain.or_.return_value     = chain
    chain.update.return_value  = chain
    chain.insert.return_value  = chain
    chain.execute.return_value = result

    db.table.return_value = chain
    return db

# ─── Cliente HTTP de prueba ───────────────────────────────────────────────────

@pytest.fixture
async def client():
    """Cliente HTTP que habla directamente con la app FastAPI (sin red real)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

@pytest.fixture
def auth_headers() -> dict:
    """Headers de autorización con JWT válido."""
    token = make_test_token()
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def expired_token() -> str:
    """JWT expirado para testear que el endpoint rechaza sesiones vencidas."""
    payload = {
        "sub":   TEST_USER_ID,
        "phone": TEST_USER["phone"],
        "exp":   datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")
