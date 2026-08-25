"""API HTTP do ULTRON (FastAPI).

Stack: FastAPI + Uvicorn. Endpoints versionados em /api/v1/*.
Portal HTML servido em /.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ultron.api.registry_router import build_registry_router
from ultron.audit import configure_logging, get_logger
from ultron.cloud import cloud_readiness
from ultron.portal import router as portal_router
from ultron.portal import templates as _unused_init_marker
from ultron.registry import DEFAULT_REGISTRY_PATH, Registry

log = get_logger("ultron.api")


# ---- App state (singleton) -----------------------------------------------


@dataclass
class AppState:
    registry: Registry
    config: dict[str, Any] = field(default_factory=dict)


_state: AppState | None = None


def get_app_state() -> AppState:
    """Retorna o estado singleton da app (criado no lifespan)."""
    if _state is None:
        raise RuntimeError("App state not initialized — app ainda não rodou lifespan.")
    return _state


def _set_app_state(state: AppState | None) -> None:
    global _state
    _state = state


# ---- Lifespan ------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Inicializa e finaliza o registry singleton."""
    configure_logging(level=os.environ.get("ULTRON_LOG", "INFO"))
    registry_path = Path(os.environ.get("ULTRON_REGISTRY_PATH", str(DEFAULT_REGISTRY_PATH)))
    log.info("opening_registry", path=str(registry_path))
    reg = Registry(registry_path)
    await reg.start()

    _set_app_state(AppState(registry=reg, config={"registry_path": registry_path}))
    log.info("ultron_ready")

    try:
        yield
    finally:
        log.info("closing_registry")
        await reg.close()
        _set_app_state(None)


# ---- FastAPI app ----------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="ULTRON API",
        version="0.1.0",
        description="Plataforma independente de capabilities versionadas.",
        lifespan=_lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    # Static files (CSS, JS do portal)
    static_dir = Path(__file__).parent.parent / "portal" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # API JSON de manifests
    app.include_router(build_registry_router(), prefix="/api/v1")

    # Portal HTML
    app.include_router(portal_router)

    # Health
    @app.get("/api/v1/health", tags=["meta"])
    async def health() -> dict[str, Any]:
        state = get_app_state()
        stats = await state.registry.stats()
        return {
            "status": "ok",
            "version": app.version,
            "registry": {
                "path": str(state.config["registry_path"]),
                "manifests": stats.total,
            },
        }

    @app.get("/api/v1/readiness/cloud", tags=["meta"])
    async def readiness_cloud() -> dict[str, Any]:
        readiness = cloud_readiness()
        return {
            "ready": readiness.ready,
            "mode": readiness.mode,
            "components": {
                "supabase": readiness.supabase,
                "github_auth": readiness.github_auth,
                "github_app": readiness.github_app,
                "mcp_oauth": readiness.mcp_oauth,
            },
        }

    return app


# Singleton app (para `uvicorn ultron.api:app`)
app = create_app()


__all__ = ["app", "create_app", "get_app_state"]
