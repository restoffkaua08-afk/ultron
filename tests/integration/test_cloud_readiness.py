"""Endpoint público informa somente flags de readiness."""

from fastapi.testclient import TestClient

from ultron.api import create_app


def test_cloud_readiness_does_not_expose_secrets(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ULTRON_REGISTRY_PATH", str(tmp_path / "registry.db"))
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "never-return-this")

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/readiness/cloud")

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert "never-return-this" not in response.text
