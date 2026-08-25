"""Pipeline de admissão seguro; inspeciona metadados e bytes sem executar pacotes."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from ultron.core.base import BaseManifest, RiskLevel
from ultron.supply_chain import PublisherTrustStore, SignatureEnvelope


class ValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    message: str
    severity: ValidationSeverity


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    """Decisão determinística; erros sempre resultam em quarentena."""

    accepted: bool
    quarantined: bool
    artifact_sha256: str
    findings: tuple[ValidationFinding, ...]


class ValidationRule(ABC):
    @abstractmethod
    def inspect(self, manifest: BaseManifest, artifact: bytes) -> tuple[ValidationFinding, ...]:
        """Retorna achados sem alterar ou executar o artefato."""


class ArtifactIntegrityRule(ValidationRule):
    def inspect(self, manifest: BaseManifest, artifact: bytes) -> tuple[ValidationFinding, ...]:
        actual = hashlib.sha256(artifact).hexdigest()
        if manifest.integrity is None:
            return (
                ValidationFinding(
                    "INTEGRITY_MISSING",
                    "Manifest não declara SHA-256 do artefato",
                    ValidationSeverity.ERROR,
                ),
            )
        if manifest.integrity.digest != actual:
            return (
                ValidationFinding(
                    "INTEGRITY_MISMATCH",
                    "SHA-256 declarado não corresponde aos bytes recebidos",
                    ValidationSeverity.ERROR,
                ),
            )
        return ()


class PinnedProvenanceRule(ValidationRule):
    def inspect(self, manifest: BaseManifest, artifact: bytes) -> tuple[ValidationFinding, ...]:
        del artifact
        provenance = manifest.provenance
        if provenance.source == "git" and (
            provenance.commit is None
            or re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", provenance.commit) is None
        ):
            return (
                ValidationFinding(
                    "GIT_PROVENANCE_UNPINNED",
                    "Proveniência Git precisa de commit completo e imutável",
                    ValidationSeverity.ERROR,
                ),
            )
        if provenance.source == "oci" and "@sha256:" not in (provenance.repository or ""):
            return (
                ValidationFinding(
                    "OCI_PROVENANCE_UNPINNED",
                    "Proveniência OCI precisa estar fixada por digest sha256",
                    ValidationSeverity.ERROR,
                ),
            )
        return ()


class PermissionRiskRule(ValidationRule):
    _SENSITIVE = frozenset({"network.write", "fs.write", "process.spawn", "publish.external"})

    def inspect(self, manifest: BaseManifest, artifact: bytes) -> tuple[ValidationFinding, ...]:
        del artifact
        sensitive = sorted(
            permission.capability
            for permission in manifest.permissions
            if permission.capability in self._SENSITIVE
        )
        if sensitive and manifest.risks in {RiskLevel.SAFE, RiskLevel.LOW}:
            return (
                ValidationFinding(
                    "RISK_UNDERSTATED",
                    f"Permissões sensíveis incompatíveis com risco {manifest.risks.value}",
                    ValidationSeverity.ERROR,
                ),
            )
        if manifest.risks in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return (
                ValidationFinding(
                    "EXPLICIT_APPROVAL_REQUIRED",
                    "Capability de alto risco exige aprovação explícita do consumer",
                    ValidationSeverity.WARNING,
                ),
            )
        return ()


class ValidationPipeline:
    """Composição ordenada de regras deny-by-default para admissão."""

    def __init__(self, rules: tuple[ValidationRule, ...] | None = None) -> None:
        self.rules = rules or (
            ArtifactIntegrityRule(),
            PinnedProvenanceRule(),
            PermissionRiskRule(),
        )

    def validate(
        self,
        manifest: BaseManifest,
        artifact: bytes,
        *,
        signature: SignatureEnvelope | None = None,
        trust_store: PublisherTrustStore | None = None,
    ) -> AdmissionDecision:
        findings = tuple(
            finding for rule in self.rules for finding in rule.inspect(manifest, artifact)
        ) + self._signature_findings(manifest, artifact, signature, trust_store)
        quarantined = any(finding.severity == ValidationSeverity.ERROR for finding in findings)
        return AdmissionDecision(
            accepted=not quarantined,
            quarantined=quarantined,
            artifact_sha256=hashlib.sha256(artifact).hexdigest(),
            findings=findings,
        )

    @staticmethod
    def _signature_findings(
        manifest: BaseManifest,
        artifact: bytes,
        signature: SignatureEnvelope | None,
        trust_store: PublisherTrustStore | None,
    ) -> tuple[ValidationFinding, ...]:
        if signature is None:
            severity = (
                ValidationSeverity.WARNING
                if manifest.provenance.source == "local"
                else ValidationSeverity.ERROR
            )
            return (
                ValidationFinding(
                    "SIGNATURE_MISSING",
                    "Artefato não possui assinatura verificável do publisher",
                    severity,
                ),
            )
        if trust_store is None or not trust_store.verify(manifest, artifact, signature):
            return (
                ValidationFinding(
                    "SIGNATURE_INVALID",
                    "Assinatura ausente do trust store, revogada ou inválida",
                    ValidationSeverity.ERROR,
                ),
            )
        return ()


__all__ = [
    "AdmissionDecision",
    "ArtifactIntegrityRule",
    "PermissionRiskRule",
    "PinnedProvenanceRule",
    "ValidationFinding",
    "ValidationPipeline",
    "ValidationRule",
    "ValidationSeverity",
]
