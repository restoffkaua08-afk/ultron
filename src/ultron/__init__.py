"""ULTRON — plataforma independente de capacidades versionadas.

Este pacote é a fonte canônica do namespace público. Tudo o que é
importável diretamente de ``ultron`` deve ser considerado estável
dentro do mesmo ``MAJOR`` (semver).
"""

from ultron.core.base import (
    BaseManifest,
    DependencyRef,
    IntegrityInfo,
    Permission,
    Provenance,
    RiskLevel,
)
from ultron.core.errors import (
    DependencyCycleError,
    IntegrityError,
    InvalidManifestError,
    PermissionDeniedError,
    SchemaVersionError,
    UltronError,
    VersionConflictError,
)
from ultron.core.ids import ManifestId, PublisherId, UltronVersion
from ultron.core.manifests import (
    AgentManifest,
    PackManifest,
    SkillManifest,
    WorkflowManifest,
)

__version__ = "0.1.0"
__all__ = [
    # Manifests
    "AgentManifest",
    # Base
    "BaseManifest",
    "DependencyCycleError",
    "DependencyRef",
    "IntegrityError",
    "IntegrityInfo",
    "InvalidManifestError",
    # IDs
    "ManifestId",
    "PackManifest",
    "Permission",
    "PermissionDeniedError",
    "Provenance",
    "PublisherId",
    "RiskLevel",
    "SchemaVersionError",
    "SkillManifest",
    # Errors
    "UltronError",
    "UltronVersion",
    "VersionConflictError",
    "WorkflowManifest",
    "__version__",
]
