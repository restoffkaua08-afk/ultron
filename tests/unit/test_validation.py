"""Pipeline de admissão U3: falha segura sem executar artefatos."""

from __future__ import annotations

import hashlib

from ultron.core.base import IntegrityInfo, Permission, Provenance, RiskLevel
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.validation import ValidationPipeline, ValidationSeverity


def manifest(
    content: bytes,
    *,
    provenance: Provenance | None = None,
    integrity: bool = True,
    risk: RiskLevel = RiskLevel.SAFE,
    permissions: tuple[Permission, ...] = (),
) -> SkillManifest:
    return SkillManifest(
        id=ManifestId("acme", "validator"),
        version="1.0.0",
        publisher="acme",
        description="Validation fixture",
        risks=risk,
        skill_type="prompt",
        permissions=permissions,
        provenance=provenance or Provenance(source="local"),
        integrity=(
            IntegrityInfo(digest=hashlib.sha256(content).hexdigest()) if integrity else None
        ),
    )


def codes(decision) -> set[str]:
    return {finding.code for finding in decision.findings}


def test_valid_local_artifact_is_admitted() -> None:
    content = b"verified"
    decision = ValidationPipeline().validate(manifest(content), content)

    assert decision.accepted
    assert not decision.quarantined
    assert decision.artifact_sha256 == hashlib.sha256(content).hexdigest()


def test_missing_or_mismatched_integrity_is_quarantined() -> None:
    pipeline = ValidationPipeline()

    missing = pipeline.validate(manifest(b"expected", integrity=False), b"expected")
    mismatch = pipeline.validate(manifest(b"expected"), b"different")

    assert missing.quarantined and "INTEGRITY_MISSING" in codes(missing)
    assert mismatch.quarantined and "INTEGRITY_MISMATCH" in codes(mismatch)


def test_mutable_supply_chain_references_are_quarantined() -> None:
    content = b"artifact"
    git = manifest(
        content,
        provenance=Provenance(source="git", repository="https://example.test/repo", commit="main"),
    )
    oci = manifest(
        content,
        provenance=Provenance(source="oci", repository="registry.test/pkg:latest"),
    )

    assert "GIT_PROVENANCE_UNPINNED" in codes(ValidationPipeline().validate(git, content))
    assert "OCI_PROVENANCE_UNPINNED" in codes(ValidationPipeline().validate(oci, content))


def test_understated_risk_is_blocked_and_high_risk_requires_approval() -> None:
    content = b"artifact"
    sensitive = (Permission(capability="process.spawn"),)

    understated = ValidationPipeline().validate(manifest(content, permissions=sensitive), content)
    declared = ValidationPipeline().validate(
        manifest(content, risk=RiskLevel.HIGH, permissions=sensitive), content
    )

    assert understated.quarantined and "RISK_UNDERSTATED" in codes(understated)
    assert declared.accepted
    assert declared.findings[0].severity == ValidationSeverity.WARNING
    assert "EXPLICIT_APPROVAL_REQUIRED" in codes(declared)
