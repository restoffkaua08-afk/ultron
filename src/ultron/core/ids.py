"""Identificadores e versão — tipos canônicos do ULTRON.

Regras (da especificação):

* ``ManifestId`` é ``publisher.name`` em kebab-case minúsculo.
* ``UltronVersion`` segue SemVer estrito.
* Ambos são imutáveis e serializáveis como string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Final

from pydantic import AfterValidator, StringConstraints

# ---- Padrões ---------------------------------------------------------------

_PUBLISHER_RE: Final[str] = r"^[a-z0-9][a-z0-9._-]{0,62}$"
_NAME_RE: Final[str] = r"^[a-z0-9][a-z0-9._-]{0,62}$"
_SEMVER_RE: Final[str] = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# ---- Validadores -----------------------------------------------------------


def _validate_publisher(v: str) -> str:
    if not re.match(_PUBLISHER_RE, v):
        raise ValueError(
            f"Publisher inválido: {v!r}. Deve casar {_PUBLISHER_RE!r} "
            "(kebab/snake minúsculo, 1-63 chars)."
        )
    return v


def _validate_name(v: str) -> str:
    if not re.match(_NAME_RE, v):
        raise ValueError(
            f"Nome de manifesto inválido: {v!r}. Deve casar {_NAME_RE!r}."
        )
    return v


def _validate_semver(v: str) -> str:
    if not re.match(_SEMVER_RE, v):
        raise ValueError(f"Versão semver inválida: {v!r}.")
    return v


# ---- Tipos públicos --------------------------------------------------------

PublisherId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=63),
    AfterValidator(_validate_publisher),
]
"""ID de publisher. Ex.: ``acme``, ``restoff``, ``kortain-research``."""

_NameStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=63),
    AfterValidator(_validate_name),
]


@dataclass(frozen=True, slots=True, eq=True)
class ManifestId:
    """ID global de um manifesto, no formato ``<publisher>/<name>``.

    Opaco ao caller: use ``str(manifest_id)`` para serializar e
    ``ManifestId.parse(raw)`` para desserializar.
    """

    publisher: str
    name: str

    def __post_init__(self) -> None:
        _validate_publisher(self.publisher)
        _validate_name(self.name)

    @classmethod
    def parse(cls, raw: str) -> ManifestId:
        if "/" not in raw:
            raise ValueError(f"ManifestId deve conter '/': {raw!r}")
        publisher, _, name = raw.partition("/")
        if not name:
            raise ValueError(f"ManifestId sem nome: {raw!r}")
        return cls(publisher, name)

    def __str__(self) -> str:
        return f"{self.publisher}/{self.name}"

    def __repr__(self) -> str:
        return f"ManifestId({self.publisher!r}, {self.name!r})"


UltronVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    AfterValidator(_validate_semver),
]
"""Versão SemVer estrita. Ex.: ``1.0.0``, ``2.3.1-beta.1``."""

# Faixa de versão (semver range). Aceita prefixos de comparação.
# Validação completa de ranges é feita por um resolver no U2.
# Aqui só validamos o formato mínimo para evitar lixo no manifesto.
_VERSION_RANGE_RE: Final[str] = r"^[\^~>=<\s0-9.,*+xX-]+$"


def _validate_version_range(v: str) -> str:
    if not re.match(_VERSION_RANGE_RE, v):
        raise ValueError(f"Faixa de versão inválida: {v!r}.")
    if not v.strip():
        raise ValueError("Faixa de versão vazia.")
    return v


UltronVersionRange = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
    AfterValidator(_validate_version_range),
]
"""Faixa semver, ex.: ``>=1.0.0,<2.0.0``, ``^1.2.0``, ``~1.2.0``."""
