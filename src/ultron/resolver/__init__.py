"""Resolução determinística de dependências do Gate U2."""

from __future__ import annotations

import re
from dataclasses import dataclass

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from ultron.core.base import BaseManifest, DependencyRef
from ultron.core.errors import DependencyCycleError, DependencyResolutionError
from ultron.registry import Registry, RegistryStatus


@dataclass(frozen=True, slots=True)
class ResolvedDependency:
    """Versão exata escolhida para uma dependência."""

    id: str
    version: str
    optional: bool


@dataclass(frozen=True, slots=True)
class ResolutionPlan:
    """Plano reproduzível; dependências aparecem antes do manifesto raiz."""

    root_id: str
    root_version: str
    dependencies: tuple[ResolvedDependency, ...]
    warnings: tuple[str, ...] = ()


class DependencyResolver:
    """Resolve o grafo sem instalar, ativar ou executar artefatos."""

    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    async def resolve(self, root: BaseManifest) -> ResolutionPlan:
        selected: dict[str, ResolvedDependency] = {}
        manifests: dict[str, BaseManifest] = {str(root.id): root}
        warnings: list[str] = []

        async def visit(manifest: BaseManifest, path: tuple[str, ...]) -> None:
            current_id = str(manifest.id)
            if current_id in path:
                cycle = [*path, current_id]
                raise DependencyCycleError(
                    f"Ciclo detectado: {' -> '.join(cycle)}", context={"cycle": cycle}
                )
            for dependency in manifest.dependencies:
                resolved_manifest = await self._select(dependency)
                if resolved_manifest is None:
                    if dependency.optional:
                        target = f"{dependency.id}@{dependency.version_range}"
                        warnings.append(f"Dependência opcional ausente: {target}")
                        continue
                    target = f"{dependency.id}@{dependency.version_range}"
                    raise DependencyResolutionError(
                        f"Nenhuma versão compatível para {target}",
                        context={
                            "id": str(dependency.id),
                            "version_range": dependency.version_range,
                        },
                    )
                dep_id = str(resolved_manifest.id)
                existing = selected.get(dep_id)
                if existing and existing.version != resolved_manifest.version:
                    raise DependencyResolutionError(
                        f"Conflito de versões para {dep_id}: "
                        f"{existing.version} vs {resolved_manifest.version}",
                        context={
                            "id": dep_id,
                            "versions": [existing.version, resolved_manifest.version],
                        },
                    )
                manifests[dep_id] = resolved_manifest
                selected[dep_id] = ResolvedDependency(
                    id=dep_id,
                    version=resolved_manifest.version,
                    optional=dependency.optional,
                )
                await visit(resolved_manifest, (*path, current_id))

        await visit(root, ())
        ordered = _topological_order(root, manifests, selected)
        return ResolutionPlan(
            root_id=str(root.id),
            root_version=root.version,
            dependencies=tuple(ordered),
            warnings=tuple(warnings),
        )

    async def _select(self, dependency: DependencyRef) -> BaseManifest | None:
        entries = await self.registry.list_versions(dependency.id)
        specifier = _to_specifier(dependency.version_range)
        compatible = [
            entry.manifest
            for entry in entries
            if entry.status in {RegistryStatus.PUBLISHED, RegistryStatus.DEPRECATED}
            and Version(entry.manifest.version) in specifier
        ]
        if not compatible:
            return None
        return max(compatible, key=lambda manifest: Version(manifest.version))


def _to_specifier(version_range: str) -> SpecifierSet:
    """Converte ranges ULTRON comuns para ``packaging.SpecifierSet``."""
    raw = version_range.strip()
    if raw in {"*", "x", "X"}:
        return SpecifierSet()
    if raw.startswith("^"):
        base = Version(raw[1:])
        if base.major > 0:
            upper = f"{base.major + 1}.0.0"
        elif base.minor > 0:
            upper = f"0.{base.minor + 1}.0"
        else:
            upper = f"0.0.{base.micro + 1}"
        return SpecifierSet(f">={base},<{upper}")
    if raw.startswith("~") and not raw.startswith("~="):
        base = Version(raw[1:])
        return SpecifierSet(f">={base},<{base.major}.{base.minor + 1}.0")
    wildcard = re.fullmatch(r"(\d+)\.(\d+)\.[xX*]", raw)
    if wildcard:
        major, minor = map(int, wildcard.groups())
        return SpecifierSet(f">={major}.{minor}.0,<{major}.{minor + 1}.0")
    if re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", raw):
        raw = f"=={raw}"
    try:
        return SpecifierSet(raw)
    except InvalidSpecifier as exc:
        raise DependencyResolutionError(
            f"Faixa de versão inválida: {version_range!r}",
            context={"version_range": version_range},
        ) from exc


def _topological_order(
    root: BaseManifest,
    manifests: dict[str, BaseManifest],
    selected: dict[str, ResolvedDependency],
) -> list[ResolvedDependency]:
    ordered: list[ResolvedDependency] = []
    visited: set[str] = set()

    def visit(manifest: BaseManifest) -> None:
        for dependency in sorted(manifest.dependencies, key=lambda item: str(item.id)):
            dep_id = str(dependency.id)
            if dep_id in visited or dep_id not in selected:
                continue
            visit(manifests[dep_id])
            visited.add(dep_id)
            ordered.append(selected[dep_id])

    visit(root)
    return ordered


__all__ = ["DependencyResolver", "ResolutionPlan", "ResolvedDependency"]
