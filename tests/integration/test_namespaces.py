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
