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
def make_agent():
    def _factory(**overrides):
        defaults: dict = {
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
        return AgentManifest(**defaults)

    return _factory


@pytest.fixture
def make_skill():
    def _factory(**overrides):
        defaults: dict = {
            "id": ManifestId("acme", "summarize"),
            "version": "0.1.0",
            "publisher": "acme",
            "description": "Skill de sumarização de texto.",
            "skill_type": "prompt",
            "provenance": _provenance(),
        }
        defaults.update(overrides)
        return SkillManifest(**defaults)

    return _factory


@pytest.fixture
def make_workflow():
    def _factory(**overrides):
        steps = overrides.pop(
            "steps",
            (
                WorkflowStep(id="fetch", uses="skill:fetch"),
                WorkflowStep(id="summarize", uses="skill:summarize", retries=2),
            ),
        )
        defaults: dict = {
            "id": ManifestId("acme", "research-workflow"),
            "version": "1.0.0",
            "publisher": "acme",
            "description": "Workflow de pesquisa e sumarização.",
            "steps": steps,
            "provenance": _provenance(),
        }
        defaults.update(overrides)
        return WorkflowManifest(**defaults)

    return _factory


@pytest.fixture
def make_pack():
    def _factory(**overrides):
        defaults: dict = {
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
        return PackManifest(**defaults)

    return _factory


__all__ = [
    "BaseManifest",
    "IntegrityInfo",
    "Permission",
    "Provenance",
    "ValidationError",
]
