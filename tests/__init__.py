"""Conftest do projeto — fixtures compartilhadas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ultron.core.base import (
    BaseManifest,
    IntegrityInfo,
    Permission,
    Provenance,
    RiskLevel,
)
from ultron.core.ids import ManifestId
from ultron.core.manifests import (
    AgentManifest,
    PackManifest,
    SkillManifest,
    WorkflowManifest,
    WorkflowStep,
)


def _provenance() -> Provenance:
    return Provenance(source="local")


@pytest.fixture
def valid_provenance() -> Provenance:
    return _provenance()


@pytest.fixture
def make_agent() -> callable:  # type: ignore[type-arg]
    def _factory(**overrides: object) -> AgentManifest:
        defaults: dict[str, object] = {
            "id": ManifestId("acme", "research-agent"),
            "version": "1.0.0",
            "publisher": "acme",
            "description": "Agent de pesquisa acadêmica.",
            "runtime": "python",
            "entrypoint": "acme_research.agent:ResearchAgent",
            "provenance": _provenance(),
            "risks": RiskLevel.LOW,
            "capabilities": ("web_search", "summarize"),
        }
        defaults.update(overrides)
        return AgentManifest(**defaults)  # type: ignore[arg-type]

    return _factory


@pytest.fixture
def make_skill() -> callable:  # type: ignore[type-arg]
    def _factory(**overrides: object) -> SkillManifest:
        defaults: dict[str, object] = {
            "id": ManifestId("acme", "summarize"),
            "version": "0.1.0",
            "publisher": "acme",
            "description": "Skill de sumarização de texto.",
            "skill_type": "prompt",
            "provenance": _provenance(),
        }
        defaults.update(overrides)
        return SkillManifest(**defaults)  # type: ignore[arg-type]

    return _factory


@pytest.fixture
def make_workflow() -> callable:  # type: ignore[type-arg]
    def _factory(**overrides: object) -> WorkflowManifest:
        steps = overrides.pop(
            "steps",
            (
                WorkflowStep(id="fetch", uses="skill:fetch"),
                WorkflowStep(id="summarize", uses="skill:summarize", retries=2),
            ),
        )
        defaults: dict[str, object] = {
            "id": ManifestId("acme", "research-workflow"),
            "version": "1.0.0",
            "publisher": "acme",
            "description": "Workflow de pesquisa e sumarização.",
            "steps": steps,
            "provenance": _provenance(),
        }
        defaults.update(overrides)
        return WorkflowManifest(**defaults)  # type: ignore[arg-type]

    return _factory


@pytest.fixture
def make_pack() -> callable:  # type: ignore[type-arg]
    def _factory(**overrides: object) -> PackManifest:
        defaults: dict[str, object] = {
            "id": ManifestId("acme", "research-pack"),
            "version": "1.0.0",
            "publisher": "acme",
            "description": "Bundle de pesquisa.",
            "contents": (
                {
                    "manifest_id": "acme/research-agent",
                    "version_range": ">=1.0.0",
                },
            ),
            "provenance": _provenance(),
        }
        defaults.update(overrides)
        return PackManifest(**defaults)  # type: ignore[arg-type]

    return _factory


__all__ = [
    "BaseManifest",
    "IntegrityInfo",
    "Permission",
    "Provenance",
    "ValidationError",
]
