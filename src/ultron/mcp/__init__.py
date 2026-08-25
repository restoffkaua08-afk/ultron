"""Servidor MCP remoto do ULTRON.

O transporte usa Streamable HTTP stateless. A camada MCP permanece fina: ela
consulta o mesmo Registry da API e não executa lifecycle dentro do processo web.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ultron.protocol import protocol_descriptor
from ultron.registry import RegistryStatus
from ultron.resolver import DependencyResolver


def _registry() -> Any:
    """Resolve o Registry no momento da chamada, sem criar estado paralelo."""
    from ultron.api import get_app_state

    return get_app_state().registry


def _installations() -> Any:
    from ultron.api import get_app_state

    return get_app_state().installations


def _installation_json(record: Any) -> dict[str, Any]:
    return {
        "capability_id": record.capability_id,
        "version": record.version,
        "kind": record.kind,
        "payload_sha256": record.payload_sha256,
        "dependencies": list(record.dependencies),
        "is_root": record.is_root,
        "active": record.active,
    }


def _entry(entry: Any) -> dict[str, Any]:
    return {
        "manifest": entry.manifest.model_dump(mode="json"),
        "status": entry.status.value,
        "published_at": entry.published_at.isoformat(),
        "payload_hash": entry.payload_hash,
    }


def _require_confirmation(confirmed: bool, operation: str) -> None:
    if not confirmed:
        raise ValueError(f"{operation} exige confirmed=true após aprovação explícita do usuário")


mcp = FastMCP(
    "ULTRON",
    instructions=(
        "Catálogo neutro de agents, skills, workflows e packs. "
        "Mutações sempre exigem confirmação explícita e um adapter de consumer configurado."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)


@mcp.tool(name="ultron_catalog_list")
async def catalog_list(kind: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Lista capabilities publicadas no catálogo ULTRON."""
    if kind not in {None, "agent", "skill", "workflow", "pack"}:
        raise ValueError("kind deve ser agent, skill, workflow ou pack")
    if not 1 <= limit <= 500 or offset < 0:
        raise ValueError("limit deve estar entre 1 e 500 e offset deve ser >= 0")
    registry = _registry()
    entries = await registry.list_all(kind=kind, limit=limit, offset=offset)
    return {
        "protocol_version": protocol_descriptor()["protocol_version"],
        "total": await registry.count(kind=kind),
        "limit": limit,
        "offset": offset,
        "results": [_entry(entry) for entry in entries],
    }


@mcp.tool(name="ultron_installation_list")
async def installation_list(organization_id: str, consumer_id: str) -> dict[str, Any]:
    """Lista instalações isoladas por organização e consumer."""
    records = await _installations().list(organization_id, consumer_id)
    return {"results": [_installation_json(record) for record in records]}


@mcp.tool(name="ultron_capability_status")
async def capability_status(
    capability_id: str, organization_id: str, consumer_id: str
) -> dict[str, Any]:
    """Consulta estado de uma capability no consumer indicado."""
    record = await _installations().status(organization_id, consumer_id, capability_id)
    return _installation_json(record)


@mcp.tool(name="ultron_compatibility_check")
async def compatibility_check(capability_id: str, version: str | None = None) -> dict[str, Any]:
    """Verifica se uma versão do catálogo pode seguir para planejamento."""
    entry = await _registry().get(capability_id, version)
    compatible = entry.status in {RegistryStatus.PUBLISHED, RegistryStatus.DEPRECATED}
    warnings = []
    if entry.status is RegistryStatus.DEPRECATED:
        warnings.append("A versão está deprecated; prefira uma versão publicada mais recente")
    if not compatible:
        warnings.append(f"A versão está {entry.status.value} e não pode ser instalada")
    return {
        "compatible": compatible,
        "warnings": warnings,
        "capability": _entry(entry),
    }


@mcp.tool(name="ultron_capability_install")
async def capability_install(
    capability_id: str,
    organization_id: str,
    consumer_id: str,
    version: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Resolve e registra metadados; nunca executa o código da capability."""
    _require_confirmation(confirmed, "capability.install")
    registry = _registry()
    root_entry = await registry.get(capability_id, version)
    if root_entry.status not in {RegistryStatus.PUBLISHED, RegistryStatus.DEPRECATED}:
        raise ValueError(f"Capability {root_entry.status.value} não pode ser instalada")
    plan = await DependencyResolver(registry).resolve(root_entry.manifest)
    selected = []
    for item in plan.dependencies:
        selected.append(await registry.get(item.id, item.version))
    selected.append(root_entry)
    selected_ids = {str(entry.manifest.id) for entry in selected}
    from ultron.installations import InstallationRecord

    records = tuple(
        InstallationRecord(
            capability_id=str(entry.manifest.id),
            version=entry.manifest.version,
            kind=entry.manifest.kind,
            payload_sha256=entry.payload_hash,
            dependencies=tuple(
                str(dependency.id)
                for dependency in entry.manifest.dependencies
                if str(dependency.id) in selected_ids
            ),
            is_root=entry is root_entry,
        )
        for entry in selected
    )
    installed = await _installations().install(organization_id, consumer_id, records)
    return {
        "root": f"{plan.root_id}@{plan.root_version}",
        "warnings": list(plan.warnings),
        "results": [_installation_json(record) for record in installed],
        "executes_code": False,
    }


@mcp.tool(name="ultron_capability_activate")
async def capability_activate(
    capability_id: str, organization_id: str, consumer_id: str, confirmed: bool = False
) -> dict[str, Any]:
    """Ativa uma capability instalada após confirmação explícita."""
    _require_confirmation(confirmed, "capability.activate")
    record = await _installations().set_active(
        organization_id, consumer_id, capability_id, active=True
    )
    return _installation_json(record)


@mcp.tool(name="ultron_capability_deactivate")
async def capability_deactivate(
    capability_id: str, organization_id: str, consumer_id: str, confirmed: bool = False
) -> dict[str, Any]:
    """Desativa uma capability após confirmação explícita."""
    _require_confirmation(confirmed, "capability.deactivate")
    record = await _installations().set_active(
        organization_id, consumer_id, capability_id, active=False
    )
    return _installation_json(record)


@mcp.tool(name="ultron_capability_remove")
async def capability_remove(
    capability_id: str, organization_id: str, consumer_id: str, confirmed: bool = False
) -> dict[str, Any]:
    """Remove uma capability após confirmação explícita."""
    _require_confirmation(confirmed, "capability.remove")
    await _installations().remove(organization_id, consumer_id, capability_id)
    return {"removed": True, "capability_id": capability_id}


def create_mcp_server() -> FastMCP:
    """Cria uma instância isolada; o session manager do SDK não é reiniciável."""
    server = FastMCP(
        "ULTRON",
        instructions=mcp.instructions,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    )
    for tool in mcp._tool_manager._tools.values():
        server.add_tool(
            tool.fn,
            name=tool.name,
            title=tool.title,
            description=tool.description,
            annotations=tool.annotations,
            icons=tool.icons,
            meta=tool.meta,
        )
    return server


__all__ = ["create_mcp_server", "mcp"]
