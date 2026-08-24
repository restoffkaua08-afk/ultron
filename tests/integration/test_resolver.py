"""Integração do resolver SemVer com o Registry U1."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from ultron.core.base import DependencyRef, Provenance, RiskLevel
from ultron.core.errors import DependencyCycleError, DependencyResolutionError
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.registry import Registry, RegistryStatus
from ultron.resolver import DependencyResolver

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def registry(tmp_path: Path) -> AsyncIterator[Registry]:
    reg = Registry(tmp_path / "registry.db")
    await reg.start()
    try:
        yield reg
    finally:
        await reg.close()


def skill(
    publisher: str,
    name: str,
    version: str,
    *,
    dependencies: tuple[DependencyRef, ...] = (),
) -> SkillManifest:
    return SkillManifest(
        id=ManifestId(publisher=publisher, name=name),
        version=version,
        description=f"Skill {name} {version}",
        publisher=publisher,
        license="MIT",
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        dependencies=dependencies,
        provenance=Provenance(source="local"),
    )


def dep(name: str, version_range: str, *, optional: bool = False) -> DependencyRef:
    return DependencyRef(
        id=ManifestId(publisher="acme", name=name),
        version_range=version_range,
        optional=optional,
    )


@pytest.mark.asyncio
async def test_resolver_selects_highest_compatible_version(registry: Registry) -> None:
    await registry.publish(skill("acme", "search", "1.0.0"))
    await registry.publish(skill("acme", "search", "1.8.0"))
    await registry.publish(skill("acme", "search", "2.0.0"))
    root = skill("acme", "agent-kit", "1.0.0", dependencies=(dep("search", "^1.0.0"),))

    plan = await DependencyResolver(registry).resolve(root)

    assert [(item.id, item.version) for item in plan.dependencies] == [("acme/search", "1.8.0")]


@pytest.mark.asyncio
async def test_resolver_orders_transitive_dependencies_first(registry: Registry) -> None:
    leaf = skill("acme", "leaf", "1.0.0")
    middle = skill("acme", "middle", "1.0.0", dependencies=(dep("leaf", "1.0.0"),))
    root = skill("acme", "root", "1.0.0", dependencies=(dep("middle", "1.0.0"),))
    await registry.publish(leaf)
    await registry.publish(middle)

    plan = await DependencyResolver(registry).resolve(root)

    assert [item.id for item in plan.dependencies] == ["acme/leaf", "acme/middle"]


@pytest.mark.asyncio
async def test_optional_missing_dependency_becomes_warning(registry: Registry) -> None:
    root = skill("acme", "root", "1.0.0", dependencies=(dep("missing", "*", optional=True),))

    plan = await DependencyResolver(registry).resolve(root)

    assert plan.dependencies == ()
    assert "Dependência opcional ausente" in plan.warnings[0]


@pytest.mark.asyncio
async def test_required_missing_or_revoked_dependency_fails(registry: Registry) -> None:
    dependency = skill("acme", "blocked", "1.0.0")
    await registry.publish(dependency)
    await registry.set_status("acme/blocked", "1.0.0", RegistryStatus.REVOKED)
    root = skill("acme", "root", "1.0.0", dependencies=(dep("blocked", "*"),))

    with pytest.raises(DependencyResolutionError):
        await DependencyResolver(registry).resolve(root)


@pytest.mark.asyncio
async def test_cycle_is_rejected(registry: Registry) -> None:
    a = skill("acme", "a", "1.0.0", dependencies=(dep("b", "1.0.0"),))
    b = skill("acme", "b", "1.0.0", dependencies=(dep("a", "1.0.0"),))
    await registry.publish(a)
    await registry.publish(b)

    with pytest.raises(DependencyCycleError):
        await DependencyResolver(registry).resolve(a)
