"""Referências confinadas e coleta conservadora de conteúdo."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultron.core.base import IntegrityInfo, Provenance, RiskLevel
from ultron.core.errors import ArtifactNotFoundError, InstallationError
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.journal import LockfileJournal
from ultron.lockfile import LockedCapability, LockfileStore, UltronLockfile
from ultron.references import LocalReferenceAdapter, MappingReferenceAdapter
from ultron.store import PackageStore


def manifest(repository: str | None = None) -> SkillManifest:
    return SkillManifest(
        id=ManifestId("acme", "skill"),
        version="1.0.0",
        publisher="acme",
        description="Skill",
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        provenance=Provenance(source="local", repository=repository),
        integrity=IntegrityInfo(digest=hashlib.sha256(b"artifact").hexdigest()),
    )


def lockfile(digest: str) -> UltronLockfile:
    return UltronLockfile(
        root="acme/skill@1.0.0",
        capabilities=(
            LockedCapability(id="acme/skill", version="1.0.0", kind="skill", digest=digest),
        ),
    )


def test_mapping_reference_is_explicit_about_missing_artifacts() -> None:
    item = manifest()
    adapter = MappingReferenceAdapter({("acme/skill", "1.0.0"): b"artifact"})

    assert adapter.fetch(item) == b"artifact"
    with pytest.raises(ArtifactNotFoundError):
        MappingReferenceAdapter({}).fetch(item)


def test_local_reference_is_confined_to_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "skill.pkg").write_bytes(b"artifact")
    adapter = LocalReferenceAdapter(allowed)

    assert adapter.fetch(manifest("skill.pkg")) == b"artifact"
    with pytest.raises(InstallationError):
        adapter.fetch(manifest("../outside.pkg"))
    with pytest.raises(ArtifactNotFoundError):
        adapter.fetch(manifest("missing.pkg"))


def test_collection_defaults_to_dry_run_and_protects_history(tmp_path: Path) -> None:
    packages = PackageStore(tmp_path / "packages")
    current_digest = packages.put(b"current").digest
    historic_digest = packages.put(b"historic").digest
    orphan_digest = packages.put(b"orphan").digest
    lockfiles = LockfileStore(tmp_path / "ultron.lock")
    lockfiles.write(lockfile(current_digest))
    journal = LockfileJournal(tmp_path / "journal")
    journal.checkpoint(lockfile(historic_digest))

    simulated = packages.collect_with_history(lockfiles, journal)

    assert simulated.protected == tuple(sorted((current_digest, historic_digest)))
    assert simulated.candidates == (orphan_digest,)
    assert simulated.removed == ()
    assert packages.contains(orphan_digest)

    applied = packages.collect_with_history(lockfiles, journal, dry_run=False)
    assert applied.removed == (orphan_digest,)
    assert not packages.contains(orphan_digest)
    assert packages.contains(current_digest)
    assert packages.contains(historic_digest)
