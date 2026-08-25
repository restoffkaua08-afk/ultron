"""API JSON de manifests — /api/v1/manifests/*."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, HTTPException, Query

from ultron.graph import build_operational_graph
from ultron.registry import RegistryStatus, SearchQuery

if TYPE_CHECKING:
    from ultron.api import get_app_state  # noqa: F401 — só para type-checker


def _state() -> Any:
    """Lazy accessor para evitar import circular no startup."""
    from ultron.api import get_app_state

    return get_app_state()


def build_registry_router() -> APIRouter:
    """Constrói o router da API de manifests."""
    router = APIRouter(tags=["manifests"])

    @router.get("/manifests")
    async def list_manifests(
        kind: str | None = Query(None, pattern="^(agent|skill|workflow|pack)$"),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        reg = _state().registry
        entries = await reg.list_all(kind=kind, limit=limit, offset=offset)
        return {
            "total": await reg.count(kind=kind),
            "limit": limit,
            "offset": offset,
            "results": [_entry_to_json(e) for e in entries],
        }

    @router.get("/manifests/search")
    async def search_manifests(
        q: str = Query("", description="Texto de busca (FTS5)"),
        kind: str | None = Query(None, pattern="^(agent|skill|workflow|pack)$"),
        capability: str | None = Query(None),
        runtime: str | None = Query(None),
        publisher: str | None = Query(None),
        license: str | None = Query(None),
        risk: str | None = Query(None),
        status: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        reg = _state().registry
        parsed_status: RegistryStatus | None = None
        if status:
            try:
                parsed_status = RegistryStatus(status)
            except ValueError as exc:
                allowed = ", ".join(item.value for item in RegistryStatus)
                raise HTTPException(
                    status_code=422, detail=f"Status inválido. Valores aceitos: {allowed}"
                ) from exc
        query = SearchQuery(
            text=q,
            kind=kind,  # type: ignore[arg-type]
            capability=capability,
            runtime=runtime,
            publisher=publisher,
            license=license,
            risk=risk,
            status=parsed_status,
            limit=limit,
            offset=offset,
        )
        entries = await reg.search(query)
        return {
            "total": await reg.count_search(query),
            "limit": limit,
            "offset": offset,
            "results": [_entry_to_json(e) for e in entries],
        }

    @router.get("/manifests/{manifest_id:path}")
    async def get_manifest(manifest_id: str, version: str | None = None) -> dict[str, Any]:
        reg = _state().registry
        if version is None and "@" in manifest_id:
            manifest_id, version = manifest_id.rsplit("@", 1)
        try:
            entry = await reg.get(manifest_id, version)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return _entry_to_json(entry, detailed=True)

    @router.get("/stats")
    async def get_stats() -> dict[str, Any]:
        reg = _state().registry
        return cast("dict[str, Any]", (await reg.stats()).__dict__)

    @router.get("/audit/recent")
    async def get_recent_audit(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        reg = _state().registry
        events = await reg.recent_audit(limit=limit)
        return {"events": events}

    @router.get("/graph")
    async def get_operational_graph(
        q: str = Query("", max_length=120),
        kind: str | None = Query(None),
        relation: str | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ) -> dict[str, Any]:
        """Projeção JSON estável do catálogo e de suas dependências."""
        entries = await _state().registry.list_all(limit=500)
        graph = build_operational_graph(tuple(entry.manifest for entry in entries))
        graph = graph.search(q, kind=kind, relation=relation, limit=limit)
        return {
            "schema_version": "1.0.0",
            "nodes": [
                {"id": node.id, "kind": node.kind, "label": node.label, "version": node.version}
                for node in graph.nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "constraint": edge.constraint,
                }
                for edge in graph.edges
            ],
        }

    return router


def _entry_to_json(entry: Any, detailed: bool = False) -> dict[str, Any]:
    """Serializa um RegistryEntry para JSON."""
    base = {
        "manifest": entry.manifest.model_dump(mode="json"),
        "status": entry.status.value,
        "published_at": entry.published_at.isoformat(),
        "payload_hash": entry.payload_hash,
    }
    if detailed:
        base["manifest_id_str"] = str(entry.manifest.id)
    return base


__all__ = ["build_registry_router"]
