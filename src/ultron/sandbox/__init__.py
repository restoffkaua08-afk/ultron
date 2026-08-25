"""Contrato de execução isolada para capabilities ULTRON.

O Registry apenas descreve e valida artefatos. A execução é delegada a um
backend separado, sempre por uma especificação fechada e auditável.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ultron.core.base import Permission
from ultron.core.errors import PermissionDeniedError, PolicyViolationError
from ultron.policy import Policy, check_manifest_permissions


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    """Limites obrigatórios aplicados pelo backend de isolamento."""

    timeout_seconds: int = 30
    memory_bytes: int = 256 * 1024 * 1024
    cpu_count: float = 1.0
    process_limit: int = 64
    output_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_seconds <= 300:
            raise PolicyViolationError("timeout do sandbox fora do intervalo seguro")
        if not 16 * 1024 * 1024 <= self.memory_bytes <= 2 * 1024 * 1024 * 1024:
            raise PolicyViolationError("memória do sandbox fora do intervalo seguro")
        if not 0.1 <= self.cpu_count <= 4:
            raise PolicyViolationError("CPU do sandbox fora do intervalo seguro")
        if not 1 <= self.process_limit <= 256:
            raise PolicyViolationError("limite de processos fora do intervalo seguro")
        if not 1 <= self.output_bytes <= 10 * 1024 * 1024:
            raise PolicyViolationError("limite de saída fora do intervalo seguro")


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    """Pedido autocontido; imagens precisam estar fixadas por digest."""

    capability_id: str
    image: str
    command: tuple[str, ...]
    permissions: tuple[Permission, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    limits: SandboxLimits = field(default_factory=SandboxLimits)

    def __post_init__(self) -> None:
        if "@sha256:" not in self.image:
            raise PolicyViolationError("imagem do sandbox deve estar fixada por digest SHA-256")
        digest = self.image.rsplit("@sha256:", 1)[1]
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise PolicyViolationError("digest SHA-256 inválido para imagem do sandbox")
        if not self.command or any(not part or "\x00" in part for part in self.command):
            raise PolicyViolationError("comando do sandbox inválido")
        keys = [key for key, _ in self.environment]
        if len(keys) != len(set(keys)) or any(not key.isidentifier() for key in keys):
            raise PolicyViolationError("ambiente do sandbox contém chaves inválidas ou duplicadas")


@dataclass(frozen=True, slots=True)
class SandboxResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    timed_out: bool = False


class SandboxBackend(Protocol):
    """Porta implementada por um worker isolado (Docker, microVM ou equivalente)."""

    def run(self, request: SandboxRequest, *, network_enabled: bool) -> SandboxResult: ...


class SandboxExecutor:
    """Autoriza e delega execução sem importar ou executar o pacote no Registry."""

    def __init__(self, backend: SandboxBackend) -> None:
        self._backend = backend

    def execute(self, request: SandboxRequest, policy: Policy) -> SandboxResult:
        check_manifest_permissions(request.permissions, policy)
        if policy.needs_approval("process.spawn"):
            raise PermissionDeniedError(
                "execução requer aprovação explícita",
                context={"capability_id": request.capability_id},
            )
        if not policy.allows("process.spawn"):
            raise PermissionDeniedError(
                "consumer não concede process.spawn",
                context={"capability_id": request.capability_id},
            )

        network_enabled = any(
            permission.capability in {"network.readonly", "network.full"}
            for permission in request.permissions
        )
        result = self._backend.run(request, network_enabled=network_enabled)
        return SandboxResult(
            exit_code=result.exit_code,
            stdout=result.stdout[: request.limits.output_bytes],
            stderr=result.stderr[: request.limits.output_bytes],
            timed_out=result.timed_out,
        )


__all__ = [
    "SandboxBackend",
    "SandboxExecutor",
    "SandboxLimits",
    "SandboxRequest",
    "SandboxResult",
]
