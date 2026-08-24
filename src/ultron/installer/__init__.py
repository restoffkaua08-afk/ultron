"""Pipeline transacional de instalação; nunca ativa nem executa artefatos."""

from __future__ import annotations

from collections.abc import Mapping

from ultron.core.base import BaseManifest
from ultron.core.errors import InstallationError
from ultron.lockfile import LockedCapability, LockfileStore, UltronLockfile
from ultron.registry import Registry, RegistryStatus
from ultron.resolver import DependencyResolver
from ultron.store import PackageStore

ArtifactKey = tuple[str, str]


class Installer:
    """Resolve, verifica e armazena um grafo antes de trocar o lockfile."""

    def __init__(
        self,
        registry: Registry,
        package_store: PackageStore,
        lockfile_store: LockfileStore,
    ) -> None:
        self.registry = registry
        self.package_store = package_store
        self.lockfile_store = lockfile_store

    async def install(
        self,
        root: BaseManifest,
        artifacts: Mapping[ArtifactKey, bytes],
    ) -> UltronLockfile:
        plan = await DependencyResolver(self.registry).resolve(root)
        manifests: list[BaseManifest] = []
        for item in plan.dependencies:
            manifests.append(await self._manifest(item.id, item.version))
        manifests.append(root)
        selected_versions = {str(manifest.id): manifest.version for manifest in manifests}
        locked: list[LockedCapability] = []

        for manifest in manifests:
            key = (str(manifest.id), manifest.version)
            content = artifacts.get(key)
            if content is None:
                raise InstallationError(
                    f"Artefato ausente para {key[0]}@{key[1]}",
                    context={"id": key[0], "version": key[1]},
                )
            if manifest.integrity is None:
                raise InstallationError(
                    f"Manifest {key[0]}@{key[1]} não declara integridade",
                    context={"id": key[0], "version": key[1]},
                )
            integrity = self.package_store.put(content, manifest.integrity)
            dependencies = tuple(
                sorted(
                    f"{dependency.id}@{selected_versions[str(dependency.id)]}"
                    for dependency in manifest.dependencies
                    if str(dependency.id) in selected_versions
                )
            )
            locked.append(
                LockedCapability(
                    id=key[0],
                    version=key[1],
                    kind=manifest.kind,
                    digest=integrity.digest,
                    dependencies=dependencies,
                )
            )

        lockfile = UltronLockfile(
            root=f"{root.id}@{root.version}",
            capabilities=tuple(sorted(locked, key=lambda item: (item.id, item.version))),
        )
        self.lockfile_store.write(lockfile)
        return lockfile

    async def _manifest(self, manifest_id: str, version: str) -> BaseManifest:
        entry = await self.registry.get(manifest_id, version)
        if entry.status == RegistryStatus.REVOKED:
            raise InstallationError(
                f"Manifest revogado: {manifest_id}@{version}",
                context={"id": manifest_id, "version": version},
            )
        return entry.manifest


__all__ = ["ArtifactKey", "Installer"]
