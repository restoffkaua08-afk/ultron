"""E2E real: cliente MCP oficial -> Streamable HTTP -> Ultron -> SQLite."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ultron.core.base import Provenance
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.protocol import OPERATION_BINDINGS
from ultron.registry import Registry


def _available_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


async def _wait_until_ready(base_url: str, process: subprocess.Popen[str]) -> None:
    async with httpx.AsyncClient(trust_env=False) as client:
        for _ in range(100):
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise AssertionError(f"Uvicorn encerrou antes do health check: {stdout}\n{stderr}")
            try:
                response = await client.get(f"{base_url}/api/v1/health", timeout=0.2)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await __import__("asyncio").sleep(0.05)
    raise AssertionError("Uvicorn não ficou pronto dentro do prazo")


@pytest.mark.integration
async def test_official_client_completes_lifecycle_over_real_http(tmp_path: Path) -> None:
    registry_path = tmp_path / "mcp-http.db"
    manifest = SkillManifest(
        id=ManifestId("acme", "http-prompt"),
        version="1.0.0",
        publisher="acme",
        description="Capability usada na prova HTTP real",
        skill_type="prompt",
        provenance=Provenance(source="local"),
    )
    async with Registry.open(registry_path) as registry:
        await registry.publish(manifest)

    port = _available_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["ULTRON_REGISTRY_PATH"] = str(registry_path)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ultron.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=Path(__file__).parents[2],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        await _wait_until_ready(base_url, process)
        async with httpx.AsyncClient(trust_env=False) as http_client:
            async with streamable_http_client(
                f"{base_url}/mcp/", http_client=http_client
            ) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == "ULTRON"

                    discovered = await session.list_tools()
                    assert {tool.name for tool in discovered.tools} == {
                        binding.mcp_tool for binding in OPERATION_BINDINGS
                    }

                    installed = await session.call_tool(
                        "ultron_capability_install",
                        {
                            "capability_id": "acme/http-prompt",
                            "organization_id": "org-e2e",
                            "consumer_id": "claude",
                            "confirmed": True,
                        },
                    )
                    assert installed.isError is False
                    assert installed.structuredContent is not None
                    assert installed.structuredContent["executes_code"] is False

                    activated = await session.call_tool(
                        "ultron_capability_activate",
                        {
                            "capability_id": "acme/http-prompt",
                            "organization_id": "org-e2e",
                            "consumer_id": "claude",
                            "confirmed": True,
                        },
                    )
                    assert activated.isError is False
                    assert activated.structuredContent is not None
                    assert activated.structuredContent["active"] is True

                    isolated = await session.call_tool(
                        "ultron_installation_list",
                        {"organization_id": "other-org", "consumer_id": "claude"},
                    )
                    assert isolated.structuredContent == {"results": []}
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
