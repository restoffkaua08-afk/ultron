"""Quarentena registrada e excluída de instalação/resolução."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultron.core.base import DependencyRef, IntegrityInfo, Provenance, RiskLevel
from ultron.core.errors import DependencyResolutionError, InstallationError
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.installer import Installer
from ultron.lockfile import LockfileStore
from ultron.registry import Registry, RegistryStatus
from ultron.resolver import DependencyResolver
from ultron.store import PackageStore
from ultron.validation import ValidationPipeline

pytestmark = pytest.mark.integration


def skill(name: str, content: bytes, *, dependencies=()) -> SkillManifest:
    return SkillManifest(
        id=ManifestId("acme", name),
        version="1.0.0",
        publisher="acme",
        description=name,
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        dependencies=dependencies,
        provenance=Provenance(source="local"),
        integrity=IntegrityInfo(digest=hashlib.sha256(content).hexdigest()),
    )


@pytest.mark.asyncio
async def test_quarantined_version_is_audited_and_never_installable(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.db")
    await registry.start()
    try:
        blocked_bytes = b"blocked"
        blocked = skill("blocked", blocked_bytes)
        decision = ValidationPipeline().validate(blocked, b"tampered")
        assert decision.quarantined
        entry = await registry.publish(blocked, status=RegistryStatus.QUARANTINED)
        assert entry.status == RegistryStatus.QUARANTINED

        root = skill(
            "root",
            b"root",
            dependencies=(DependencyRef(id=ManifestId("acme", "blocked"), version_range="1.0.0"),),
        )
        with pytest.raises(DependencyResolutionError):
            await DependencyResolver(registry).resolve(root)

        installer = Installer(
            registry,
            PackageStore(tmp_path / "packages"),
            LockfileStore(tmp_path / "ultron.lock"),
        )
        with pytest.raises(InstallationError, match="não instalável"):
            await installer._manifest("acme/blocked", "1.0.0")

        assert (await registry.recent_audit(limit=1))[0]["action"] == "quarantine"
    finally:
        await registry.close()
