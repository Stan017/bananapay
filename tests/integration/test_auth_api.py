"""
Integration tests del endpoint /app/auth/login.
Mockea Supabase — nunca toca la BD real.
"""

import pytest
from unittest.mock import patch
from tests.integration.conftest import TEST_USER, TEST_PIN, make_supabase_mock


LOGIN_URL = "/app/auth/login"


@pytest.fixture
def mock_db_with_user():
    """Supabase mock que retorna TEST_USER al buscar por teléfono."""
    db = make_supabase_mock(data=[TEST_USER])
    with patch("app.api.app.auth.get_supabase", return_value=db):
        yield db

@pytest.fixture
def mock_db_empty():
    """Supabase mock que retorna lista vacía (usuario no existe)."""
    db = make_supabase_mock(data=[])
    with patch("app.api.app.auth.get_supabase", return_value=db):
        yield db


class TestLoginExitoso:
    async def test_login_retorna_token(self, client, mock_db_with_user):
        resp = await client.post(LOGIN_URL, json={
            "cedula": TEST_USER["cedula"],
            "phone":  "0997097262",
            "pin":    TEST_PIN,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token"   in data
        assert "user_id" in data
        assert "name"    in data
        assert "phone"   in data

    async def test_login_retorna_nombre_correcto(self, client, mock_db_with_user):
        resp = await client.post(LOGIN_URL, json={
            "cedula": TEST_USER["cedula"],
            "phone":  "0997097262",
            "pin":    TEST_PIN,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == TEST_USER["name"]

    async def test_login_acepta_telefono_con_prefijo(self, client, mock_db_with_user):
        """Debe aceptar tanto 09... como +593..."""
        resp = await client.post(LOGIN_URL, json={
            "cedula": TEST_USER["cedula"],
            "phone":  "+593997097262",
            "pin":    TEST_PIN,
        })
        assert resp.status_code == 200

    async def test_token_es_string_no_vacio(self, client, mock_db_with_user):
        resp = await client.post(LOGIN_URL, json={
            "cedula": TEST_USER["cedula"],
            "phone":  "0997097262",
            "pin":    TEST_PIN,
        })
        token = resp.json()["token"]
        assert isinstance(token, str)
        assert len(token) > 20


class TestLoginFallido:
    async def test_usuario_no_existe_retorna_401(self, client, mock_db_empty):
        resp = await client.post(LOGIN_URL, json={
            "cedula": "0000000000",
            "phone":  "0999999999",
            "pin":    TEST_PIN,
        })
        assert resp.status_code == 401

    async def test_pin_incorrecto_retorna_401(self, client, mock_db_with_user):
        resp = await client.post(LOGIN_URL, json={
            "cedula": TEST_USER["cedula"],
            "phone":  "0997097262",
            "pin":    "000000",   # PIN incorrecto
        })
        assert resp.status_code == 401

    async def test_cedula_incorrecta_retorna_401(self, client, mock_db_with_user):
        resp = await client.post(LOGIN_URL, json={
            "cedula": "1111111111",   # cédula incorrecta
            "phone":  "0997097262",
            "pin":    TEST_PIN,
        })
        assert resp.status_code == 401

    async def test_sin_body_retorna_422(self, client):
        resp = await client.post(LOGIN_URL, json={})
        assert resp.status_code == 422

    async def test_pin_vacio_retorna_error(self, client, mock_db_with_user):
        resp = await client.post(LOGIN_URL, json={
            "cedula": TEST_USER["cedula"],
            "phone":  "0997097262",
            "pin":    "",
        })
        assert resp.status_code in (401, 422)

    async def test_respuesta_no_expone_pin_hash(self, client, mock_db_with_user):
        """CRÍTICO: la respuesta nunca debe contener el pin_hash."""
        resp = await client.post(LOGIN_URL, json={
            "cedula": TEST_USER["cedula"],
            "phone":  "0997097262",
            "pin":    TEST_PIN,
        })
        response_text = resp.text
        assert "pin_hash" not in response_text
        assert "$2b$"     not in response_text
