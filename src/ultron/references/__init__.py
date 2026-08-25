"""Adapters seguros para materializar artefatos referenciados por manifests."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path

from ultron.core.base import BaseManifest
from ultron.core.errors import ArtifactNotFoundError, InstallationError


class ReferenceAdapter(ABC):
    """Porta de leitura: adapters retornam bytes, nunca executam conteúdo."""

    @abstractmethod
    def fetch(self, manifest: BaseManifest) -> bytes:
        """Materializa os bytes declarados por um manifesto."""


class MappingReferenceAdapter(ReferenceAdapter):
    """Adapter determinístico para integrações que já obtiveram os bytes."""

    def __init__(self, artifacts: Mapping[tuple[str, str], bytes]) -> None:
        self.artifacts = artifacts

    def fetch(self, manifest: BaseManifest) -> bytes:
        key = (str(manifest.id), manifest.version)
        try:
            return self.artifacts[key]
        except KeyError as exc:
            raise ArtifactNotFoundError(
                f"Referência não encontrada para {key[0]}@{key[1]}",
                context={"id": key[0], "version": key[1]},
            ) from exc


class LocalReferenceAdapter(ReferenceAdapter):
    """Lê referências locais confinadas a uma raiz permitida."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve(strict=True)

    def fetch(self, manifest: BaseManifest) -> bytes:
        provenance = manifest.provenance
        if provenance.source != "local" or not provenance.repository:
            raise InstallationError(
                "Adapter local exige provenance.source='local' e repository",
                context={"id": str(manifest.id)},
            )
        candidate = (self.root / provenance.repository).resolve(strict=False)
        if not candidate.is_relative_to(self.root):
            raise InstallationError(
                "Referência local escaparia da raiz permitida",
                context={"id": str(manifest.id)},
            )
        if not candidate.is_file():
            raise ArtifactNotFoundError(
                f"Artefato local não encontrado: {provenance.repository}",
                context={"id": str(manifest.id)},
            )
        return candidate.read_bytes()


__all__ = ["LocalReferenceAdapter", "MappingReferenceAdapter", "ReferenceAdapter"]
