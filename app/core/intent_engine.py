"""
Motor de intenciones — parsea lenguaje natural en español ecuatoriano
y retorna una intención estructurada con parámetros extraídos.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from app.utils.currency import parse_amount
from app.utils.phone import normalize_phone


class Intent(str, Enum):
    # Generales
    GREETING = "greeting"
    HELP = "help"
    BALANCE = "balance"
    HISTORY = "history"
    UNKNOWN = "unknown"

    # Fiat
    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    WITHDRAW_USDT = "withdraw_usdt"

    # Crypto
    CRYPTO_PRICE = "crypto_price"
    CRYPTO_BUY = "crypto_buy"
    CRYPTO_SEND = "crypto_send"
    CRYPTO_WALLET = "crypto_wallet"

    # Auth
    PIN_SETUP = "pin_setup"
    CHANGE_CUSTODY = "change_custody"

    # Cobro con QR
    RECEIVE = "receive"

    # Soporte
    SUPPORT = "support"

    # Cancelación / escape universal
    CANCEL = "cancel"


@dataclass
class ParsedIntent:
    intent: Intent
    amount: Decimal | None = None
    currency: str = "USD"
    recipient: str | None = None       # teléfono normalizado o nombre
    raw_recipient: str | None = None
    params: dict = field(default_factory=dict)


# ─── Tokens crypto reconocidos ────────────────────────────────────────────────

CRYPTO_TOKENS: dict[str, str] = {
    "btc": "BTC", "bitcoin": "BTC",
    "eth": "ETH", "ethereum": "ETH", "ether": "ETH",
    "sol": "SOL", "solana": "SOL",
    "bnb": "BNB",
    "usdt": "USDT", "tether": "USDT",
    "usdc": "USDC",
}

# ─── Conjuntos de palabras clave ──────────────────────────────────────────────

GREETINGS = {
    "hola", "buenas", "hi", "hello", "hey",
    "buen día", "buenas tardes", "buenas noches", "buenos días",
}
HELP_WORDS = {
    "ayuda", "help", "menú", "menu", "opciones",
    "que puedes hacer", "qué puedes hacer", "inicio",
}
SUPPORT_WORDS = {
    "soporte", "agente", "hablar con alguien", "hablar con un agente",
    "necesito ayuda", "quiero hablar", "atencion al cliente",
    "atención al cliente", "contactar", "problema", "queja", "reclamo",
}
BALANCE_WORDS = {
    "saldo", "cuánto tengo", "cuanto tengo", "mi plata",
    "mi saldo", "balance", "cuánto hay", "cuanto hay",
}
HISTORY_WORDS = {
    "historial", "movimientos", "transacciones",
    "mis movimientos", "mis transacciones",
}
CANCEL_WORDS = {
    "cancelar", "cancelalo", "cancelar todo", "cancelar operación",
    "cancel", "salir", "volver", "inicio", "regresar",
    "no quiero", "olvidalo", "olvídalo", "para", "detener",
    "stop", "exit", "abort",
}

# ─── Patrones regex ───────────────────────────────────────────────────────────

# Verbos de transferencia reconocidos
_TRANSFER_VERBS = (
    r"enviar(?:le|les|me|nos)?|envia|manda[rle]*|transferir?|transfiere|transfiero|"
    r"pagar?|pagale|mandale|mandame|dale|pasale|pasame|puedes\s+enviar(?:le|les)?"
)

# Transferencia completa: "enviar $25 a 0991234567"
TRANSFER_PATTERN = re.compile(
    rf"(?:{_TRANSFER_VERBS})\s+"
    r"\$?(\d+(?:[.,]\d+)?)\s*"
    r"(?P<currency>usd|dólares?|dolares?|dólar|dolar|usdt|usdc|btc|eth|sol|bnb)?\s*"
    r"(?:a|al|para|hacia)\s+(?P<recipient>.+)",
    re.IGNORECASE,
)

# Solo verbo sin monto ni destinatario: "enviar"
TRANSFER_VERB_ONLY = re.compile(
    rf"^(?:{_TRANSFER_VERBS})\s*$",
    re.IGNORECASE,
)

# Verbo + destinatario sin monto: "enviar a 0991234567"
TRANSFER_TO_ONLY = re.compile(
    rf"(?:{_TRANSFER_VERBS})\s+(?:a|al|para|hacia)\s+(?P<recipient>.+)",
    re.IGNORECASE,
)

PRICE_PATTERN = re.compile(
    r"(?:precio|price|valor|cotización|cotizacion|cuánto\s+vale|cuanto\s+vale)\s+(?P<token>\w+)",
    re.IGNORECASE,
)

BUY_PATTERN = re.compile(
    r"(?:comprar?|compra)\s+(\d+(?:[.,]\d+)?)\s*(?:de\s+)?(?P<token>\w+)",
    re.IGNORECASE,
)

DEPOSIT_PATTERN = re.compile(
    r"dep[oó]sito|depositar?|deposite|cargar?\s+saldo|recargar?|quiero\s+depositar?",
    re.IGNORECASE,
)

WITHDRAW_USDT_PATTERN = re.compile(
    r"retir[ao]r?\s+usdt|sacar\s+usdt|retirar?\s+crypto|retirar?\s+stable|"
    r"retiro\s+usdt|sacar?\s+(?:mis\s+)?usdt|enviar\s+usdt\s+a",
    re.IGNORECASE,
)

WITHDRAW_PATTERN = re.compile(
    r"retir[ao]r?|retiro|sacar?\s+(?:plata|dinero|saldo)|quiero\s+retirar?",
    re.IGNORECASE,
)

RECEIVE_PATTERN = re.compile(
    r"cobrar?|recibir\s+(?:pago|dinero|plata)|generar?\s+qr|mi\s+qr|"
    r"qr\s+(?:de\s+)?(?:cobro|pago)|quiero\s+cobrar?|crear?\s+qr|como\s+cobro",
    re.IGNORECASE,
)

# "cobrar 50 USDT" / "cobrar 100 USDC"
RECEIVE_AMOUNT_PATTERN = re.compile(
    r"cobrar?\s+(\d+(?:[.,]\d+)?)\s*(?P<token>usdt|usdc)",
    re.IGNORECASE,
)

PIN_PATTERN = re.compile(r"(?:cambiar?|configurar?|poner?|crear?)\s+pin", re.IGNORECASE)

CUSTODY_PATTERN = re.compile(r"cambiar?\s+a\s+(?:self.custody|custodial|binance|coinbase)", re.IGNORECASE)

MY_WALLET_PATTERN = re.compile(r"mi\s+wallet\s+(?P<token>\w+)|ver\s+mis?\s+crypto", re.IGNORECASE)


# ─── Función principal ────────────────────────────────────────────────────────

def parse_intent(text: str) -> ParsedIntent:
    """
    Detecta la intención del mensaje y extrae parámetros relevantes.
    Tolerante a errores ortográficos y jerga ecuatoriana.
    """
    normalized = text.strip().lower()

    def _matches(keywords: set[str]) -> bool:
        """
        Comprueba si alguna keyword aparece en el texto como palabra completa.
        Evita falsos positivos como 'hi' dentro de 'historial'.
        """
        for kw in keywords:
            pattern = r"(?<![a-záéíóúüñ])" + re.escape(kw) + r"(?![a-záéíóúüñ])"
            if re.search(pattern, normalized):
                return True
        return False

    # ── Cancelación — escape universal desde cualquier estado ─────────────────
    if any(c == normalized or normalized.startswith(c) for c in CANCEL_WORDS):
        return ParsedIntent(intent=Intent.CANCEL)

    if _matches(GREETINGS):
        return ParsedIntent(intent=Intent.GREETING)

    if _matches(SUPPORT_WORDS):
        return ParsedIntent(intent=Intent.SUPPORT)

    if _matches(HELP_WORDS):
        return ParsedIntent(intent=Intent.HELP)

    # DEPOSIT antes que BALANCE para que "cargar saldo" no caiga en balance
    if DEPOSIT_PATTERN.search(normalized):
        return ParsedIntent(intent=Intent.DEPOSIT)

    if _matches(BALANCE_WORDS):
        return ParsedIntent(intent=Intent.BALANCE)

    if _matches(HISTORY_WORDS):
        return ParsedIntent(intent=Intent.HISTORY)

    if m := MY_WALLET_PATTERN.search(normalized):
        token = CRYPTO_TOKENS.get((m.group("token") or "").lower())
        return ParsedIntent(intent=Intent.CRYPTO_WALLET, currency=token or "BTC")

    if m := PRICE_PATTERN.search(normalized):
        token = CRYPTO_TOKENS.get(m.group("token").lower())
        if token:
            return ParsedIntent(intent=Intent.CRYPTO_PRICE, currency=token)

    if m := BUY_PATTERN.search(normalized):
        token = CRYPTO_TOKENS.get(m.group("token").lower())
        amount = parse_amount(m.group(1))
        if token and amount:
            return ParsedIntent(intent=Intent.CRYPTO_BUY, amount=amount, currency=token)

    # "enviar" solo — sin monto ni destinatario
    if TRANSFER_VERB_ONLY.match(normalized):
        return ParsedIntent(intent=Intent.TRANSFER)

    if m := TRANSFER_PATTERN.search(normalized):
        amount = parse_amount(m.group(1))
        raw_currency = (m.group("currency") or "usd").lower()
        currency = CRYPTO_TOKENS.get(raw_currency, "USD")
        if raw_currency in ("usd", "dólares", "dolares", "dólar", "dolar"):
            currency = "USD"
        raw_recipient = m.group("recipient").strip()
        recipient = normalize_phone(raw_recipient) or raw_recipient
        if amount:
            return ParsedIntent(
                intent=Intent.TRANSFER,
                amount=amount,
                currency=currency,
                recipient=recipient,
                raw_recipient=raw_recipient,
            )

    # "enviar a 0991234567" — con destinatario pero sin monto
    if m := TRANSFER_TO_ONLY.search(normalized):
        raw_recipient = m.group("recipient").strip()
        recipient = normalize_phone(raw_recipient) or raw_recipient
        return ParsedIntent(
            intent=Intent.TRANSFER,
            recipient=recipient,
            raw_recipient=raw_recipient,
        )

    # "cobrar 50 USDT" — con monto y moneda
    if m := RECEIVE_AMOUNT_PATTERN.search(normalized):
        token  = CRYPTO_TOKENS.get(m.group("token").lower(), "USDT")
        amount = parse_amount(m.group(1))
        return ParsedIntent(intent=Intent.RECEIVE, amount=amount, currency=token)

    # "cobrar", "generar qr", "mi qr", etc.
    if RECEIVE_PATTERN.search(normalized):
        return ParsedIntent(intent=Intent.RECEIVE)

    # USDT antes que fiat para que "retirar usdt" no caiga en WITHDRAW genérico
    if WITHDRAW_USDT_PATTERN.search(normalized):
        return ParsedIntent(intent=Intent.WITHDRAW_USDT)

    if WITHDRAW_PATTERN.search(normalized):
        amount_match = re.search(r"(\d+(?:[.,]\d+)?)", normalized)
        amount = parse_amount(amount_match.group(1)) if amount_match else None
        return ParsedIntent(intent=Intent.WITHDRAW, amount=amount)

    if PIN_PATTERN.search(normalized):
        return ParsedIntent(intent=Intent.PIN_SETUP)

    if CUSTODY_PATTERN.search(normalized):
        return ParsedIntent(intent=Intent.CHANGE_CUSTODY)

    return ParsedIntent(intent=Intent.UNKNOWN)
