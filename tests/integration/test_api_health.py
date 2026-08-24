"""Smoke test: app FastAPI + endpoints básicos."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ultron.api import create_app


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
    assert "data-theme=\"dark\"" in body


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
