"""Helpers de validación de direcciones crypto."""

import re


def is_valid_evm_address(address: str) -> bool:
    """Valida dirección EVM (Ethereum, BSC, etc.) en formato checksum o lowercase."""
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", address))


def is_valid_btc_address(address: str) -> bool:
    """Validación básica de dirección Bitcoin (P2PKH, P2SH, Bech32)."""
    return bool(re.fullmatch(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59}", address))


def is_valid_sol_address(address: str) -> bool:
    """Valida dirección Solana (base58, 32-44 caracteres)."""
    return bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", address))
