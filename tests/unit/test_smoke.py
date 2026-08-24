"""Smoke test do pacote e dos módulos públicos."""

from __future__ import annotations


class TestPublicAPI:
    def test_import_top_level(self) -> None:
        import ultron

        assert ultron.__version__ == "0.1.0"

    def test_import_manifests(self) -> None:
        from ultron import (
            AgentManifest,
            BaseManifest,
            PackManifest,
            SkillManifest,
            WorkflowManifest,
        )

        assert AgentManifest is not None
        assert SkillManifest is not None
        assert WorkflowManifest is not None
        assert PackManifest is not None
        assert BaseManifest is not None

    def test_import_errors(self) -> None:
        from ultron import (
            DependencyCycleError,
            IntegrityError,
            InvalidManifestError,
            PermissionDeniedError,
            SchemaVersionError,
            UltronError,
            VersionConflictError,
        )

        assert UltronError is not None
        assert InvalidManifestError is not None
        assert SchemaVersionError is not None
        assert IntegrityError is not None
        assert DependencyCycleError is not None
        assert VersionConflictError is not None
        assert PermissionDeniedError is not None

    def test_import_policy(self) -> None:
        from ultron.policy import (
            Policy,
            check_manifest_permissions,
            conservative_policy,
            default_deny_policy,
        )

        assert Policy is not None
        assert check_manifest_permissions is not None
        assert conservative_policy is not None
        assert default_deny_policy is not None

    def test_import_consumer(self) -> None:
        from ultron.consumer import (
            CONSUMER_PROTOCOL_VERSION,
            CapabilityRef,
            ConsumerAdapter,
            InstallPlan,
        )

        assert CONSUMER_PROTOCOL_VERSION == "1.0.0"
        assert CapabilityRef is not None
        assert ConsumerAdapter is not None
        assert InstallPlan is not None
