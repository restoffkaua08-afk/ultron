"""Fonte de verdade neutra para operações Python, REST e MCP."""

from dataclasses import asdict, dataclass

from ultron.consumer import CONSUMER_PROTOCOL_VERSION


@dataclass(frozen=True, slots=True)
class OperationBinding:
    operation: str
    python_method: str
    rest_method: str
    rest_path: str
    mcp_tool: str
    mutating: bool = False
    requires_confirmation: bool = False


OPERATION_BINDINGS = (
    OperationBinding(
        "catalog.list", "get_capabilities", "GET", "/api/v1/manifests", "ultron_catalog_list"
    ),
    OperationBinding(
        "installation.list",
        "list_installed",
        "GET",
        "/api/v1/installations",
        "ultron_installation_list",
    ),
    OperationBinding(
        "capability.status",
        "get_status",
        "GET",
        "/api/v1/capabilities/{id}/status",
        "ultron_capability_status",
    ),
    OperationBinding(
        "compatibility.check",
        "check_compatibility",
        "POST",
        "/api/v1/compatibility/check",
        "ultron_compatibility_check",
    ),
    OperationBinding(
        "capability.install",
        "install",
        "POST",
        "/api/v1/installations",
        "ultron_capability_install",
        True,
        True,
    ),
    OperationBinding(
        "capability.activate",
        "activate",
        "POST",
        "/api/v1/capabilities/{id}/activate",
        "ultron_capability_activate",
        True,
        True,
    ),
    OperationBinding(
        "capability.deactivate",
        "deactivate",
        "POST",
        "/api/v1/capabilities/{id}/deactivate",
        "ultron_capability_deactivate",
        True,
        True,
    ),
    OperationBinding(
        "capability.remove",
        "remove",
        "DELETE",
        "/api/v1/capabilities/{id}",
        "ultron_capability_remove",
        True,
        True,
    ),
)


def protocol_descriptor() -> dict[str, object]:
    return {
        "protocol_version": CONSUMER_PROTOCOL_VERSION,
        "operations": [asdict(item) for item in OPERATION_BINDINGS],
    }


__all__ = ["OPERATION_BINDINGS", "OperationBinding", "protocol_descriptor"]
