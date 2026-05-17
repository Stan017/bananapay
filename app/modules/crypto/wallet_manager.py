"""
wallet_manager.py — Gestión de wallets USDT TRC-20
═══════════════════════════════════════════════════
Modelo custodial: BananaPay genera y custodia las llaves privadas.
Cada usuario tiene una dirección TRC-20 única.

Seguridad:
  - La llave privada se encripta con AES-256 (Fernet) antes de guardar en BD.
  - La clave maestra de encriptación viene de WALLET_ENCRYPTION_KEY en .env.
  - Nunca se guarda la llave privada en texto plano.
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from tronpy import Tron
from tronpy.keys import PrivateKey

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── Cliente TRON (lazy — se instancia al primer uso, no al importar) ─────────
_client: "Tron | None" = None

def _get_tron_client() -> "Tron":
    global _client
    if _client is None:
        _client = Tron(network="mainnet")
    return _client


# ─── Encriptación de llaves privadas ─────────────────────────────────────────

def _get_fernet() -> Fernet:
    """
    Retorna una instancia Fernet usando WALLET_ENCRYPTION_KEY del .env.
    La clave debe ser generada con Fernet.generate_key() — 44 chars base64 URL-safe.

    Generación:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    ⚠️  Si la clave no está configurada, el servidor NO arranca.
        Las private keys de los usuarios dependen de esta clave — perderla = perder los fondos.
    """
    from app.config import settings
    key = (settings.wallet_encryption_key or "").strip()

    if not key:
        raise RuntimeError(
            "WALLET_ENCRYPTION_KEY no está configurado en .env. "
            "Genera una clave con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    raw = key.encode()
    if len(raw) != 44:
        raise RuntimeError(
            f"WALLET_ENCRYPTION_KEY tiene formato inválido ({len(raw)} chars, se esperan 44). "
            "Debe ser una clave Fernet válida generada con Fernet.generate_key()."
        )

    return Fernet(raw)


def encrypt_private_key(private_key_hex: str) -> str:
    """Encripta una llave privada hex. Retorna string encriptado."""
    f = _get_fernet()
    return f.encrypt(private_key_hex.encode()).decode()


def decrypt_private_key(encrypted: str) -> str:
    """Desencripta una llave privada. Retorna hex string."""
    try:
        f = _get_fernet()
        return f.decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        logger.error("No se pudo desencriptar llave privada: %s", exc)
        raise ValueError("Llave privada inválida o clave de encriptación incorrecta") from exc


# ─── Generación de wallets ────────────────────────────────────────────────────

def generate_wallet() -> dict:
    """
    Genera una nueva wallet TRC-20.

    Returns:
        {
            "address":               "TXxxx...xxx",   ← dirección pública
            "private_key_encrypted": "gAAA...",       ← llave encriptada (para guardar en BD)
        }
    """
    # Generar par de llaves aleatorio
    private_key = PrivateKey(os.urandom(32))
    address     = private_key.public_key.to_base58check_address()
    encrypted   = encrypt_private_key(private_key.hex())

    logger.info("wallet_manager: nueva wallet generada -> %s", address)
    return {
        "address":               address,
        "private_key_encrypted": encrypted,
    }


def get_private_key(encrypted_key: str) -> PrivateKey:
    """Desencripta y retorna el objeto PrivateKey listo para firmar."""
    hex_key = decrypt_private_key(encrypted_key)
    return PrivateKey(bytes.fromhex(hex_key))


# ─── Consulta de saldo on-chain ───────────────────────────────────────────────

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # USDT TRC-20 en mainnet

def get_onchain_balance(address: str) -> float:
    """
    Consulta el saldo de USDT TRC-20 de una dirección en la blockchain.
    Retorna el saldo como float (ya dividido por 10^6).
    Falla silenciosamente → retorna 0.0.
    """
    try:
        contract = _get_tron_client().get_contract(USDT_CONTRACT)
        raw = contract.functions.balanceOf(address)
        return raw / 1_000_000  # USDT tiene 6 decimales
    except Exception as exc:
        logger.warning("wallet_manager: no se pudo consultar balance on-chain %s — %s", address, exc)
        return 0.0


# ─── Asignación de wallet a usuario ──────────────────────────────────────────

async def assign_wallet_to_user(user_id: str) -> dict:
    """
    Genera una wallet nueva y la guarda en la tabla users.
    Llama esto cuando el usuario se registra.

    Returns:
        {"address": "TXxxx...", "already_existed": bool}
    """
    from app.integrations.supabase_client import get_supabase
    db = get_supabase()

    # Verificar si ya tiene wallet
    result = db.table("users").select("wallet_address").eq("id", user_id).single().execute()
    if result.data and result.data.get("wallet_address"):
        return {"address": result.data["wallet_address"], "already_existed": True}

    # Generar nueva wallet
    wallet = generate_wallet()

    # Guardar en BD
    db.table("users").update({
        "wallet_address":         wallet["address"],
        "wallet_private_key_enc": wallet["private_key_encrypted"],
    }).eq("id", user_id).execute()

    logger.info("wallet_manager: wallet asignada -> user=%s addr=%s", user_id, wallet["address"])
    return {"address": wallet["address"], "already_existed": False}


async def get_user_wallet_address(user_id: str) -> str | None:
    """Retorna la dirección TRC-20 del usuario, o None si no tiene."""
    from app.integrations.supabase_client import get_supabase
    db = get_supabase()
    result = db.table("users").select("wallet_address").eq("id", user_id).single().execute()
    return result.data.get("wallet_address") if result.data else None
