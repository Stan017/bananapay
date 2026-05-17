"""Historial completo de operaciones para el panel admin."""

from fastapi import APIRouter, Depends, Query

from app.api.admin.auth import verify_token
from app.integrations.supabase_client import get_supabase

router = APIRouter(prefix="/admin/history", tags=["admin-history"])

PAGE_SIZE = 50


@router.get("/deposits")
async def deposits_history(
    page:   int = Query(1, ge=1),
    status: str = Query("all"),
    token:  dict = Depends(verify_token),
) -> dict:
    """Depósitos fiat (banco + comprobante)."""
    db = get_supabase()
    q = (
        db.table("deposits")
        .select("id, amount, bank_name, reference_number, status, created_at, user:users(name, phone, cedula)")
        .order("created_at", desc=True)
        .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1)
    )
    if status != "all":
        q = q.eq("status", status)
    result = q.execute()
    rows = [{"currency": "USD", "type": "deposit_fiat", **r} for r in (result.data or [])]
    return {"page": page, "data": rows}


@router.get("/crypto-deposits")
async def crypto_deposits_history(
    page:     int = Query(1, ge=1),
    currency: str = Query("all", description="USDT | USDC | all"),
    token:    dict = Depends(verify_token),
) -> dict:
    """Depósitos USDT / USDC TRC-20 detectados por el listener."""
    db = get_supabase()
    q = (
        db.table("crypto_deposits")
        .select("id, amount_usdt, currency, from_address, to_address, tx_hash, status, created_at, user:users(name, phone)")
        .order("created_at", desc=True)
        .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1)
    )
    if currency in ("USDT", "USDC"):
        q = q.eq("currency", currency)
    result = q.execute()
    rows = [
        {
            "type":     f"deposit_{r.get('currency', 'USDT').lower()}",
            "amount":   r.get("amount_usdt"),
            **r,
        }
        for r in (result.data or [])
    ]
    return {"page": page, "data": rows}


@router.get("/withdrawals")
async def withdrawals_history(
    page:   int = Query(1, ge=1),
    status: str = Query("all"),
    token:  dict = Depends(verify_token),
) -> dict:
    """Retiros fiat a banco."""
    db = get_supabase()
    q = (
        db.table("withdrawals")
        .select(
            "id, amount, fee, amount_received, bank_name, account_type, account_number, "
            "account_holder, withdrawal_type, status, created_at, "
            "user:users(name, phone, cedula)"
        )
        .order("created_at", desc=True)
        .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1)
    )
    if status != "all":
        q = q.eq("status", status)
    result = q.execute()
    rows = [{"currency": "USD", "type": "withdrawal_fiat", **r} for r in (result.data or [])]
    return {"page": page, "data": rows}


@router.get("/crypto-withdrawals")
async def crypto_withdrawals_history(
    page:     int = Query(1, ge=1),
    currency: str = Query("all", description="USDT | USDC | all"),
    token:    dict = Depends(verify_token),
) -> dict:
    """Retiros USDT / USDC on-chain (registrados en transactions)."""
    db = get_supabase()
    q = (
        db.table("transactions")
        .select(
            "id, amount, fee, currency, status, created_at, "
            "from_user:from_user_id(name, phone)"
        )
        .eq("tx_type", "withdrawal")
        .in_("currency", ["USDT", "USDC"])
        .order("created_at", desc=True)
        .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1)
    )
    if currency in ("USDT", "USDC"):
        q = q.eq("currency", currency)
    result = q.execute()
    rows = [
        {"type": f"withdrawal_{r.get('currency', 'USDT').lower()}", **r}
        for r in (result.data or [])
    ]
    return {"page": page, "data": rows}


@router.get("/transfers")
async def transfers_history(
    page:  int = Query(1, ge=1),
    token: dict = Depends(verify_token),
) -> dict:
    """Transferencias P2P entre usuarios."""
    db = get_supabase()
    result = (
        db.table("transactions")
        .select(
            "id, amount, fee, currency, status, created_at, "
            "from_user:from_user_id(name, phone), "
            "to_user:to_user_id(name, phone)"
        )
        .eq("tx_type", "transfer")
        .order("created_at", desc=True)
        .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1)
        .execute()
    )
    return {"page": page, "data": result.data or []}


@router.get("/all")
async def all_transactions(
    page:  int = Query(1, ge=1),
    token: dict = Depends(verify_token),
) -> dict:
    """
    Vista unificada de todas las transacciones con badge USD/USDT.
    Ideal para la tabla principal del panel.
    """
    db = get_supabase()
    result = (
        db.table("transactions")
        .select(
            "id, amount, fee, currency, tx_type, status, created_at, "
            "from_user:from_user_id(name, phone), "
            "to_user:to_user_id(name, phone)"
        )
        .order("created_at", desc=True)
        .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1)
        .execute()
    )
    return {"page": page, "data": result.data or []}


@router.get("/fraud-alerts")
async def fraud_alerts(
    page:  int = Query(1, ge=1),
    token: dict = Depends(verify_token),
) -> dict:
    """Alertas de fraude generadas por el sistema."""
    db = get_supabase()
    result = (
        db.table("fraud_alerts")
        .select("id, phone, cedula, reason, amount, tx_type, created_at, user:users(name, phone)")
        .order("created_at", desc=True)
        .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1)
        .execute()
    )
    return {"page": page, "data": result.data or []}
