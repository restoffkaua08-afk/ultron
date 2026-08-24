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
    ArtifactNotFoundError,
    DependencyCycleError,
    DependencyResolutionError,
    InstallationError,
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
from ultron.installer import Installer
from ultron.lockfile import LockedCapability, LockfileStore, UltronLockfile
from ultron.resolver import DependencyResolver, ResolutionPlan, ResolvedDependency
from ultron.store import PackageStore

__version__ = "0.1.0"
__all__ = [
    "AgentManifest",
    "ArtifactNotFoundError",
    "BaseManifest",
    "DependencyCycleError",
    "DependencyRef",
    "DependencyResolutionError",
    "DependencyResolver",
    "InstallationError",
    "Installer",
    "IntegrityError",
    "IntegrityInfo",
    "InvalidManifestError",
    "LockedCapability",
    "LockfileStore",
    "ManifestId",
    "PackManifest",
    "PackageStore",
    "Permission",
    "PermissionDeniedError",
    "Provenance",
    "PublisherId",
    "ResolutionPlan",
    "ResolvedDependency",
    "RiskLevel",
    "SchemaVersionError",
    "SkillManifest",
    # Errors
    "UltronError",
    "UltronLockfile",
    "UltronVersion",
    "VersionConflictError",
    "WorkflowManifest",
    "__version__",
]
