"""Tipos base compartilhados por todos os manifests."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

from ultron.core.ids import (
    ManifestId,
    PublisherId,
    UltronVersion,
    UltronVersionRange,
)

# ---- Enums -----------------------------------------------------------------


class RiskLevel(StrEnum):
    """Nível de risco declarado pelo manifesto.

    * ``safe`` — leitura apenas, sem efeito colateral.
    * ``low`` — escrita local, reversível.
    * ``medium`` — escrita externa ou parcialmente irreversível.
    * ``high`` — exige aprovação explícita do consumer.
    * ``critical`` — exige aprovação *e* auditoria adicional.
    """

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---- Tipos escalares -------------------------------------------------------

_SemverStr = UltronVersion
_DescStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2048),
]
_NameShortStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_LicenseStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


# ---- Proveniência e integridade -------------------------------------------


class Provenance(BaseModel):
    """De onde veio o manifesto. Obrigatório em U0 (anti-gate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Literal["local", "git", "oci"] = Field(
        description="Origem do artefato. ULTRON só aceita 'local' no U0."
    )
    repository: str | None = Field(
        default=None,
        description="URL do repositório (se source=git).",
    )
    commit: str | None = Field(
        default=None,
        description="SHA do commit (se source=git).",
    )
    built_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Quando o artefato foi empacotado.",
    )

    @model_validator(mode="after")
    def _check_git_requires_repo(self) -> Provenance:
        if self.source in {"git", "oci"} and not self.repository:
            raise ValueError(f"Provenance com source={self.source!r} exige 'repository'.")
        return self


class IntegrityInfo(BaseModel):
    """Hash + algoritmo de integridade de um artefato."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    algorithm: Literal["sha256"] = "sha256"
    digest: Annotated[
        str,
        StringConstraints(pattern=r"^[a-f0-9]{64}$"),
    ] = Field(
        description="Digest em hex (64 chars para SHA-256).",
    )


# ---- Permissões -----------------------------------------------------------


# Allowlist de permissões suportadas no U0. Novas permissões exigem
# decisão explícita e atualização desta lista + dos testes de policy.
VALID_PERMISSIONS: frozenset[str] = frozenset(
    {
        # Rede
        "network.readonly",
        "network.write",
        # Filesystem
        "fs.read",
        "fs.write",
        # Processos
        "process.spawn",
        # Sistema
        "system.time",
        "system.env.read",
        # Memória / dados
        "memory.read",
        "memory.write",
        "memory.share",
        # Publicação externa
        "publish.external",
        # Aprovação
        "approval.request",
    }
)


class Permission(BaseModel):
    """Permissão solicitada por um manifesto."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
    ]
    scope: str | None = Field(
        default=None,
        description="Escopo opcional (ex.: 'user:123', 'project:meta').",
    )

    def model_post_init(self, __context: Any) -> None:
        if self.capability not in VALID_PERMISSIONS:
            raise ValueError(
                f"Permissão desconhecida: {self.capability!r}. Válidas: {sorted(VALID_PERMISSIONS)}"
            )


# ---- Dependências ---------------------------------------------------------


class DependencyRef(BaseModel):
    """Referência a outra capability: ``<publisher>/<name>@<version-range>``."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    id: ManifestId = Field(description="ID do manifesto dependente.")
    version_range: UltronVersionRange = Field(
        description="Faixa semver aceita (ex.: '>=1.0.0,<2.0.0').",
    )
    optional: bool = Field(
        default=False,
        description="Se a dependência é opcional (capability degradada se ausente).",
    )


# ---- Base manifest --------------------------------------------------------


class BaseManifest(BaseModel):
    """Manifest base. Todos os manifests do ULTRON herdam deste.

    Invariantes (verificadas em ``model_post_init``):

    * ``schema_version`` é uma string semver.
    * ``id`` segue ``<publisher>/<name>`` e o publisher bate com ``publisher``.
    * ``version`` é semver.
    """

    model_config = ConfigDict(
        extra="forbid",  # campos desconhecidos = erro (anti-gate)
        frozen=True,  # manifests publicados são imutáveis
        populate_by_name=True,
        arbitrary_types_allowed=True,  # ManifestId é classe Python custom
    )

    schema_version: _SemverStr = Field(
        default="1.0.0",
        description="Versão do schema ULTRON usada por este manifesto.",
    )
    kind: Literal["agent", "skill", "workflow", "pack"]
    id: ManifestId
    version: _SemverStr
    publisher: PublisherId
    description: _DescStr
    license: _LicenseStr = "MIT"
    homepage: HttpUrl | None = None
    tags: tuple[str, ...] = Field(default_factory=tuple)
    capabilities: tuple[str, ...] = Field(default_factory=tuple)
    permissions: tuple[Permission, ...] = Field(default_factory=tuple)
    risks: RiskLevel = RiskLevel.LOW
    dependencies: tuple[DependencyRef, ...] = Field(default_factory=tuple)
    compatibility: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Restrições de compatibilidade (ex.: 'runtime=python>=3.12').",
    )
    provenance: Provenance
    integrity: IntegrityInfo | None = None

    def model_post_init(self, __context: Any) -> None:
        # ID e publisher devem concordar.
        if self.id.publisher != self.publisher:
            raise ValueError(f"Manifest {self.id} tem publisher divergente: {self.publisher!r}")
        # Anti-gate: nenhum manifest pode solicitar aprovação total.
        for p in self.permissions:
            if p.capability in {"approve-all", "*"}:
                raise ValueError(f"Permissão proibida: {p.capability!r} (anti-gate de policy).")
