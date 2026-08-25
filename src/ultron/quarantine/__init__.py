"""Promoção controlada de quarentena com revalidação e auditoria."""

from __future__ import annotations

from dataclasses import dataclass

from ultron.core.errors import QuarantinePromotionError
from ultron.registry import Registry, RegistryEntry, RegistryStatus
from ultron.supply_chain import PublisherTrustStore, SignatureEnvelope
from ultron.validation import AdmissionDecision, ValidationPipeline


@dataclass(frozen=True, slots=True)
class SecurityPrincipal:
    """Principal autenticado pelo chamador; o núcleo apenas aplica os roles."""

    subject: str
    roles: frozenset[str]

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("subject de segurança não pode ser vazio")


@dataclass(frozen=True, slots=True)
class PromotionResult:
    entry: RegistryEntry
    decision: AdmissionDecision
    promoted_by: str
    correlation_id: str


class QuarantineManager:
    """Único fluxo autorizado para mover `quarantined` para `published`."""

    def __init__(self, registry: Registry, pipeline: ValidationPipeline) -> None:
        self.registry = registry
        self.pipeline = pipeline

    async def promote(
        self,
        manifest_id: str,
        version: str,
        artifact: bytes,
        *,
        principal: SecurityPrincipal,
        correlation_id: str,
        signature: SignatureEnvelope | None = None,
        trust_store: PublisherTrustStore | None = None,
    ) -> PromotionResult:
        if "security_admin" not in principal.roles:
            raise QuarantinePromotionError(
                "Promoção exige role security_admin",
                context={"subject": principal.subject},
            )
        if not correlation_id.strip():
            raise QuarantinePromotionError("Promoção exige correlation_id auditável")
        current = await self.registry.get(manifest_id, version)
        if current.status != RegistryStatus.QUARANTINED:
            raise QuarantinePromotionError(
                "Somente versões em quarentena podem ser promovidas",
                context={"status": current.status.value},
            )
        decision = self.pipeline.validate(
            current.manifest,
            artifact,
            signature=signature,
            trust_store=trust_store,
        )
        if not decision.accepted or decision.quarantined:
            raise QuarantinePromotionError(
                "Artefato falhou na revalidação de segurança",
                context={"findings": [finding.code for finding in decision.findings]},
            )
        promoted = await self.registry.set_status(
            manifest_id,
            version,
            RegistryStatus.PUBLISHED,
            actor=principal.subject,
            audit_action="quarantine_promoted",
            correlation_id=correlation_id,
        )
        return PromotionResult(promoted, decision, principal.subject, correlation_id)


__all__ = ["PromotionResult", "QuarantineManager", "SecurityPrincipal"]
