"""Fixtures globales para pytest."""

import warnings
import pytest
from httpx import ASGITransport, AsyncClient

# Silencia el warning de urllib3/requests que se emite ANTES de que pytest
# cargue filterwarnings desde pytest.ini (ocurre al importar requests).
warnings.filterwarnings("ignore", category=Warning, module="requests")

from main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
