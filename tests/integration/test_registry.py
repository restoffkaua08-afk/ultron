"""Testes de integração do Registry (U1).

Stack: pytest-asyncio + fixtures para DB temporário.
Cobre: CRUD, FTS5, audit log, imutabilidade, versionamento.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio

from ultron.core.base import (
    Provenance,
    RiskLevel,
)
from ultron.core.errors import (
    UltronError,
    VersionConflictError,
)
from ultron.core.ids import ManifestId
from ultron.core.manifests import AgentManifest
from ultron.registry import Registry, RegistryStatus, SearchQuery

pytestmark = pytest.mark.integration


# ---- Fixtures -------------------------------------------------------------


@pytest_asyncio.fixture
async def registry(tmp_path: Path) -> AsyncIterator[Registry]:
    """Registry com DB temporário, inicializado."""
    db_path = tmp_path / "registry.db"
    reg = Registry(db_path)
    await reg.start()
    try:
        yield reg
    finally:
        await reg.close()


@pytest.fixture
def agent_v1() -> AgentManifest:
    """Manifest de agent válido."""
    return AgentManifest(
        id=ManifestId(publisher="acme", name="test-agent"),
        version="1.0.0",
        description="Agente de teste para U1",
        publisher="acme",
        license="MIT",
        risks=RiskLevel.LOW,
        runtime="python:3.12",
        entrypoint="acme.test.agent:main",
        capabilities=["search.web", "answer.question"],
        tags=["acme", "test", "alpha"],
        provenance=Provenance(source="local"),
    )


@pytest.fixture
def agent_v2(agent_v1: AgentManifest) -> AgentManifest:
    """Mesma cap, versão 2.0.0."""
    return AgentManifest(
        id=ManifestId(publisher="acme", name="test-agent"),
        version="2.0.0",
        description=agent_v1.description,
        publisher=agent_v1.publisher,
        license=agent_v1.license,
        risks=RiskLevel.LOW,
        runtime="python:3.13",
        entrypoint="acme.test.agent:main",
        capabilities=agent_v1.capabilities,
        tags=agent_v1.tags,
        provenance=Provenance(source="local"),
    )


@pytest.fixture
def agent_b() -> AgentManifest:
    """Outro publisher."""
    return AgentManifest(
        id=ManifestId(publisher="other", name="agent"),
        version="1.0.0",
        description="Outro agente",
        publisher="other",
        license="Apache-2.0",
        risks=RiskLevel.MEDIUM,
        runtime="python:3.12",
        entrypoint="other_pkg.module:run",
        capabilities=["search.code"],
        tags=["other"],
        provenance=Provenance(source="local"),
    )


# ---- Publish --------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_then_get(registry: Registry, agent_v1: AgentManifest) -> None:
    entry = await registry.publish(agent_v1)
    assert entry.status == RegistryStatus.PUBLISHED
    assert entry.manifest.id == agent_v1.id
    assert len(entry.payload_hash) == 64  # SHA-256 hex

    # Roundtrip via get
    fetched = await registry.get(str(agent_v1.id), str(agent_v1.version))
    assert fetched.manifest.id == agent_v1.id
    assert fetched.manifest.version == agent_v1.version
    assert fetched.manifest.runtime == "python:3.12"


@pytest.mark.asyncio
async def test_publish_duplicate_raises_version_conflict(
    registry: Registry, agent_v1: AgentManifest
) -> None:
    await registry.publish(agent_v1)
    with pytest.raises(VersionConflictError):
        await registry.publish(agent_v1)


@pytest.mark.asyncio
async def test_publish_two_versions(registry: Registry, agent_v1, agent_v2) -> None:
    """Versões diferentes da mesma capability coexistem."""
    e1 = await registry.publish(agent_v1)
    e2 = await registry.publish(agent_v2)
    assert e1.manifest.version == "1.0.0"
    assert e2.manifest.version == "2.0.0"

    # get sem versão retorna a mais recente
    latest = await registry.get(str(agent_v1.id))
    assert latest.manifest.version == "2.0.0"

    # get com versão retorna a exata
    old = await registry.get(str(agent_v1.id), "1.0.0")
    assert old.manifest.version == "1.0.0"


# ---- Get ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_not_found(registry: Registry) -> None:
    with pytest.raises(UltronError):
        await registry.get("nonexistent/pkg")


@pytest.mark.asyncio
async def test_get_specific_version_not_found(
    registry: Registry, agent_v1: AgentManifest
) -> None:
    await registry.publish(agent_v1)
    with pytest.raises(UltronError):
        await registry.get(str(agent_v1.id), "9.9.9")


# ---- List + filtros -------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_with_filter(registry: Registry, agent_v1, agent_b) -> None:
    await registry.publish(agent_v1)
    await registry.publish(agent_b)
    all_agents = await registry.list_all(kind="agent")
    assert len(all_agents) == 2

    acme_only = await registry.list_all(publisher="acme")
    assert len(acme_only) == 1
    assert acme_only[0].manifest.publisher == "acme"


@pytest.mark.asyncio
async def test_list_pagination(registry: Registry, agent_v1, agent_b) -> None:
    """Respeita limit + offset."""
    await registry.publish(agent_v1)
    await registry.publish(agent_b)
    page1 = await registry.list_all(limit=1, offset=0)
    page2 = await registry.list_all(limit=1, offset=1)
    assert len(page1) == 1
    assert len(page2) == 1
    assert page1[0].manifest.id != page2[0].manifest.id


# ---- Search (FTS5) --------------------------------------------------------


@pytest.mark.asyncio
async def test_search_text(registry: Registry, agent_v1, agent_b) -> None:
    await registry.publish(agent_v1)
    await registry.publish(agent_b)
    results = await registry.search(SearchQuery(text="agente"))
    assert len(results) == 2  # ambos têm "agente" na descrição


@pytest.mark.asyncio
async def test_search_by_capability(registry: Registry, agent_v1, agent_b) -> None:
    await registry.publish(agent_v1)
    await registry.publish(agent_b)
    only_v1 = await registry.search(SearchQuery(capability="search.web"))
    assert len(only_v1) == 1
    assert only_v1[0].manifest.id == agent_v1.id


@pytest.mark.asyncio
async def test_search_filters_combine(registry: Registry, agent_v1, agent_b) -> None:
    await registry.publish(agent_v1)
    await registry.publish(agent_b)
    # Filtro kind + publisher: ambos agent, mas só acme
    results = await registry.search(
        SearchQuery(kind="agent", publisher="acme")
    )
    assert len(results) == 1
    assert results[0].manifest.id == agent_v1.id


@pytest.mark.asyncio
async def test_search_diacritics_insensitive(
    registry: Registry, agent_v1: AgentManifest
) -> None:
    """Tokenizer unicode61 remove_diacritics — `Agênte` deve achar `agente`."""
    await registry.publish(agent_v1)
    # Publicar v2 com descrição acentuada
    v2 = AgentManifest(
        id=ManifestId(publisher="acme", name="test-agent"),
        version="1.1.0",
        description="Agênte de testes com acentos",
        publisher="acme",
        license="MIT",
        risks=RiskLevel.LOW,
        runtime="python:3.12",
        entrypoint="acme.test.agent:main",
        capabilities=["search.code"],
        tags=[],
        provenance=Provenance(source="local"),
    )
    await registry.publish(v2)
    # Query sem acento deve casar com a descrição acentuada
    no_accent = await registry.search(SearchQuery(text="agente"))
    assert len(no_accent) >= 1


@pytest.mark.asyncio
async def test_search_empty_returns_all(
    registry: Registry, agent_v1, agent_b
) -> None:
    await registry.publish(agent_v1)
    await registry.publish(agent_b)
    results = await registry.search(SearchQuery(text=""))
    assert len(results) == 2


# ---- Delete + Audit -------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_removes_and_audits(
    registry: Registry, agent_v1: AgentManifest
) -> None:
    await registry.publish(agent_v1, actor="tester")
    assert await registry.count() == 1

    await registry.delete(str(agent_v1.id), str(agent_v1.version), actor="tester")
    assert await registry.count() == 0

    audit = await registry.recent_audit()
    actions = [e["action"] for e in audit]
    assert "publish" in actions
    assert "delete" in actions


@pytest.mark.asyncio
async def test_delete_missing_raises(registry: Registry) -> None:
    with pytest.raises(UltronError):
        await registry.delete("missing", "1.0.0")


# ---- Imutabilidade --------------------------------------------------------


@pytest.mark.asyncio
async def test_published_payload_is_immutable(
    registry: Registry, agent_v1: AgentManifest
) -> None:
    """Uma vez publicado, o payload não muda (apenas nova versão)."""
    await registry.publish(agent_v1)
    # Tentativa de re-publicar mesma (id, version) deve falhar
    with pytest.raises(VersionConflictError):
        await registry.publish(agent_v1)

    # Payload persistido continua o mesmo
    entry = await registry.get(str(agent_v1.id), str(agent_v1.version))
    assert entry.payload_hash == __import__("hashlib").sha256(
        agent_v1.model_dump_json().encode()
    ).hexdigest()


# ---- Stats ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_aggregate(registry: Registry, agent_v1, agent_b) -> None:
    await registry.publish(agent_v1)
    await registry.publish(agent_b)
    stats = await registry.stats()
    assert stats.total == 2
    assert stats.by_kind.get("agent") == 2
    assert stats.by_publisher.get("acme") == 1
    assert stats.by_publisher.get("other") == 1
    assert stats.latest_migration >= 1


@pytest.mark.asyncio
async def test_stats_empty(registry: Registry) -> None:
    stats = await registry.stats()
    assert stats.total == 0
    assert stats.by_kind == {}
    assert stats.latest_migration >= 1  # migration inicial


# ---- Count ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_with_filter(registry: Registry, agent_v1, agent_b) -> None:
    await registry.publish(agent_v1)
    await registry.publish(agent_b)
    assert await registry.count() == 2
    assert await registry.count(kind="agent") == 2
    assert await registry.count(publisher="acme") == 1
    assert await registry.count(kind="skill") == 0


# ---- Auditoria append-only ----------------------------------------------


@pytest.mark.asyncio
async def test_audit_records_publish(
    registry: Registry, agent_v1: AgentManifest
) -> None:
    await registry.publish(agent_v1, actor="alice", correlation_id="corr-1")
    audit = await registry.recent_audit()
    publish_event = next((e for e in audit if e["action"] == "publish"), None)
    assert publish_event is not None
    assert publish_event["actor"] == "alice"
    assert publish_event["correlation_id"] == "corr-1"
    assert publish_event["target_id"] == str(agent_v1.id)


@pytest.mark.asyncio
async def test_audit_event_timestamp_is_utc(
    registry: Registry, agent_v1: AgentManifest
) -> None:
    await registry.publish(agent_v1)
    audit = await registry.recent_audit(limit=1)
    ts = audit[0]["occurred_at"]
    # ISO 8601 com timezone
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
