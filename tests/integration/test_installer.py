"""Instalação transacional: resolver → verificar → store → lockfile."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from ultron.core.base import DependencyRef, IntegrityInfo, Provenance, RiskLevel
from ultron.core.errors import InstallationError, IntegrityError
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.installer import Installer
from ultron.journal import LockfileJournal
from ultron.lockfile import LockfileStore, UltronLockfile
from ultron.registry import Registry
from ultron.store import PackageStore

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def registry(tmp_path: Path) -> AsyncIterator[Registry]:
    instance = Registry(tmp_path / "registry.db")
    await instance.start()
    try:
        yield instance
    finally:
        await instance.close()


def manifest(
    name: str,
    content: bytes,
    *,
    dependencies: tuple[DependencyRef, ...] = (),
    integrity: bool = True,
) -> SkillManifest:
    digest = hashlib.sha256(content).hexdigest()
    return SkillManifest(
        id=ManifestId("acme", name),
        version="1.0.0",
        publisher="acme",
        description=f"Skill {name}",
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        dependencies=dependencies,
        provenance=Provenance(source="local"),
        integrity=IntegrityInfo(digest=digest) if integrity else None,
    )


def dependency(name: str) -> DependencyRef:
    return DependencyRef(id=ManifestId("acme", name), version_range="1.0.0")


def installer(registry: Registry, tmp_path: Path) -> Installer:
    return Installer(
        registry,
        PackageStore(tmp_path / "packages"),
        LockfileStore(tmp_path / "ultron.lock"),
    )


@pytest.mark.asyncio
async def test_installs_verified_graph_and_writes_deterministic_lock(
    registry: Registry, tmp_path: Path
) -> None:
    leaf_bytes = b"leaf package"
    root_bytes = b"root package"
    leaf = manifest("leaf", leaf_bytes)
    root = manifest("root", root_bytes, dependencies=(dependency("leaf"),))
    await registry.publish(leaf)
    service = installer(registry, tmp_path)

    result = await service.install(
        root,
        {("acme/leaf", "1.0.0"): leaf_bytes, ("acme/root", "1.0.0"): root_bytes},
    )

    assert [item.id for item in result.capabilities] == ["acme/leaf", "acme/root"]
    assert result.capabilities[1].dependencies == ("acme/leaf@1.0.0",)
    assert LockfileStore(tmp_path / "ultron.lock").read() == result


@pytest.mark.asyncio
async def test_failure_preserves_previous_lockfile(registry: Registry, tmp_path: Path) -> None:
    lock_store = LockfileStore(tmp_path / "ultron.lock")
    previous = UltronLockfile(root="acme/old@1.0.0", capabilities=())
    lock_store.write(previous)
    root_bytes = b"root"
    root = manifest("root", root_bytes)
    service = Installer(registry, PackageStore(tmp_path / "packages"), lock_store)

    with pytest.raises(IntegrityError):
        await service.install(root, {("acme/root", "1.0.0"): b"tampered"})

    assert lock_store.read() == previous


@pytest.mark.asyncio
async def test_successful_replacement_checkpoints_previous_lockfile(
    registry: Registry, tmp_path: Path
) -> None:
    lock_store = LockfileStore(tmp_path / "ultron.lock")
    previous = UltronLockfile(root="acme/old@1.0.0", capabilities=())
    lock_store.write(previous)
    journal = LockfileJournal(tmp_path / "journal")
    root_bytes = b"root"
    root = manifest("root", root_bytes)
    service = Installer(
        registry,
        PackageStore(tmp_path / "packages"),
        lock_store,
        journal,
    )

    result = await service.install(root, {("acme/root", "1.0.0"): root_bytes})

    checkpoints = journal.list()
    assert len(checkpoints) == 1
    assert journal.get(checkpoints[0]) == previous
    assert lock_store.read() == result


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing-artifact", "missing-integrity"])
async def test_incomplete_package_is_rejected_without_lock_change(
    registry: Registry, tmp_path: Path, case: str
) -> None:
    content = b"root"
    root = manifest("root", content, integrity=case != "missing-integrity")
    artifacts = {} if case == "missing-artifact" else {("acme/root", "1.0.0"): content}

    with pytest.raises(InstallationError):
        await installer(registry, tmp_path).install(root, artifacts)

    assert not (tmp_path / "ultron.lock").exists()
