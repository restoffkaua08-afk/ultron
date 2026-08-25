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
    CapabilityNotInstalledError,
    CheckpointNotFoundError,
    DependencyCycleError,
    DependencyResolutionError,
    InstallationError,
    IntegrityError,
    InvalidManifestError,
    PermissionDeniedError,
    ProtocolCompatibilityError,
    SchemaVersionError,
    UltronError,
    UnsafeRemovalError,
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
from ultron.journal import LockfileJournal
from ultron.lifecycle import LifecycleManager, LifecycleState, LifecycleStore
from ultron.lockfile import LockedCapability, LockfileStore, UltronLockfile
from ultron.references import LocalReferenceAdapter, MappingReferenceAdapter, ReferenceAdapter
from ultron.resolver import DependencyResolver, ResolutionPlan, ResolvedDependency
from ultron.store import CollectionResult, PackageStore
from ultron.supply_chain import PublisherTrustStore, SignatureEnvelope
from ultron.validation import AdmissionDecision, ValidationPipeline, ValidationSeverity

__version__ = "0.1.0"
__all__ = [
    "AdmissionDecision",
    "AgentManifest",
    "ArtifactNotFoundError",
    "BaseManifest",
    "CapabilityNotInstalledError",
    "CheckpointNotFoundError",
    "CollectionResult",
    "DependencyCycleError",
    "DependencyRef",
    "DependencyResolutionError",
    "DependencyResolver",
    "InstallationError",
    "Installer",
    "IntegrityError",
    "IntegrityInfo",
    "InvalidManifestError",
    "LifecycleManager",
    "LifecycleState",
    "LifecycleStore",
    "LocalReferenceAdapter",
    "LockedCapability",
    "LockfileJournal",
    "LockfileStore",
    "ManifestId",
    "MappingReferenceAdapter",
    "PackManifest",
    "PackageStore",
    "Permission",
    "PermissionDeniedError",
    "ProtocolCompatibilityError",
    "Provenance",
    "PublisherId",
    "PublisherTrustStore",
    "ReferenceAdapter",
    "ResolutionPlan",
    "ResolvedDependency",
    "RiskLevel",
    "SchemaVersionError",
    "SignatureEnvelope",
    "SkillManifest",
    "UltronError",
    "UltronLockfile",
    "UltronVersion",
    "UnsafeRemovalError",
    "ValidationPipeline",
    "ValidationSeverity",
    "VersionConflictError",
    "WorkflowManifest",
    "__version__",
]
