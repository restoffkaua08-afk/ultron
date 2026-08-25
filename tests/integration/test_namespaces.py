from datetime import UTC, datetime, timedelta

import pytest

from ultron.core.errors import PermissionDeniedError, UltronError
from ultron.data import NamespaceContext, NamespaceStore


@pytest.mark.asyncio
async def test_organizations_are_strictly_isolated(tmp_path):
    async with NamespaceStore.open(tmp_path / "data.db") as store:
        alpha = NamespaceContext("org-alpha", "claude")
        beta = NamespaceContext("org-beta", "codex")
        await store.put(alpha, "memory", "fact-1", {"value": "alpha"})
        with pytest.raises(UltronError):
            await store.get(beta, "memory", "fact-1")
        assert await store.list(beta, "memory") == []


@pytest.mark.asyncio
async def test_lineage_is_scoped_and_requires_existing_records(tmp_path):
    async with NamespaceStore.open(tmp_path / "data.db") as store:
        context = NamespaceContext("org-alpha", "zane")
        await store.put(context, "knowledge", "source", {"kind": "document"})
        await store.put(context, "knowledge", "summary", {"kind": "derived"})
        await store.add_lineage(context, "knowledge", "source", "summary", "derived-from")
        with pytest.raises(PermissionDeniedError):
            await store.add_lineage(context, "knowledge", "missing", "summary", "derived-from")


def test_context_and_namespace_identifiers_are_validated():
    with pytest.raises(ValueError):
        NamespaceContext("../other-org", "claude")


@pytest.mark.asyncio
async def test_graph_projection_is_deterministic_and_depth_limited(tmp_path):
    async with NamespaceStore.open(tmp_path / "data.db") as store:
        context = NamespaceContext("org-alpha", "claude")
        for key in ("a", "b", "c", "isolated"):
            await store.put(context, "knowledge", key, {"key": key})
        await store.add_lineage(context, "knowledge", "a", "b", "derived-from")
        await store.add_lineage(context, "knowledge", "b", "c", "derived-from")

        graph = await store.project_graph(context, "knowledge", roots=("a",), max_depth=1)

        assert [node.key for node in graph.nodes] == ["a", "b"]
        assert [(edge.source, edge.target) for edge in graph.edges] == [("a", "b")]


@pytest.mark.asyncio
async def test_graph_projection_never_crosses_organization(tmp_path):
    async with NamespaceStore.open(tmp_path / "data.db") as store:
        alpha = NamespaceContext("org-alpha", "claude")
        beta = NamespaceContext("org-beta", "claude")
        await store.put(alpha, "knowledge", "private", {"secret": True})
        await store.put(beta, "knowledge", "public", {"secret": False})

        graph = await store.project_graph(beta, "knowledge")

        assert [node.key for node in graph.nodes] == ["public"]
        assert graph.edges == ()


@pytest.mark.asyncio
async def test_retention_is_planned_then_applied_without_touching_other_org(tmp_path):
    now = datetime(2026, 8, 25, tzinfo=UTC)
    async with NamespaceStore.open(tmp_path / "data.db") as store:
        alpha = NamespaceContext("org-alpha", "claude")
        beta = NamespaceContext("org-beta", "claude")
        await store.put(alpha, "memory", "expired", {}, expires_at=now - timedelta(seconds=1))
        await store.put(alpha, "memory", "current", {}, expires_at=now + timedelta(days=1))
        await store.put(beta, "memory", "expired", {}, expires_at=now - timedelta(seconds=1))
        await store.add_lineage(alpha, "memory", "expired", "current", "related")

        plan = await store.plan_retention(alpha, "memory", now=now)
        assert plan.expired_keys == ("expired",)
        assert await store.list(alpha, "memory")
        assert await store.apply_retention(alpha, plan) == 1
        assert [record.key for record in await store.list(alpha, "memory")] == ["current"]
        assert [record.key for record in await store.list(beta, "memory")] == ["expired"]


@pytest.mark.asyncio
async def test_retention_plan_cannot_cross_organization(tmp_path):
    async with NamespaceStore.open(tmp_path / "data.db") as store:
        alpha = NamespaceContext("org-alpha", "claude")
        beta = NamespaceContext("org-beta", "claude")
        plan = await store.plan_retention(alpha, "memory")
        with pytest.raises(PermissionDeniedError):
            await store.apply_retention(beta, plan)
