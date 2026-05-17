"""Rutas admin para solicitudes de soporte."""

import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.admin.auth import verify_token
from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

router = APIRouter(prefix="/admin/support", tags=["admin-support"])
logger = get_logger(__name__)


@router.get("/pending")
async def list_pending(token: dict = Depends(verify_token)) -> list:
    """Retorna solicitudes de soporte pendientes, más recientes primero."""
    db = get_supabase()
    result = (
        db.table("support_requests")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


@router.post("/{request_id}/attend")
async def mark_attended(request_id: str, token: dict = Depends(verify_token)) -> dict:
    """Marca una solicitud como atendida."""
    db = get_supabase()
    result = db.table("support_requests").update({
        "status":      "attended",
        "attended_at": datetime.datetime.utcnow().isoformat(),
        "attended_by": token["sub"],
    }).eq("id", request_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    logger.info("Soporte atendido: id=%s by=%s", request_id, token["sub"])
    return result.data[0]
