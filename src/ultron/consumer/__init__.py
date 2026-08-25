"""Consumer Adapter — interface versionada entre ULTRON e seus consumidores.

No U0, este módulo define apenas o *contrato* (classe abstrata + tipos).
Implementações concretas (HTTP, CLI, in-process) entram no U1/U2.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from ultron.core.errors import ProtocolCompatibilityError
from ultron.core.ids import ManifestId, UltronVersion

if TYPE_CHECKING:
    from ultron.core.base import BaseManifest

# Versão do protocolo — incrementada em breaking changes.
CONSUMER_PROTOCOL_VERSION: str = "1.0.0"
_VERSION_ADAPTER = TypeAdapter(UltronVersion)
_KINDS = frozenset({"agent", "skill", "workflow", "pack"})


@dataclass(frozen=True, slots=True)
class CapabilityRef:
    """Referência a uma capability publicada no ULTRON."""

    id: str  # "<publisher>/<name>"
    version: str
    kind: str

    def __post_init__(self) -> None:
        ManifestId.parse(self.id)
        _VERSION_ADAPTER.validate_python(self.version)
        if self.kind not in _KINDS:
            raise ValueError(f"Kind de capability inválido: {self.kind!r}")


@dataclass(frozen=True, slots=True)
class InstallPlan:
    """Plano de instalação gerado pelo consumer antes de aplicar."""

    plan_id: str
    to_install: tuple[CapabilityRef, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id não pode ser vazio")
        identities = tuple((item.id, item.version) for item in self.to_install)
        if len(identities) != len(set(identities)):
            raise ValueError("Plano contém capabilities duplicadas")


@dataclass(frozen=True, slots=True)
class ConsumerDescriptor:
    """Identidade e capacidades de transporte de um consumer independente."""

    consumer_id: str
    protocol_version: str
    transports: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.consumer_id.strip():
            raise ValueError("consumer_id não pode ser vazio")
        _VERSION_ADAPTER.validate_python(self.protocol_version)
        if not self.transports or any(not item.strip() for item in self.transports):
            raise ValueError("Consumer precisa declarar ao menos um transporte")


@dataclass(frozen=True, slots=True)
class ProtocolHandshake:
    """Resultado serializável da negociação de versão do protocolo."""

    accepted: bool
    server_version: str
    consumer_version: str
    consumer_id: str


@dataclass(frozen=True, slots=True)
class ConsumerConformanceReport:
    """Evidência não mutante produzida pela suíte de conformidade."""

    handshake: ProtocolHandshake
    catalog_count: int
    installed_count: int


def negotiate_protocol(descriptor: ConsumerDescriptor) -> ProtocolHandshake:
    """Aceita versões do mesmo major e rejeita breaking changes."""
    server_major = int(CONSUMER_PROTOCOL_VERSION.split(".", 1)[0])
    consumer_major = int(descriptor.protocol_version.split(".", 1)[0])
    if server_major != consumer_major:
        raise ProtocolCompatibilityError(
            "Major do protocolo do consumer é incompatível",
            context={
                "consumer_id": descriptor.consumer_id,
                "consumer_version": descriptor.protocol_version,
                "server_version": CONSUMER_PROTOCOL_VERSION,
            },
        )
    return ProtocolHandshake(
        accepted=True,
        server_version=CONSUMER_PROTOCOL_VERSION,
        consumer_version=descriptor.protocol_version,
        consumer_id=descriptor.consumer_id,
    )


def verify_consumer(
    adapter: ConsumerAdapter, descriptor: ConsumerDescriptor
) -> ConsumerConformanceReport:
    """Verifica handshake e formatos de leitura sem alterar o consumer."""
    handshake = negotiate_protocol(descriptor)
    catalog = adapter.get_capabilities()
    installed = adapter.list_installed()
    for item in (*catalog, *installed):
        if not isinstance(item, CapabilityRef):
            raise TypeError("Consumer retornou referência fora do contrato")
    if len(catalog) != len(set(catalog)) or len(installed) != len(set(installed)):
        raise ValueError("Consumer retornou referências duplicadas")
    return ConsumerConformanceReport(handshake, len(catalog), len(installed))


class ConsumerAdapter(ABC):
    """Interface estável entre ULTRON e qualquer consumidor (Zane, Jarvis, etc).

    Invariantes:

    * Métodos são ``idempotentes`` quando recebem o mesmo ``id`` + versão.
    * Falhas parciais nunca retornam sucesso silencioso.
    * ``ULTRON offline`` → o adapter deve degradar com erro tipado, nunca
      com retorno vazio.
    """

    @abstractmethod
    def get_capabilities(self) -> list[CapabilityRef]:
        """Lista todas as capabilities publicadas (offline-first)."""

    @abstractmethod
    def check_compatibility(self, manifest: BaseManifest) -> tuple[bool, list[str]]:
        """Devolve ``(compatível, lista de warnings)``.

        Warnings não bloqueiam — mas devem ser reportados ao usuário.
        """

    @abstractmethod
    def install(self, manifest: BaseManifest) -> InstallPlan:
        """Resolve dependências e devolve um plano. NÃO executa."""

    @abstractmethod
    def activate(self, capability_id: str) -> None:
        """Ativa uma capability já instalada. Falha se não estiver."""

    @abstractmethod
    def deactivate(self, capability_id: str) -> None:
        """Desativa. Dados podem permanecer; execução para."""

    @abstractmethod
    def remove(self, capability_id: str) -> None:
        """Remove definitivamente. Verifica dependentes antes."""

    @abstractmethod
    def list_installed(self) -> list[CapabilityRef]:
        """Capabilities instaladas no escopo deste consumer."""

    @abstractmethod
    def get_status(self, capability_id: str) -> dict[str, Any]:
        """Estado atual: instalado, ativado, versão, hash, etc."""


__all__ = [
    "CONSUMER_PROTOCOL_VERSION",
    "CapabilityRef",
    "ConsumerAdapter",
    "ConsumerConformanceReport",
    "ConsumerDescriptor",
    "InstallPlan",
    "ProtocolHandshake",
    "negotiate_protocol",
    "verify_consumer",
]
