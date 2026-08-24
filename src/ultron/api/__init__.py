"""API HTTP do ULTRON — definida no U1.

Stub mantido no U0 para reservar o namespace e a convenção de routers.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["ultron"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — sem I/O, sem dependência externa."""
    return {"status": "ok", "version": "0.1.0"}
