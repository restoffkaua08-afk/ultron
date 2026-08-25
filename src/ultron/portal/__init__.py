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
from ultron.graph import build_operational_graph
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
async def graph_view(
    request: Request,
    q: str = Query("", max_length=120),
    kind: str | None = Query(None),
) -> HTMLResponse:
    """Visualização 2D da mesma projeção servida pela API."""
    reg = _get_registry_singleton()
    all_manifests = await reg.list_all(limit=500)
    graph = build_operational_graph(tuple(entry.manifest for entry in all_manifests))
    graph = graph.search(q, kind=kind, limit=500)
    nodes = [
        {"id": node.id, "label": node.label, "kind": node.kind, "version": node.version}
        for node in graph.nodes
    ]
    edges = [
        {
            "source": edge.source,
            "target": edge.target,
            "label": edge.constraint or edge.relation,
            "relation": edge.relation,
        }
        for edge in graph.edges
    ]

    return templates.TemplateResponse(
        request,
        "graph.html",
        {
            "graph_data": json.dumps({"nodes": nodes, "edges": edges}),
            "active": "graph",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "q": q,
            "kind": kind or "",
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
