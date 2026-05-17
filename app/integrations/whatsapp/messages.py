"""
Tipos de mensajes interactivos para WhatsApp Cloud API.
Soporta: texto plano, botones (hasta 3), listas (hasta 10 opciones).
"""

from dataclasses import dataclass, field


@dataclass
class ImageMessage:
    """
    Mensaje de imagen — se sube a Meta Cloud API y se envía como imagen con caption.
    El handler retorna este tipo; send_bot_message se encarga de subir y enviar.
    Si se define follow_up, webhook.py lo envía como segundo mensaje después de la imagen
    (útil para agregar botones, ya que WhatsApp no permite botones en mensajes de imagen).
    """
    image_bytes: bytes
    mime_type: str = "image/png"
    caption: str = ""
    follow_up: "BotMessage | None" = None


@dataclass
class Btn:
    """Un botón de respuesta rápida. Título máx 20 chars."""
    id: str
    title: str


@dataclass
class ListRow:
    """Una fila dentro de una sección de lista. Título máx 24 chars."""
    id: str
    title: str
    description: str = ""


@dataclass
class ListSection:
    """Sección de una lista. Agrupa filas bajo un título."""
    title: str
    rows: list[ListRow]


@dataclass
class BotMessage:
    """
    Mensaje unificado que puede ser texto, botones o lista.
    - Solo text           → mensaje de texto plano
    - text + buttons      → mensaje con hasta 3 botones de respuesta
    - text + sections     → lista desplegable con hasta 10 opciones
    """
    text: str
    buttons: list[Btn] | None = None
    sections: list[ListSection] | None = None
    list_button_label: str = "Ver opciones"   # texto del botón que abre la lista

    @property
    def is_buttons(self) -> bool:
        return bool(self.buttons)

    @property
    def is_list(self) -> bool:
        return bool(self.sections)


# ─── Mapeo de button IDs a texto de comando ───────────────────────────────────
# Cuando el usuario toca un botón, Meta envía el ID.
# Lo convertimos al texto equivalente y lo procesamos como mensaje normal.

BUTTON_ID_TO_TEXT: dict[str, str] = {
    # Menú principal
    "btn_send":         "enviar",
    "btn_balance":      "saldo",
    "btn_withdraw":     "retirar",
    "btn_deposit":      "depositar",
    # Métodos de depósito
    "btn_deposit_bank": "__deposit_bank__",
    "btn_deposit_usdt": "__deposit_usdt__",
    "btn_history":    "historial",
    "btn_help":       "ayuda",
    "btn_pin":        "cambiar pin",
    "btn_more":       "__menu_more__",   # especial → dispara lista
    # Registro
    "btn_register":   "hola",
    "btn_how":        "ayuda",
    # Confirmaciones
    "btn_confirm":    "sí",
    "btn_cancel":     "no",
    # Método de retiro (fiat vs USDT)
    "btn_withdraw_fiat": "__withdraw_fiat__",
    "btn_withdraw_usdt": "__withdraw_usdt__",
    # Tipo de retiro (valores que _handle_withdraw_type reconoce)
    "btn_normal":     "normal",
    "btn_instant":    "instant",
    # Tipo de cuenta bancaria
    "btn_savings":    "ahorros",
    "btn_checking":   "corriente",
    # Cuenta propia o tercero
    "btn_own_account":   "btn_own_account",
    "btn_third_account": "btn_third_account",
    # Cobrar con QR
    "btn_receive_bp":   "__receive_bp__",
    "btn_receive_usdt": "__receive_usdt__",
    "btn_receive_usdc": "__receive_usdc__",
    # Cerrar sesión (re-auth inmediata)
    "btn_logout":       "__logout__",
    # Selector de moneda al enviar
    "btn_send_usd":     "__send_usd__",
    "btn_send_usdt":    "__send_usdt__",
    "btn_send_usdc":    "__send_usdc__",
    # Modo custody
    "btn_custodial":  "1",
    "btn_selfcustody":"2",
    # Opciones de lista
    "opt_send":       "enviar",
    "opt_receive":    "cobrar",
    "opt_balance":    "saldo",
    "opt_deposit":    "depositar",
    "opt_history":    "historial",
    "opt_pin":        "cambiar pin",
    "opt_help":       "ayuda",
    "opt_withdraw":   "retirar",
    # Selección de banco en retiro
    "opt_bank_pichincha":  "opt_bank_pichincha",
    "opt_bank_guayaquil":  "opt_bank_guayaquil",
    "opt_bank_pacifico":   "opt_bank_pacifico",
    "opt_bank_produbanco": "opt_bank_produbanco",
}


# ─── Helper: botones post-transacción ────────────────────────────────────────

def post_tx_buttons(text: str) -> "BotMessage":
    """
    Envuelve un mensaje de éxito de transacción con botones de navegación.
    Menú → abre el menú principal.
    Salir → cierra la sesión y pide re-autenticación inmediata.
    """
    return BotMessage(
        text=text,
        buttons=[
            Btn("btn_more",   "📋 Menú"),
            Btn("btn_logout", "🔒 Salir"),
        ],
    )


# ─── Menú principal (lista) ───────────────────────────────────────────────────

MAIN_MENU_SECTIONS = [
    ListSection(
        title="💳 Operaciones",
        rows=[
            ListRow("opt_send",     "💸 Enviar plata",      "Transferir a otro usuario"),
            ListRow("opt_receive",  "💳 Cobrar con QR",     "Genera tu QR de cobro"),
            ListRow("opt_deposit",  "📥 Depositar",          "Cargar saldo desde tu banco"),
            ListRow("opt_withdraw", "📤 Retirar",            "Sacar a tu cuenta bancaria"),
        ],
    ),
    ListSection(
        title="📊 Tu cuenta",
        rows=[
            ListRow("opt_balance",  "💰 Ver saldo",          "Saldo actual + movimientos"),
            ListRow("opt_history",  "📄 Historial",           "Últimas transacciones"),
        ],
    ),
    ListSection(
        title="⚙️ Configuración",
        rows=[
            ListRow("opt_pin",      "🔐 Cambiar PIN",        "Actualizar tu contraseña"),
            ListRow("opt_help",     "❓ Ayuda",              "Guía de uso completa"),
        ],
    ),
]
