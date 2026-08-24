"""Testes dos manifests concretos (agent, skill, workflow, pack) e anti-gates."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ultron.core.base import DependencyRef
from ultron.core.ids import ManifestId
from ultron.core.manifests import (
    check_unique_versions,
    detect_cycles,
)


class TestAgentManifest:
    def test_basico_valido(self, make_agent):
        agent = make_agent()
        assert agent.kind == "agent"
        assert agent.id == ManifestId("acme", "research-agent")
        assert agent.publisher == "acme"
        assert agent.runtime == "python"
        assert ":" in agent.entrypoint

    def test_extra_field_rejeitado(self, make_agent):
        with pytest.raises(ValidationError):
            make_agent(foo="bar")  # type: ignore[call-arg]

    def test_entrypoint_sem_virgula_rejeitado(self, make_agent):
        with pytest.raises(ValidationError):
            make_agent(entrypoint="acme_research.agent.ResearchAgent")

    def test_publisher_divergente_rejeitado(self, make_agent):
        with pytest.raises(ValidationError):
            make_agent(publisher="outro")

    def test_imutavel(self, make_agent):
        agent = make_agent()
        with pytest.raises(ValidationError):
            agent.version = "9.9.9"  # type: ignore[misc]


class TestSkillManifest:
    def test_skill_prompt(self, make_skill):
        s = make_skill()
        assert s.kind == "skill"
        assert s.skill_type == "prompt"

    def test_skill_type_invalido(self, make_skill):
        with pytest.raises(ValidationError):
            make_skill(skill_type="magic")


class TestWorkflowManifest:
    def test_valido(self, make_workflow):
        wf = make_workflow()
        assert len(wf.steps) == 2
        assert wf.steps[1].retries == 2

    def test_step_ids_duplicados_rejeitados(self, make_workflow):
        from ultron.core.manifests import WorkflowStep

        with pytest.raises(ValidationError):
            make_workflow(
                steps=(
                    WorkflowStep(id="x", uses="skill:a"),
                    WorkflowStep(id="x", uses="skill:b"),
                )
            )

    def test_compensacao_para_step_inexistente(self, make_workflow):
        with pytest.raises(ValidationError):
            make_workflow(compensations={"nao_existe": "tambem_nao"})


class TestPackManifest:
    def test_valido(self, make_pack):
        p = make_pack()
        assert p.kind == "pack"
        assert len(p.contents) == 1

    def test_conflict_self_rejeitado(self, make_pack):
        with pytest.raises(ValidationError):
            make_pack(conflicts=("acme/research-pack",))


class TestAntiGates:
    def test_permissao_approve_all_rejeitada(self, make_agent):
        with pytest.raises(ValidationError):
            make_agent(
                permissions=(
                    {
                        "capability": "approve-all",
                    },
                )
            )


class TestDependencyCycles:
    def test_sem_ciclo(self, make_agent):
        a = make_agent()
        b = make_agent(
            id=ManifestId("acme", "b"),
            entrypoint="acme.b:B",
            dependencies=(
                DependencyRef(
                    id=ManifestId("acme", "research-agent"),
                    version_range=">=1.0.0",
                ),
            ),
        )
        detect_cycles([a, b])  # não deve lançar

    def test_ciclo_detectado(self, make_agent):
        a = make_agent(
            id=ManifestId("acme", "a"),
            entrypoint="acme.a:A",
            dependencies=(
                DependencyRef(
                    id=ManifestId("acme", "b"),
                    version_range=">=1.0.0",
                ),
            ),
        )
        b = make_agent(
            id=ManifestId("acme", "b"),
            entrypoint="acme.b:B",
            dependencies=(
                DependencyRef(
                    id=ManifestId("acme", "a"),
                    version_range=">=1.0.0",
                ),
            ),
        )
        with pytest.raises(Exception) as exc:
            detect_cycles([a, b])
        msg = str(exc.value).lower()
        assert "ciclo" in msg or "cycle" in msg


class TestUniqueVersions:
    def test_mesma_versao_ok(self, make_agent):
        a = make_agent()
        b = make_agent(entrypoint="acme.x:X")
        check_unique_versions([a, b])

    def test_versoes_conflitantes(self, make_agent):
        a = make_agent()
        b = make_agent(version="2.0.0", entrypoint="acme.x:X")
        with pytest.raises(Exception) as exc:
            check_unique_versions([a, b])
        assert "CONFLICT" in exc.value.code.upper() or "conflito" in str(exc.value).lower()
