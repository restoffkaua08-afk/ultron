"""Smoke test: app FastAPI + endpoints básicos."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ultron.api import create_app, get_app_state
from ultron.core.base import Provenance, RiskLevel
from ultron.core.ids import ManifestId
from ultron.core.manifests import AgentManifest


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Cliente síncrono com DB isolado por teste."""
    os.environ["ULTRON_REGISTRY_PATH"] = str(tmp_path / "registry.db")
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["registry"]["manifests"] == 0


def test_openapi_served(client: TestClient) -> None:
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    assert "/api/v1/health" in paths
    assert "/api/v1/manifests" in paths
    assert "/api/v1/manifests/search" in paths
    assert "/" in paths


def test_index_renders(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "ULTRON" in body
    assert 'data-theme="dark"' in body


def test_browse_renders(client: TestClient) -> None:
    r = client.get("/browse")
    assert r.status_code == 200
    assert "Buscar" in r.text


def test_audit_renders_empty(client: TestClient) -> None:
    r = client.get("/audit")
    assert r.status_code == 200
    assert "Audit" in r.text
    assert "Nenhum evento" in r.text


def test_static_css_served(client: TestClient) -> None:
    r = client.get("/static/ultron.css")
    assert r.status_code == 200
    assert "ULTRON portal" in r.text


def test_search_endpoint_empty(client: TestClient) -> None:
    r = client.get("/api/v1/manifests/search?q=test")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["results"] == []


def test_list_endpoint_empty(client: TestClient) -> None:
    r = client.get("/api/v1/manifests")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0


def test_get_missing_returns_404(client: TestClient) -> None:
    r = client.get("/api/v1/manifests/missing-pkg")
    assert r.status_code == 404


def _publish_agent(client: TestClient, *, version: str = "1.0.0") -> AgentManifest:
    manifest = AgentManifest(
        id=ManifestId(publisher="acme", name="api-agent"),
        version=version,
        description="Agente publicado pelo teste da API",
        publisher="acme",
        license="MIT",
        risks=RiskLevel.LOW,
        runtime="python:3.12",
        entrypoint="acme.api.agent:main",
        capabilities=["search.web"],
        provenance=Provenance(source="local"),
    )
    assert client.portal is not None
    client.portal.call(get_app_state().registry.publish, manifest)
    return manifest


def test_get_manifest_accepts_id_with_slash_and_at_version(client: TestClient) -> None:
    _publish_agent(client)

    response = client.get("/api/v1/manifests/acme/api-agent@1.0.0")

    assert response.status_code == 200
    assert response.json()["manifest"]["version"] == "1.0.0"


def test_search_total_is_not_limited_to_page_size(client: TestClient) -> None:
    _publish_agent(client, version="1.0.0")
    _publish_agent(client, version="2.0.0")

    response = client.get("/api/v1/manifests/search?q=agente&limit=1")

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["results"]) == 1


def test_search_rejects_invalid_status(client: TestClient) -> None:
    response = client.get("/api/v1/manifests/search?status=unknown")

    assert response.status_code == 422
