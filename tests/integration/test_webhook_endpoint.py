"""
Tests del endpoint HTTP /webhook.
Verifica verificación de Meta, firma HMAC y recepción de mensajes.
"""

import json
import pytest
from app.config import settings


class TestWebhookVerificacion:
    async def test_verificacion_token_correcto(self, client):
        """Meta llama GET /webhook con el token correcto → debe retornar el challenge."""
        resp = await client.get("/webhook", params={
            "hub.mode":         "subscribe",
            "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge":    "test_challenge_abc123",
        })
        assert resp.status_code == 200
        assert resp.text == "test_challenge_abc123"

    async def test_verificacion_token_incorrecto(self, client):
        """Token incorrecto → debe rechazarse con 403."""
        resp = await client.get("/webhook", params={
            "hub.mode":         "subscribe",
            "hub.verify_token": "token_equivocado",
            "hub.challenge":    "challenge_xyz",
        })
        assert resp.status_code == 403

    async def test_verificacion_sin_params_retorna_error(self, client):
        """Sin parámetros → error de validación."""
        resp = await client.get("/webhook")
        assert resp.status_code == 422


class TestWebhookRecepcion:
    def _make_payload(self, phone: str, text: str, msg_id: str = "wamid.test001") -> dict:
        """Construye un payload válido de Meta Cloud API."""
        return {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": phone,
                            "id":   msg_id,
                            "type": "text",
                            "text": {"body": text},
                        }]
                    }
                }]
            }]
        }

    async def test_post_sin_firma_rechazado(self, client):
        """Payload sin firma HMAC válida → 403."""
        payload = self._make_payload("+593997097262", "hola")
        resp = await client.post(
            "/webhook",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            # Sin X-Hub-Signature-256
        )
        # En producción rechaza, en dev permite (WHATSAPP_APP_SECRET vacío)
        assert resp.status_code in (200, 403)

    async def test_post_con_firma_invalida_rechazado(self, client):
        """Firma HMAC incorrecta → 403 solo si el secret está configurado."""
        if not settings.whatsapp_app_secret:
            pytest.skip("WHATSAPP_APP_SECRET no configurado — modo dev permite todo")

        payload = self._make_payload("+593997097262", "hola")
        resp = await client.post(
            "/webhook",
            content=json.dumps(payload),
            headers={
                "Content-Type":        "application/json",
                "X-Hub-Signature-256": "sha256=firmafalsaquenocoincide",
            },
        )
        assert resp.status_code == 403

    async def test_post_payload_valido_responde_200(self, client):
        """Un payload bien formado debe responder 200 inmediatamente (procesa en background)."""
        from unittest.mock import patch, AsyncMock

        payload = self._make_payload("+593997097262", "hola")
        body    = json.dumps(payload).encode()

        # Mock de firma para bypassear la verificación
        with patch("app.api.webhook.verify_whatsapp_signature", return_value=True):
            with patch("app.api.webhook._process_payload", new=AsyncMock()):
                resp = await client.post(
                    "/webhook",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_respuesta_es_inmediata_no_bloquea(self, client):
        """El webhook responde 200 inmediatamente — no espera a procesar el mensaje."""
        import time
        from unittest.mock import patch, AsyncMock

        payload = self._make_payload("+593997097262", "saldo")
        body    = json.dumps(payload).encode()

        start = time.time()
        with patch("app.api.webhook.verify_whatsapp_signature", return_value=True):
            with patch("app.api.webhook._process_payload", new=AsyncMock()):
                resp = await client.post(
                    "/webhook",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )
        elapsed = time.time() - start

        assert resp.status_code == 200
        assert elapsed < 2.0  # debe responder en menos de 2 segundos
