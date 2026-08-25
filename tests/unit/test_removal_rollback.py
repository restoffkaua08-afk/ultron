"""Remoção segura e rollback imutável."""

from pathlib import Path

import pytest

from ultron.core.errors import (
    CapabilityNotInstalledError,
    CheckpointNotFoundError,
    IntegrityError,
    UnsafeRemovalError,
)
from ultron.journal import LockfileJournal
from ultron.lifecycle import LifecycleManager, LifecycleStore
from ultron.lockfile import LockedCapability, LockfileStore, UltronLockfile


def graph() -> UltronLockfile:
    return UltronLockfile(
        root="acme/root@1.0.0",
        capabilities=(
            LockedCapability(id="acme/leaf", version="1.0.0", kind="skill", digest="a" * 64),
            LockedCapability(
                id="acme/root",
                version="1.0.0",
                kind="agent",
                digest="b" * 64,
                dependencies=("acme/leaf@1.0.0",),
            ),
            LockedCapability(id="acme/unused", version="1.0.0", kind="skill", digest="c" * 64),
        ),
    )


def services(tmp_path: Path) -> tuple[LifecycleManager, LockfileJournal]:
    lockfiles = LockfileStore(tmp_path / "ultron.lock")
    lockfiles.write(graph())
    lifecycle = LifecycleManager(lockfiles, LifecycleStore(tmp_path / "ultron.state"))
    return lifecycle, LockfileJournal(tmp_path / "journal")


def test_remove_unused_capability_creates_checkpoint(tmp_path: Path) -> None:
    lifecycle, journal = services(tmp_path)

    state = lifecycle.remove("acme/unused", journal)

    assert [item.id for item in state.capabilities] == ["acme/leaf", "acme/root"]
    assert len(journal.list()) == 1


def test_remove_rejects_root_dependency_active_and_missing(tmp_path: Path) -> None:
    lifecycle, journal = services(tmp_path)

    with pytest.raises(UnsafeRemovalError, match="raiz"):
        lifecycle.remove("acme/root", journal)
    with pytest.raises(UnsafeRemovalError, match="dependentes"):
        lifecycle.remove("acme/leaf", journal)
    lifecycle.activate("acme/unused")
    with pytest.raises(UnsafeRemovalError, match="Desative"):
        lifecycle.remove("acme/unused", journal)
    with pytest.raises(CapabilityNotInstalledError):
        lifecycle.remove("acme/missing", journal)

    assert journal.list() == ()


def test_rollback_restores_lockfile_and_checkpoints_current_state(tmp_path: Path) -> None:
    lifecycle, journal = services(tmp_path)
    lifecycle.remove("acme/unused", journal)
    original_checkpoint = journal.list()[0]

    state = lifecycle.rollback(original_checkpoint, journal)

    assert [item.id for item in state.capabilities] == [
        "acme/leaf",
        "acme/root",
        "acme/unused",
    ]
    assert len(journal.list()) == 2


def test_missing_and_tampered_checkpoint_are_rejected(tmp_path: Path) -> None:
    lifecycle, journal = services(tmp_path)
    with pytest.raises(CheckpointNotFoundError):
        lifecycle.rollback("d" * 64, journal)

    digest = journal.checkpoint(graph())
    path = tmp_path / "journal" / digest
    path.chmod(0o644)
    path.write_bytes(b"tampered")

    with pytest.raises(IntegrityError):
        lifecycle.rollback(digest, journal)
