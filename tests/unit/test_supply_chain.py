"""Assinaturas Ed25519, confiança persistida e revogação."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ultron.core.base import IntegrityInfo, Provenance, RiskLevel
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.supply_chain import PublisherTrustStore, generate_signing_key, sign_artifact
from ultron.validation import ValidationPipeline


def manifest(content: bytes, *, source: str = "git") -> SkillManifest:
    provenance = (
        Provenance(
            source="git",
            repository="https://example.test/acme/skill",
            commit="a" * 40,
        )
        if source == "git"
        else Provenance(source="local")
    )
    return SkillManifest(
        id=ManifestId("acme", "signed-skill"),
        version="1.0.0",
        publisher="acme",
        description="Signed skill",
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        provenance=provenance,
        integrity=IntegrityInfo(digest=hashlib.sha256(content).hexdigest()),
    )


def codes(decision) -> set[str]:
    return {finding.code for finding in decision.findings}


def test_signature_binds_publisher_manifest_and_artifact(tmp_path: Path) -> None:
    content = b"signed artifact"
    item = manifest(content)
    private = generate_signing_key()
    envelope = sign_artifact(private, item, content)
    trust = PublisherTrustStore(tmp_path / "trust.json")
    trusted = trust.register("acme", private.public_key())

    assert envelope.key_id == trusted.key_id
    assert trust.verify(item, content, envelope)
    assert not trust.verify(item, b"tampered", envelope)
    assert PublisherTrustStore(tmp_path / "trust.json").verify(item, content, envelope)


def test_revoked_key_fails_closed(tmp_path: Path) -> None:
    content = b"artifact"
    item = manifest(content)
    private = generate_signing_key()
    trust = PublisherTrustStore(tmp_path / "trust.json")
    trusted = trust.register("acme", private.public_key())
    envelope = sign_artifact(private, item, content)

    trust.revoke("acme", trusted.key_id)

    assert not trust.verify(item, content, envelope)


def test_remote_signature_is_required_by_admission_pipeline(tmp_path: Path) -> None:
    content = b"artifact"
    item = manifest(content)
    private = generate_signing_key()
    trust = PublisherTrustStore(tmp_path / "trust.json")
    trust.register("acme", private.public_key())

    unsigned = ValidationPipeline().validate(item, content)
    signed = ValidationPipeline().validate(
        item,
        content,
        signature=sign_artifact(private, item, content),
        trust_store=trust,
    )

    assert unsigned.quarantined and "SIGNATURE_MISSING" in codes(unsigned)
    assert signed.accepted and not signed.quarantined


def test_local_unsigned_artifact_remains_compatible_with_warning() -> None:
    content = b"local artifact"
    decision = ValidationPipeline().validate(manifest(content, source="local"), content)

    assert decision.accepted
    assert "SIGNATURE_MISSING" in codes(decision)
