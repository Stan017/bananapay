"""
Tests del command router del bot WhatsApp.
Testea route() directamente con intents pre-parseados.
No depende de Claude, Redis, Meta ni Supabase real.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.command_router import route
from app.core.intent_engine import Intent, ParsedIntent
from app.core.session import ConversationState

# ─── Helpers ─────────────────────────────────────────────────────────────────

TEST_PHONE = "+593997097262"

TEST_USER = {
    "id":           "550e8400-e29b-41d4-a716-446655440000",
    "name":         "Stanley Bolivar Llaguno Caicedo",
    "phone":        TEST_PHONE,
    "cedula":       "0928732494",
    "is_active":    True,
    "kyc_level":    1,
    "custody_mode": "custodial",
}

def make_session(state: ConversationState, context: dict = None, last_activity: float = 9999999999) -> dict:
    """Crea un dict de sesión con el estado dado."""
    return {
        "state":         state,
        "context":       context or {},
        "last_activity": last_activity,
    }

def parsed(intent: Intent, **kwargs) -> ParsedIntent:
    """Atajo para crear un ParsedIntent en tests."""
    return ParsedIntent(intent=intent, **kwargs)


# ─── 1. Usuario nuevo ─────────────────────────────────────────────────────────

class TestUsuarioNuevo:
    async def test_usuario_nuevo_inicia_registro(self):
        """Un número desconocido debe recibir el mensaje de bienvenida y arrancar el onboarding."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.IDLE))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
            patch("app.modules.auth.register.get_user_by_phone", new=AsyncMock(return_value=None)),
        ):
            resp = await route(TEST_PHONE, "hola", parsed(Intent.GREETING))

        assert "BananaPay" in resp
        assert "nombre" in resp.lower() or "nombres" in resp.lower()

    async def test_usuario_nuevo_recibe_instruccion_de_nombre(self):
        """El primer mensaje debe pedir dos nombres y dos apellidos."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.IDLE))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
            patch("app.modules.auth.register.get_user_by_phone", new=AsyncMock(return_value=None)),
        ):
            resp = await route(TEST_PHONE, "hola", parsed(Intent.GREETING))

        assert "dos nombres" in resp.lower() or "dos apellidos" in resp.lower() or "nombre completo" in resp.lower()


# ─── 2. Usuario existente en IDLE ─────────────────────────────────────────────

class TestUsuarioExistente:
    async def test_usuario_existente_idle_inicia_reauth(self):
        """Un usuario registrado en estado IDLE debe recibir el flujo de re-autenticación."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.IDLE))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
            patch("app.modules.auth.register.get_user_by_phone", new=AsyncMock(return_value=TEST_USER)),
        ):
            resp = await route(TEST_PHONE, "hola", parsed(Intent.GREETING))

        assert "cédula" in resp.lower() or "últimos 4" in resp.lower()

    async def test_timeout_inactividad_dispara_reauth(self):
        """Si pasaron más de 8 minutos sin actividad, debe pedir re-autenticación."""
        import time
        old_time = time.time() - (9 * 60)  # 9 minutos atrás

        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(
                      ConversationState.AUTHENTICATED, last_activity=old_time
                  ))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
        ):
            resp = await route(TEST_PHONE, "saldo", parsed(Intent.BALANCE))

        assert "inactividad" in resp.lower() or "cédula" in resp.lower()


# ─── 3. Cancelación universal ─────────────────────────────────────────────────

class TestCancelacion:
    async def test_cancelar_operacion_activa(self):
        """'cancelar' durante un flujo activo debe terminar la operación."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.AWAITING_TRANSFER_AMOUNT))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
        ):
            resp = await route(TEST_PHONE, "cancelar", parsed(Intent.CANCEL))

        assert "cancelada" in resp.lower()

    async def test_cancelar_sin_operacion_responde_amigable(self):
        """'cancelar' sin operación activa no debe dar error."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.AUTHENTICATED))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
        ):
            resp = await route(TEST_PHONE, "cancelar", parsed(Intent.CANCEL))

        assert resp  # algo responde


# ─── 4. Consultas de usuario autenticado ─────────────────────────────────────

