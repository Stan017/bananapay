"""
Integration tests de /app/me/* — balance, perfil, historial.
Todos los endpoints requieren JWT válido.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from tests.integration.conftest import TEST_USER, TEST_USER_ID, make_supabase_mock


class TestBalance:
    async def test_balance_retorna_200_con_token_valido(self, client, auth_headers):
        balances_mock = {
            "fiat":  Decimal("100.00"),
            "usdt":  Decimal("50.00"),
            "usdc":  Decimal("25.00"),
            "total": Decimal("175.00"),
        }
        with patch("app.api.app.me.get_balances", new=AsyncMock(return_value=balances_mock)):
            resp = await client.get("/app/me/balance", headers=auth_headers)
        assert resp.status_code == 200

    async def test_balance_retorna_campos_correctos(self, client, auth_headers):
        balances_mock = {
            "fiat":  Decimal("100.00"),
            "usdt":  Decimal("0.00"),
            "usdc":  Decimal("0.00"),
            "total": Decimal("100.00"),
        }
        with patch("app.api.app.me.get_balances", new=AsyncMock(return_value=balances_mock)):
            resp = await client.get("/app/me/balance", headers=auth_headers)
        data = resp.json()
        assert "fiat"  in data
        assert "usdt"  in data
        assert "usdc"  in data
        assert "total" in data

    async def test_balance_total_es_suma_de_partes(self, client, auth_headers):
        balances_mock = {
            "fiat":  Decimal("30.00"),
            "usdt":  Decimal("85.50"),
            "usdc":  Decimal("50.00"),
            "total": Decimal("165.50"),
        }
        with patch("app.api.app.me.get_balances", new=AsyncMock(return_value=balances_mock)):
            resp = await client.get("/app/me/balance", headers=auth_headers)
        data = resp.json()
        assert data["total"] == pytest.approx(165.50)
        assert data["fiat"]  == pytest.approx(30.00)
        assert data["usdt"]  == pytest.approx(85.50)

    async def test_balance_sin_token_retorna_403(self, client):
        resp = await client.get("/app/me/balance")
        assert resp.status_code == 403

    async def test_balance_token_invalido_retorna_401(self, client):
        resp = await client.get(
            "/app/me/balance",
            headers={"Authorization": "Bearer token.falso.aqui"},
        )
        assert resp.status_code == 401  # token presente pero inválido → 401

    async def test_balance_token_expirado_retorna_401(self, client, expired_token):
        resp = await client.get(
            "/app/me/balance",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401


class TestProfile:
    async def test_profile_retorna_datos_del_usuario(self, client, auth_headers):
        db = make_supabase_mock(data=TEST_USER)
        with patch("app.api.app.me.get_supabase", return_value=db):
            resp = await client.get("/app/me/profile", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"]   == TEST_USER["name"]
        assert data["cedula"] == TEST_USER["cedula"]
        assert data["phone"]  == TEST_USER["phone"]

    async def test_profile_no_expone_pin_hash(self, client, auth_headers):
        """CRÍTICO: el perfil nunca debe filtrar el pin_hash."""
        db = make_supabase_mock(data=TEST_USER)
        with patch("app.api.app.me.get_supabase", return_value=db):
            resp = await client.get("/app/me/profile", headers=auth_headers)
        assert "pin_hash" not in resp.text
        assert "$2b$"     not in resp.text

    async def test_profile_sin_token_retorna_403(self, client):
        resp = await client.get("/app/me/profile")
        assert resp.status_code == 403


class TestHistory:
    async def test_history_retorna_lista(self, client, auth_headers):
        txs_mock = [
            {
                "id":           "tx-001",
                "tx_type":      "transfer",
                "currency":     "USD",
                "amount":       20.00,
                "fee":          0.00,
                "to_user_id":   "otro-user-id",
                "from_user_id": TEST_USER_ID,
                "other_name":   "Olga",
                "status":       "completed",
                "created_at":   "2024-05-10T10:00:00",
            }
        ]
        with patch("app.api.app.me.get_history", new=AsyncMock(return_value=txs_mock)):
            resp = await client.get("/app/me/history", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_history_direction_out_cuando_soy_sender(self, client, auth_headers):
        txs_mock = [{
            "id":           "tx-001",
            "tx_type":      "transfer",
            "currency":     "USD",
            "amount":       20.00,
            "fee":          0.00,
            "to_user_id":   "otro-user-id",
            "from_user_id": TEST_USER_ID,   # soy el que envía
            "other_name":   "Olga",
            "status":       "completed",
            "created_at":   "2024-05-10T10:00:00",
        }]
        with patch("app.api.app.me.get_history", new=AsyncMock(return_value=txs_mock)):
            resp = await client.get("/app/me/history", headers=auth_headers)
        assert resp.json()[0]["direction"] == "out"

    async def test_history_direction_in_cuando_soy_receptor(self, client, auth_headers):
        txs_mock = [{
            "id":           "tx-002",
            "tx_type":      "transfer",
            "currency":     "USD",
            "amount":       50.00,
            "fee":          0.00,
            "to_user_id":   TEST_USER_ID,   # soy el que recibe
            "from_user_id": "otro-user-id",
            "other_name":   "Carlos",
            "status":       "completed",
            "created_at":   "2024-05-11T10:00:00",
        }]
        with patch("app.api.app.me.get_history", new=AsyncMock(return_value=txs_mock)):
            resp = await client.get("/app/me/history", headers=auth_headers)
        assert resp.json()[0]["direction"] == "in"

    async def test_history_limit_maximo_50(self, client, auth_headers):
        """No debe devolver más de 50 transacciones aunque pidan 1000."""
        with patch("app.api.app.me.get_history", new=AsyncMock(return_value=[])) as mock_hist:
            resp = await client.get("/app/me/history?limit=1000", headers=auth_headers)
        # Verificar que se llamó con limit=50, no 1000
        called_limit = mock_hist.call_args[1].get("limit") or mock_hist.call_args[0][1]
        assert called_limit <= 50

    async def test_history_sin_token_retorna_403(self, client):
        resp = await client.get("/app/me/history")
        assert resp.status_code == 403

    async def test_history_vacio_retorna_lista_vacia(self, client, auth_headers):
        with patch("app.api.app.me.get_history", new=AsyncMock(return_value=[])):
            resp = await client.get("/app/me/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestPushToken:
    async def test_push_token_se_actualiza(self, client, auth_headers):
        db = make_supabase_mock(data=[])
        with patch("app.api.app.me.get_supabase", return_value=db):
            resp = await client.patch(
                "/app/me/push-token",
                json={"token": "ExponentPushToken[test-token-123]"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    async def test_push_token_vacio_retorna_400(self, client, auth_headers):
        db = make_supabase_mock(data=[])
        with patch("app.api.app.me.get_supabase", return_value=db):
            resp = await client.patch(
                "/app/me/push-token",
                json={"token": ""},
                headers=auth_headers,
            )
        assert resp.status_code == 400
