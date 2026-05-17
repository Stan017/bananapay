"""Endpoint de health check."""

from fastapi import APIRouter

router = APIRouter(tags=["infrastructure"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "BananaPay"}
