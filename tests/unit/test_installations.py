"""Persistência e isolamento do lifecycle por consumer."""

from __future__ import annotations

from pathlib import Path

import pytest

from ultron.core.errors import InstallationError, UnsafeRemovalError
from ultron.installations import ConsumerInstallationStore, InstallationRecord

_DIGEST = "a" * 64


@pytest.fixture
async def store(tmp_path: Path):
    value = ConsumerInstallationStore(tmp_path / "installations.db")
    await value.start()
    try:
        yield value
    finally:
        await value.close()


def _plan() -> tuple[InstallationRecord, ...]:
    return (
        InstallationRecord("acme/base", "1.0.0", "skill", _DIGEST),
        InstallationRecord(
            "acme/root",
            "1.0.0",
            "agent",
            _DIGEST,
            dependencies=("acme/base",),
            is_root=True,
        ),
    )


async def test_installation_is_isolated_by_organization_and_consumer(store) -> None:
    installed = await store.install("org-a", "claude", _plan())
    assert [record.capability_id for record in installed] == ["acme/base", "acme/root"]
    assert await store.list("org-b", "claude") == ()
    assert await store.list("org-a", "codex") == ()


async def test_activation_is_persistent_and_idempotent(store) -> None:
    await store.install("org-a", "claude", _plan())
    first = await store.set_active("org-a", "claude", "acme/base", active=True)
    second = await store.set_active("org-a", "claude", "acme/base", active=True)
    assert first.active is True
    assert second.active is True
    assert (await store.status("org-a", "claude", "acme/base")).active is True


async def test_removal_blocks_root_active_and_dependency_in_use(store) -> None:
    await store.install("org-a", "claude", _plan())
    with pytest.raises(UnsafeRemovalError, match="raiz"):
        await store.remove("org-a", "claude", "acme/root")
    with pytest.raises(UnsafeRemovalError, match="dependentes"):
        await store.remove("org-a", "claude", "acme/base")


async def test_version_conflict_rolls_back_entire_plan(store) -> None:
    await store.install("org-a", "claude", _plan())
    conflicting = (
        InstallationRecord("acme/other", "1.0.0", "skill", _DIGEST),
        InstallationRecord("acme/root", "2.0.0", "agent", _DIGEST, is_root=True),
    )
    with pytest.raises(InstallationError, match="conflita"):
        await store.install("org-a", "claude", conflicting)
    assert {item.capability_id for item in await store.list("org-a", "claude")} == {
        "acme/base",
        "acme/root",
    }


@pytest.mark.parametrize("organization_id,consumer_id", [("", "claude"), ("org", "../bad")])
async def test_invalid_scope_is_rejected(store, organization_id: str, consumer_id: str) -> None:
    with pytest.raises(ValueError, match="inválido"):
        await store.list(organization_id, consumer_id)
