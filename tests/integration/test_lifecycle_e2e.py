"""Ciclo U2 completo: referência → instalação → ativação → upgrade → rollback → coleta."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultron.core.base import IntegrityInfo, Provenance, RiskLevel
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.installer import Installer
from ultron.journal import LockfileJournal
from ultron.lifecycle import LifecycleManager, LifecycleStore
from ultron.lockfile import LockfileStore
from ultron.references import MappingReferenceAdapter
from ultron.registry import Registry
from ultron.store import PackageStore

pytestmark = pytest.mark.integration


def manifest(version: str, content: bytes) -> SkillManifest:
    return SkillManifest(
        id=ManifestId("acme", "root"),
        version=version,
        publisher="acme",
        description="Root skill",
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        provenance=Provenance(source="local"),
        integrity=IntegrityInfo(digest=hashlib.sha256(content).hexdigest()),
    )


@pytest.mark.asyncio
async def test_complete_reversible_lifecycle(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.db")
    await registry.start()
    try:
        packages = PackageStore(tmp_path / "packages")
        lockfiles = LockfileStore(tmp_path / "ultron.lock")
        journal = LockfileJournal(tmp_path / "journal")
        installer = Installer(registry, packages, lockfiles, journal)
        lifecycle = LifecycleManager(lockfiles, LifecycleStore(tmp_path / "ultron.state"))
        v1_bytes, v2_bytes = b"version-one", b"version-two"
        v1, v2 = manifest("1.0.0", v1_bytes), manifest("2.0.0", v2_bytes)

        first = await installer.install_from(
            v1, MappingReferenceAdapter({("acme/root", "1.0.0"): v1_bytes})
        )
        assert lifecycle.activate("acme/root").capabilities[0].active

        second = await installer.install_from(
            v2, MappingReferenceAdapter({("acme/root", "2.0.0"): v2_bytes})
        )
        assert second.root == "acme/root@2.0.0"
        assert not lifecycle.reconcile().capabilities[0].active

        restored = lifecycle.rollback(journal.list()[0], journal)
        assert lockfiles.read() == first
        assert restored.capabilities[0].version == "1.0.0"
        assert packages.collect_with_history(lockfiles, journal, dry_run=False).removed == ()
    finally:
        await registry.close()
