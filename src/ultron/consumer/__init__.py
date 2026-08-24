"""Consumer Adapter — interface versionada entre ULTRON e seus consumidores.

No U0, este módulo define apenas o *contrato* (classe abstrata + tipos).
Implementações concretas (HTTP, CLI, in-process) entram no U1/U2.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ultron.core.base import BaseManifest

# Versão do protocolo — incrementada em breaking changes.
CONSUMER_PROTOCOL_VERSION: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class CapabilityRef:
    """Referência a uma capability publicada no ULTRON."""

    id: str  # "<publisher>/<name>"
    version: str
    kind: str


@dataclass(frozen=True, slots=True)
class InstallPlan:
    """Plano de instalação gerado pelo consumer antes de aplicar."""

    plan_id: str
    to_install: tuple[CapabilityRef, ...]
    warnings: tuple[str, ...] = ()


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
