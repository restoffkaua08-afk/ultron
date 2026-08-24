"""Erros tipados do ULTRON.

Cada erro carrega contexto suficiente para auditoria. Nenhuma
exceção genérica (nua) deve escapar de ULTRON — ou o caller
não tem como reagir corretamente.
"""

from __future__ import annotations

from typing import Any


class UltronError(Exception):
    """Erro base do ULTRON. Todas as exceções públicas herdam desta."""

    code: str = "ULTRON_ERROR"
    http_status: int = 500

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = context or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "context": self.context,
        }


class InvalidManifestError(UltronError):
    """Manifest não atende ao schema ou a uma invariante semântica."""

    code = "INVALID_MANIFEST"
    http_status = 422


class SchemaVersionError(UltronError):
    """schema_version do manifest é desconhecido ou incompatível."""

    code = "SCHEMA_VERSION_INCOMPATIBLE"
    http_status = 409


class IntegrityError(UltronError):
    """Hash ou assinatura do artefato não confere."""

    code = "INTEGRITY_FAILED"
    http_status = 409


class DependencyCycleError(UltronError):
    """Ciclo detectado na resolução de dependências."""

    code = "DEPENDENCY_CYCLE"
    http_status = 422


class VersionConflictError(UltronError):
    """Conflito entre versões exigidas (semver) de uma mesma dependência."""

    code = "VERSION_CONFLICT"
    http_status = 409


class PermissionDeniedError(UltronError):
    """Permissão solicitada excede o que o consumer concede."""

    code = "PERMISSION_DENIED"
    http_status = 403


class PolicyViolationError(UltronError):
    """Operação viola uma regra de policy do consumer."""

    code = "POLICY_VIOLATION"
    http_status = 403
