"""Revogação desativa a capability e seus dependentes transitivos."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultron.core.base import IntegrityInfo, Provenance, RiskLevel
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.lifecycle import LifecycleManager, LifecycleStore
from ultron.lockfile import LockedCapability, LockfileStore, UltronLockfile
from ultron.registry import Registry, RegistryStatus
from ultron.revocation import RevocationManager

pytestmark = pytest.mark.integration


def manifest(name: str) -> SkillManifest:
    content = name.encode()
    return SkillManifest(
        id=ManifestId("acme", name),
        version="1.0.0",
        publisher="acme",
        description=name,
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        provenance=Provenance(source="local"),
        integrity=IntegrityInfo(digest=hashlib.sha256(content).hexdigest()),
    )


def locked(name: str, dependencies: tuple[str, ...] = ()) -> LockedCapability:
    return LockedCapability(
        id=f"acme/{name}",
        version="1.0.0",
        kind="skill",
        digest=hashlib.sha256(name.encode()).hexdigest(),
        dependencies=dependencies,
    )


@pytest.mark.asyncio
async def test_revocation_propagates_and_preserves_reproducible_files(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.db")
    await registry.start()
    try:
        for name in ("leaf", "middle", "root", "independent"):
            await registry.publish(manifest(name))
        lockfile = UltronLockfile(
            root="acme/root@1.0.0",
            capabilities=(
                locked("leaf"),
                locked("middle", ("acme/leaf@1.0.0",)),
                locked("root", ("acme/middle@1.0.0",)),
                locked("independent"),
            ),
        )
        lockfiles = LockfileStore(tmp_path / "ultron.lock")
        lockfiles.write(lockfile)
        lifecycle = LifecycleManager(lockfiles, LifecycleStore(tmp_path / "ultron.state"))
        for capability_id in ("acme/leaf", "acme/middle", "acme/root", "acme/independent"):
            lifecycle.activate(capability_id)

        revoked = await registry.revoke(
            "acme/leaf",
            "1.0.0",
            actor="security-admin",
            correlation_id="revoke-1",
        )
        report = await RevocationManager(registry, lockfiles, lifecycle).propagate()

        assert revoked.status == RegistryStatus.REVOKED
        assert report.revoked == ("acme/leaf@1.0.0",)
        assert report.impacted == ("acme/leaf", "acme/middle", "acme/root")
        assert report.deactivated == report.impacted
        state = lifecycle.reconcile()
        active = {item.id for item in state.capabilities if item.active}
        assert active == {"acme/independent"}
        assert lockfiles.read() == lockfile
        audit = await registry.recent_audit(limit=1)
        assert audit[0]["action"] == "capability_revoked"
        assert audit[0]["correlation_id"] == "revoke-1"
    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_propagation_without_installation_is_idempotent(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.db")
    await registry.start()
    try:
        lockfiles = LockfileStore(tmp_path / "missing.lock")
        lifecycle = LifecycleManager(lockfiles, LifecycleStore(tmp_path / "state"))
        report = await RevocationManager(registry, lockfiles, lifecycle).propagate()
        assert report.revoked == report.impacted == report.deactivated == ()
    finally:
        await registry.close()
