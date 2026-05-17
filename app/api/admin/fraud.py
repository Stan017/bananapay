"""Endpoints admin — Alertas de fraude y configuración de límites."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from app.api.admin.auth import verify_token


def _require_super_admin(token: dict) -> None:
    if token.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo super_admin puede realizar esta acción",
        )
from app.integrations.supabase_client import get_supabase
from app.modules.fiat.fraud import (
    get_open_alerts, resolve_alert,
    get_blacklist, add_to_blacklist, remove_from_blacklist,
)
from app.utils.logger import get_logger

router = APIRouter(prefix="/admin/fraud", tags=["admin-fraud"])
logger = get_logger(__name__)


# ─── Alertas ─────────────────────────────────────────────────────────────────

@router.get("/alerts")
async def list_fraud_alerts(_: str = Depends(verify_token)):
    """Retorna todas las alertas de fraude no resueltas."""
    alerts = get_open_alerts(limit=100)
    return {"alerts": alerts, "total": len(alerts)}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_fraud_alert(alert_id: str, _: str = Depends(verify_token)):
    """Marca una alerta como resuelta."""
    ok = resolve_alert(alert_id)
    return {"ok": ok}


# ─── Configuración de límites ─────────────────────────────────────────────────

class FraudConfigUpdate(BaseModel):
    high_deposit_amount:    float
    high_withdrawal_amount: float
    max_rejected_per_hour:  int
    new_user_hours:         int
    new_user_max_deposit:   float

    @field_validator("high_deposit_amount", "high_withdrawal_amount", "new_user_max_deposit")
    @classmethod
    def positive_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        return v

    @field_validator("max_rejected_per_hour", "new_user_hours")
    @classmethod
    def positive_int(cls, v: int) -> int:
        if v < 1:
            raise ValueError("El valor debe ser al menos 1")
        return v


@router.get("/config")
async def get_config(_: str = Depends(verify_token)):
    """Retorna la configuración actual de límites de fraude."""
    try:
        db = get_supabase()
        rows = db.table("fraud_config").select("*").order("key").execute()
        return {"config": rows.data or []}
    except Exception as exc:
        logger.error("fraud config GET error: %s", exc)
        raise HTTPException(status_code=500, detail="Error leyendo configuración")


@router.put("/config")
async def update_config(body: FraudConfigUpdate, token: dict = Depends(verify_token)):
    """Actualiza los límites de fraude. Solo super_admin."""
    _require_super_admin(token)
    db = get_supabase()
    updates = {
        "high_deposit_amount":    str(body.high_deposit_amount),
        "high_withdrawal_amount": str(body.high_withdrawal_amount),
        "max_rejected_per_hour":  str(body.max_rejected_per_hour),
        "new_user_hours":         str(body.new_user_hours),
        "new_user_max_deposit":   str(body.new_user_max_deposit),
    }
    try:
        for key, value in updates.items():
            db.table("fraud_config").update({
                "value":      value,
                "updated_at": "now()",
            }).eq("key", key).execute()

        logger.info("fraud_config actualizado por %s: %s", token.get("sub"), updates)
        return {"ok": True, "updated": updates}
    except Exception as exc:
        logger.error("fraud config PUT error: %s", exc)
        raise HTTPException(status_code=500, detail="Error guardando configuración")


# ─── Blacklist ────────────────────────────────────────────────────────────────

class BlacklistAdd(BaseModel):
    phone:  str | None = None
    cedula: str | None = None
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El motivo no puede estar vacío")
        return v.strip()


@router.get("/blacklist")
async def list_blacklist(_: dict = Depends(verify_token)):
    """Retorna la blacklist completa."""
    return {"blacklist": get_blacklist()}


@router.post("/blacklist")
async def create_blacklist_entry(body: BlacklistAdd, token: dict = Depends(verify_token)):
    """Agrega un número o cédula a la blacklist."""
    if not body.phone and not body.cedula:
        raise HTTPException(status_code=400, detail="Debes indicar phone o cedula")
    ok = add_to_blacklist(
        reason=body.reason,
        phone=body.phone,
        cedula=body.cedula,
        blocked_by=token.get("sub", "admin"),
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Error guardando en blacklist")
    return {"ok": True}


@router.delete("/blacklist/{entry_id}")
async def delete_blacklist_entry(entry_id: str, _: dict = Depends(verify_token)):
    """Elimina una entrada de la blacklist."""
    ok = remove_from_blacklist(entry_id)
    return {"ok": ok}
