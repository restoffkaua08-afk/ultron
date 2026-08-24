"""Portal web do ULTRON — design inspirado no Obsidian.

Stack: FastAPI + Jinja2 + HTMX (carregado via CDN) + CSS custom.
Sem build step. Funciona com JS desabilitado (degradação graciosa).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ultron.audit import configure_logging
from ultron.registry import Registry, SearchQuery

# Templates ficam em src/ultron/portal/templates/
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["portal"])


# ---- Dependency: pega a instância singleton de registry -------------------


def _get_registry_singleton() -> Registry:
    """Retorna a instância do registry (criada no lifespan da app).

    Import lazy para evitar ciclo com ``ultron.api``.
    """
    from ultron.api import get_app_state

    return get_app_state().registry


# ---- Páginas --------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Página inicial: dashboard com stats + manifestos recentes."""
    reg = _get_registry_singleton()
    stats = await reg.stats()
    recent = await reg.list_all(limit=10)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "stats": stats,
            "recent": recent,
            "active": "home",
        },
    )


@router.get("/browse", response_class=HTMLResponse)
async def browse(
    request: Request,
    q: str = Query("", description="Texto de busca"),
    kind: str | None = Query(None),
    capability: str | None = Query(None),
) -> HTMLResponse:
    """Página de browse com busca + filtros."""
    reg = _get_registry_singleton()
    allowed_kinds = {"agent", "skill", "workflow", "pack"}
    kind_filter: str | None = kind if kind in allowed_kinds else None
    results = await reg.search(
        SearchQuery(
            text=q,
            kind=kind_filter,  # type: ignore[arg-type]
            capability=capability,
            limit=100,
        )
    )
    return templates.TemplateResponse(
        request,
        "browse.html",
        {
            "q": q,
            "kind": kind or "",
            "capability": capability or "",
            "results": results,
            "active": "browse",
        },
    )


@router.get("/manifest/{manifest_id}", response_class=HTMLResponse)
async def manifest_detail(
    request: Request,
    manifest_id: str,
    version: str | None = None,
) -> HTMLResponse:
    """Página de detalhe de um manifest."""
    reg = _get_registry_singleton()
    try:
        entry = await reg.get(manifest_id, version)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    # Buscar dependências e quem depende deste (backlinks)
    deps_resolved: list[dict[str, Any]] = []
    for dep in entry.manifest.dependencies:
        try:
            dep_entry = await reg.get(dep.id)
            deps_resolved.append(
                {
                    "id": str(dep.id),
                    "version": dep_entry.manifest.version,
                    "kind": dep_entry.manifest.kind,
                    "range": dep.version_range,
                    "resolved": True,
                }
            )
        except Exception:
            deps_resolved.append(
                {
                    "id": str(dep.id),
                    "version": "?",
                    "kind": "?",
                    "range": dep.version_range,
                    "resolved": False,
                }
            )

    # Backlinks: quem depende deste manifest
    all_manifests = await reg.list_all(limit=500)
    backlinks: list[dict[str, Any]] = []
    for other in all_manifests:
        if other.manifest.id == entry.manifest.id:
            continue
        for d in other.manifest.dependencies:
            if d.id == entry.manifest.id:
                backlinks.append(
                    {
                        "id": str(other.manifest.id),
                        "version": other.manifest.version,
                        "kind": other.manifest.kind,
                        "range": d.version_range,
                    }
                )
                break

    return templates.TemplateResponse(
        request,
        "manifest.html",
        {
            "entry": entry,
            "manifest": entry.manifest,
            "manifest_json": entry.manifest.model_dump_json(indent=2),
            "deps_resolved": deps_resolved,
            "backlinks": backlinks,
            "active": "browse",
        },
    )


@router.get("/graph", response_class=HTMLResponse)
async def graph_view(request: Request) -> HTMLResponse:
    """Visualização do grafo de dependências (2D via Sigma.js)."""
    reg = _get_registry_singleton()
    all_manifests = await reg.list_all(limit=500)

    nodes = []
    edges = []
    for m in all_manifests:
        nodes.append(
            {
                "id": f"{m.manifest.id}@{m.manifest.version}",
                "label": m.manifest.id.name,
                "kind": m.manifest.kind,
                "publisher": m.manifest.publisher,
            }
        )
    id_index = {n["id"]: n for n in nodes}
    for m in all_manifests:
        for d in m.manifest.dependencies:
            target_id = f"{d.id}@?"
            if target_id not in id_index:
                # nó fantasma
                nodes.append(
                    {
                        "id": target_id,
                        "label": d.id.name,
                        "kind": "?",
                        "publisher": d.id.publisher,
                    }
                )
                id_index[target_id] = nodes[-1]
            edges.append(
                {
                    "source": f"{m.manifest.id}@{m.manifest.version}",
                    "target": target_id,
                    "label": d.version_range,
                }
            )

    return templates.TemplateResponse(
        request,
        "graph.html",
        {
            "graph_data": json.dumps({"nodes": nodes, "edges": edges}),
            "active": "graph",
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    )


@router.get("/audit", response_class=HTMLResponse)
async def audit_log(request: Request) -> HTMLResponse:
    """Página de auditoria."""
    reg = _get_registry_singleton()
    events = await reg.recent_audit(limit=100)
    return templates.TemplateResponse(
        request,
        "audit.html",
        {
            "events": events,
            "active": "audit",
        },
    )


# ---- Inicialização (chamada pelo lifespan da app) -----------------------


def configure_portal_logging(level: str = "INFO") -> None:
    configure_logging(level=level)


__all__ = ["router", "templates"]
