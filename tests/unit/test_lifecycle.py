"""Lifecycle explícito e reconciliado com o lockfile."""

from pathlib import Path

import pytest

from ultron.core.errors import CapabilityNotInstalledError, InstallationError
from ultron.lifecycle import LifecycleManager, LifecycleStore
from ultron.lockfile import LockedCapability, LockfileStore, UltronLockfile


def manager(tmp_path: Path, lockfile: UltronLockfile | None = None) -> LifecycleManager:
    lockfiles = LockfileStore(tmp_path / "ultron.lock")
    if lockfile is not None:
        lockfiles.write(lockfile)
    return LifecycleManager(lockfiles, LifecycleStore(tmp_path / "ultron.state"))


def installed(version: str = "1.0.0") -> UltronLockfile:
    return UltronLockfile(
        root=f"acme/root@{version}",
        capabilities=(
            LockedCapability(
                id="acme/root",
                version=version,
                kind="skill",
                digest="a" * 64,
            ),
        ),
    )


def test_reconcile_creates_inactive_state(tmp_path: Path) -> None:
    state = manager(tmp_path, installed()).reconcile()

    assert state.capabilities[0].active is False
    assert len(state.lock_sha256) == 64


def test_activate_and_deactivate_are_explicit_and_idempotent(tmp_path: Path) -> None:
    lifecycle = manager(tmp_path, installed())

    assert lifecycle.activate("acme/root").capabilities[0].active is True
    assert lifecycle.activate("acme/root").capabilities[0].active is True
    assert lifecycle.deactivate("acme/root").capabilities[0].active is False


def test_version_change_resets_activation(tmp_path: Path) -> None:
    lifecycle = manager(tmp_path, installed())
    lifecycle.activate("acme/root")
    lifecycle.lockfiles.write(installed("2.0.0"))

    assert lifecycle.reconcile().capabilities[0].active is False


def test_unknown_capability_is_rejected(tmp_path: Path) -> None:
    lifecycle = manager(tmp_path, installed())

    with pytest.raises(CapabilityNotInstalledError):
        lifecycle.activate("acme/missing")


def test_lifecycle_requires_installation(tmp_path: Path) -> None:
    with pytest.raises(InstallationError, match="lockfile"):
        manager(tmp_path).reconcile()
