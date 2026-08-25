"""Promoção exige revalidação, assinatura, admin e auditoria."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultron.core.base import IntegrityInfo, Provenance, RiskLevel
from ultron.core.errors import QuarantinePromotionError
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.quarantine import QuarantineManager, SecurityPrincipal
from ultron.registry import Registry, RegistryStatus
from ultron.supply_chain import PublisherTrustStore, generate_signing_key, sign_artifact
from ultron.validation import ValidationPipeline

pytestmark = pytest.mark.integration


def manifest(content: bytes) -> SkillManifest:
    return SkillManifest(
        id=ManifestId("acme", "promoted"),
        version="1.0.0",
        publisher="acme",
        description="Promotion fixture",
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        provenance=Provenance(
            source="git",
            repository="https://example.test/acme/promoted",
            commit="a" * 40,
        ),
        integrity=IntegrityInfo(digest=hashlib.sha256(content).hexdigest()),
    )


@pytest.mark.asyncio
async def test_promotion_fails_closed_then_succeeds_with_admin(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.db")
    await registry.start()
    try:
        content = b"verified artifact"
        item = manifest(content)
        await registry.publish(item, status=RegistryStatus.QUARANTINED)
        manager = QuarantineManager(registry, ValidationPipeline())
        private = generate_signing_key()
        trust = PublisherTrustStore(tmp_path / "trust.json")
        trust.register("acme", private.public_key())
        signature = sign_artifact(private, item, content)

        with pytest.raises(QuarantinePromotionError, match="security_admin"):
            await manager.promote(
                "acme/promoted",
                "1.0.0",
                content,
                principal=SecurityPrincipal("reviewer", frozenset({"viewer"})),
                correlation_id="promotion-1",
                signature=signature,
                trust_store=trust,
            )
        with pytest.raises(QuarantinePromotionError, match="revalidação"):
            await manager.promote(
                "acme/promoted",
                "1.0.0",
                b"tampered",
                principal=SecurityPrincipal("admin", frozenset({"security_admin"})),
                correlation_id="promotion-2",
                signature=signature,
                trust_store=trust,
            )
        assert (await registry.get("acme/promoted", "1.0.0")).status == (RegistryStatus.QUARANTINED)

        result = await manager.promote(
            "acme/promoted",
            "1.0.0",
            content,
            principal=SecurityPrincipal("admin", frozenset({"security_admin"})),
            correlation_id="promotion-3",
            signature=signature,
            trust_store=trust,
        )

        assert result.entry.status == RegistryStatus.PUBLISHED
        assert result.decision.accepted
        audit = await registry.recent_audit(limit=1)
        assert audit[0]["action"] == "quarantine_promoted"
        assert audit[0]["actor"] == "admin"
        assert audit[0]["correlation_id"] == "promotion-3"

        with pytest.raises(QuarantinePromotionError, match="Somente versões"):
            await manager.promote(
                "acme/promoted",
                "1.0.0",
                content,
                principal=SecurityPrincipal("admin", frozenset({"security_admin"})),
                correlation_id="promotion-4",
                signature=signature,
                trust_store=trust,
            )
    finally:
        await registry.close()
