"""Provas do servidor MCP e da equivalência com o contrato neutro."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ultron.api import create_app
from ultron.mcp import mcp
from ultron.protocol import OPERATION_BINDINGS


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    os.environ["ULTRON_REGISTRY_PATH"] = str(tmp_path / "registry.db")
    with TestClient(create_app()) as value:
        yield value


async def test_mcp_exposes_exactly_the_bound_tools() -> None:
    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == {binding.mcp_tool for binding in OPERATION_BINDINGS}


def test_mcp_catalog_uses_the_application_registry(client: TestClient) -> None:
    assert client.portal is not None
    _, payload = client.portal.call(
        client.app.state.ultron_mcp.call_tool, "ultron_catalog_list", {"limit": 10}
    )
    assert payload["protocol_version"] == "1.0.0"
    assert payload["total"] == 0
    assert payload["results"] == []


def test_mcp_mutation_rejects_missing_confirmation(client: TestClient) -> None:
    assert client.portal is not None
    with pytest.raises(Exception, match="confirmed=true"):
        client.portal.call(
            client.app.state.ultron_mcp.call_tool,
            "ultron_capability_install",
            {"capability_id": "acme/example", "consumer_id": "claude"},
        )


def test_mcp_is_mounted_at_stable_path(client: TestClient) -> None:
    route = next(route for route in client.app.routes if getattr(route, "name", None) == "mcp")
    assert route.path == "/mcp"