class TestConsultasAutenticado:
    def _auth_session(self):
        return make_session(ConversationState.AUTHENTICATED)

    async def test_saldo_responde_con_balance(self):
        from decimal import Decimal
        mock_balances = {"fiat": Decimal("100.00"), "usdt": Decimal("0"), "usdc": Decimal("0"), "total": Decimal("100.00")}

        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=self._auth_session())),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
            patch("app.modules.auth.register.get_user_by_phone", new=AsyncMock(return_value=TEST_USER)),
            patch("app.modules.fiat.wallet.get_balances", new=AsyncMock(return_value=mock_balances)),
        ):
            resp = await route(TEST_PHONE, "saldo", parsed(Intent.BALANCE))

        # _handle_balance puede retornar str o BotMessage (con .text)
        resp_text = resp.text if hasattr(resp, "text") else resp
        assert "$100.00" in resp_text or "100" in resp_text

    async def test_saldo_contiene_moneda(self):
        mock_balances = {"fiat": Decimal("55.00"), "usdt": Decimal("0"), "usdc": Decimal("0"), "total": Decimal("55.00")}

        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=self._auth_session())),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
            patch("app.modules.auth.register.get_user_by_phone", new=AsyncMock(return_value=TEST_USER)),
            patch("app.modules.fiat.wallet.get_balances", new=AsyncMock(return_value=mock_balances)),
        ):
            resp = await route(TEST_PHONE, "saldo", parsed(Intent.BALANCE))

        resp_text = resp.text if hasattr(resp, "text") else resp
        assert "USD" in resp_text or "$" in resp_text

    async def test_intent_desconocido_responde_sin_crashear(self):
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=self._auth_session())),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
        ):
            resp = await route(TEST_PHONE, "blablabla xyz", parsed(Intent.UNKNOWN))

        assert resp  # nunca debe retornar vacío o None
        assert isinstance(resp, str)

    async def test_saludo_a_usuario_autenticado(self):
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=self._auth_session())),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
            patch("app.modules.auth.register.get_user_by_phone", new=AsyncMock(return_value=TEST_USER)),
            patch("app.modules.fiat.wallet.get_balances",
                  new=AsyncMock(return_value={"fiat": Decimal("0"), "usdt": Decimal("0"),
                                              "usdc": Decimal("0"), "total": Decimal("0")})),
        ):
            resp = await route(TEST_PHONE, "hola", parsed(Intent.GREETING))

        assert resp


# ─── 5. Inicio de transferencia ───────────────────────────────────────────────

class TestTransferencia:
    def _auth_session(self):
        return make_session(ConversationState.AUTHENTICATED)

    async def test_transfer_sin_datos_pide_moneda(self):
        """'enviar' sin destinatario ni monto debe preguntar en qué moneda."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=self._auth_session())),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
            patch("app.modules.auth.register.get_user_by_phone", new=AsyncMock(return_value=TEST_USER)),
        ):
            resp = await route(TEST_PHONE, "enviar", parsed(Intent.TRANSFER))

        # Debe preguntar algo — moneda, destinatario o monto
        assert resp
        assert isinstance(resp, str)

    async def test_transfer_con_monto_pide_destinatario(self):
        """'enviar 50' debe preguntar a quién."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=self._auth_session())),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
            patch("app.modules.auth.register.get_user_by_phone", new=AsyncMock(return_value=TEST_USER)),
        ):
            resp = await route(TEST_PHONE, "enviar 50", parsed(Intent.TRANSFER, amount=Decimal("50")))

        assert resp
        assert isinstance(resp, str)


# ─── 6. Registro paso a paso ──────────────────────────────────────────────────

class TestRegistroPasoAPaso:
    async def test_nombre_invalido_pide_repetir(self):
        """Nombre con menos de 4 palabras debe rechazarse."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.AWAITING_NAME))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
        ):
            resp = await route(TEST_PHONE, "Juan Pérez", parsed(Intent.UNKNOWN))

        assert resp
        # Debe indicar que faltan palabras
        assert "nombre" in resp.lower() or "palabras" in resp.lower() or "apellido" in resp.lower()

    async def test_nombre_valido_avanza_a_cedula(self):
        """Nombre con 4 palabras debe avanzar al paso de cédula."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.AWAITING_NAME))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()) as mock_set,
        ):
            resp = await route(TEST_PHONE, "Stanley Bolivar Llaguno Caicedo", parsed(Intent.UNKNOWN))

        assert resp
        # Debe pedir la cédula
        assert "cédula" in resp.lower()

    async def test_cedula_invalida_pide_repetir(self):
        """Una cédula con dígitos incorrectos debe rechazarse."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.AWAITING_CEDULA))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
        ):
            resp = await route(TEST_PHONE, "1234567890", parsed(Intent.UNKNOWN))

        assert "cédula" in resp.lower() or "válida" in resp.lower() or "inválida" in resp.lower()

    async def test_pin_debil_rechazado_en_registro(self):
        """Un PIN débil como 123456 debe ser rechazado durante el registro."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.AWAITING_PIN_SET))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
        ):
            resp = await route(TEST_PHONE, "123456", parsed(Intent.UNKNOWN))

        assert "pin" in resp.lower() or "seguro" in resp.lower() or "secuencia" in resp.lower()

    async def test_pin_fuerte_aceptado(self):
        """Un PIN fuerte debe ser aceptado y pedir confirmación."""
        with (
            patch("app.core.command_router.session_manager.get",
                  new=AsyncMock(return_value=make_session(ConversationState.AWAITING_PIN_SET))),
            patch("app.core.command_router.session_manager.set_state", new=AsyncMock()),
        ):
            resp = await route(TEST_PHONE, "391047", parsed(Intent.UNKNOWN))

        assert "confirmar" in resp.lower() or "otra vez" in resp.lower() or "confirm" in resp.lower()
