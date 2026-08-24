"""Manifests concretos: Agent, Skill, Workflow, Pack."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ultron.core.base import BaseManifest
from ultron.core.errors import DependencyCycleError, VersionConflictError

# ---- Tipos auxiliares ------------------------------------------------------

_RuntimeStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
_EntrypointStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]


# ---- Agent -----------------------------------------------------------------


class AgentManifest(BaseManifest):
    """Perfil executável de um agente."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["agent"] = "agent"
    runtime: _RuntimeStr
    entrypoint: _EntrypointStr = Field(
        description=(
            "Caminho de import do agente. NÃO é executado durante validação. "
            "Formato: 'package.module:Class'."
        )
    )
    models: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Modelos aceitos (ex.: 'claude-opus-5', 'gpt-foo').",
    )
    tools: tuple[str, ...] = Field(default_factory=tuple)
    skills: tuple[str, ...] = Field(default_factory=tuple)
    budgets: dict[str, int | float] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        # Anti-gate: entrypoint precisa ter formato mínimo
        if ":" not in self.entrypoint:
            raise ValueError(
                f"Entrypoint inválido: {self.entrypoint!r}. "
                "Esperado 'package.module:Symbol'."
            )


# ---- Skill -----------------------------------------------------------------


class SkillManifest(BaseManifest):
    """Capacidade reutilizável: prompt, tool, pipeline ou agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["skill"] = "skill"
    skill_type: Literal["prompt", "tool", "pipeline", "agent"]
    inputs: dict[str, str] = Field(
        default_factory=dict,
        description="Mapa nome→tipo (texto livre; validação estrita virá no U1).",
    )
    outputs: dict[str, str] = Field(default_factory=dict)
    examples: tuple[str, ...] = Field(default_factory=tuple)


# ---- Workflow --------------------------------------------------------------


class WorkflowStep(BaseModel):
    """Passo de um workflow. Validação completa de DAG entra no U4."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    uses: str = Field(
        description=(
            "Referência a uma capability (ex.: 'skill:search', 'agent:planner')."
        )
    )
    with_: dict[str, Any] = Field(
        default_factory=dict,
        alias="with",
        description="Argumentos para a capability.",
    )
    when: str | None = Field(
        default=None,
        description="Expressão de condição (avaliada pelo runtime do consumer).",
    )
    retries: int = Field(default=0, ge=0, le=10)
    timeout_s: int = Field(default=60, ge=1, le=86_400)


class WorkflowManifest(BaseManifest):
    """Grafo de passos com dependências, retries, timeouts e compensações."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["workflow"] = "workflow"
    steps: tuple[WorkflowStep, ...]
    compensations: dict[str, str] = Field(
        default_factory=dict,
        description="Mapa step_id → step_id de compensação (executado em rollback).",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        ids = [s.id for s in self.steps]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Workflow {self.id} tem step ids duplicados: {ids}")
        unknown = set(self.compensations) - set(ids)
        if unknown:
            raise ValueError(
                f"Compensações referenciam steps inexistentes: {sorted(unknown)}"
            )


# ---- Pack ------------------------------------------------------------------


class PackEntry(BaseModel):
    """Entrada de um pack apontando para outro manifesto."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_id: str
    version_range: str
    optional: bool = False


class PackManifest(BaseManifest):
    """Unidade distribuível que agrega agents, skills, workflows, configs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["pack"] = "pack"
    contents: tuple[PackEntry, ...]
    conflicts: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Manifest IDs que NÃO podem coexistir com este pack.",
    )
    migrations: dict[str, str] = Field(
        default_factory=dict,
        description="Mapa versão→passos de migração (texto livre no U0).",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        # Anti-gate: pack não pode ser publicado com conflicts apontando para si
        for c in self.conflicts:
            if c == str(self.id):
                raise ValueError(
                    f"Pack {self.id} conflita consigo mesmo (anti-gate)."
                )


# ---- Validação cruzada (independiente de registry) -----------------------


def detect_cycles(manifests: list[BaseManifest]) -> None:
    """Detecta ciclos nas dependências. Lança ``DependencyCycleError``.

    Implementação determinística (DFS) — sem libs externas.
    """
    graph: dict[str, list[str]] = {
        str(m.id): [str(d.id) for d in m.dependencies] for m in manifests
    }

    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(graph, white)

    def visit(node: str, path: list[str]) -> None:
        if color.get(node, white) == gray:
            cycle = " -> ".join([*path, node])
            raise DependencyCycleError(
                f"Ciclo detectado: {cycle}",
                context={"cycle": [*path, node]},
            )
        if color.get(node, white) == black:
            return
        color[node] = gray
        for nxt in graph.get(node, []):
            visit(nxt, [*path, node])
        color[node] = black

    for n in graph:
        if color[n] == white:
            visit(n, [])


def check_unique_versions(manifests: list[BaseManifest]) -> None:
    """Garante que cada (id) tem no máximo uma versão na lista.

    Útil para validação em batch; ``VersionConflictError`` se houver
    duas versões diferentes do mesmo id.
    """
    seen: dict[str, str] = {}
    for m in manifests:
        key = str(m.id)
        if key in seen and seen[key] != m.version:
            raise VersionConflictError(
                f"Conflito de versão para {key}: {seen[key]} vs {m.version}",
                context={"id": key, "versions": [seen[key], m.version]},
            )
        seen[key] = m.version
