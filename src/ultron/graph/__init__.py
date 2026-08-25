"""Projeção determinística do grafo operacional do ULTRON."""

from __future__ import annotations

from dataclasses import dataclass

from ultron.consumer import ConsumerDescriptor
from ultron.core.base import BaseManifest
from ultron.lockfile import UltronLockfile


@dataclass(frozen=True, slots=True, order=True)
class OperationalNode:
    id: str
    kind: str
    label: str
    version: str | None = None


@dataclass(frozen=True, slots=True, order=True)
class OperationalEdge:
    source: str
    target: str
    relation: str
    constraint: str | None = None


@dataclass(frozen=True, slots=True)
class OperationalGraph:
    nodes: tuple[OperationalNode, ...]
    edges: tuple[OperationalEdge, ...]

    def neighbors(self, node_id: str) -> tuple[OperationalNode, ...]:
        adjacent = {
            edge.target if edge.source == node_id else edge.source
            for edge in self.edges
            if node_id in {edge.source, edge.target}
        }
        return tuple(node for node in self.nodes if node.id in adjacent)


def build_operational_graph(
    manifests: tuple[BaseManifest, ...],
    consumers: tuple[ConsumerDescriptor, ...] = (),
    installations: tuple[tuple[str, UltronLockfile], ...] = (),
) -> OperationalGraph:
    """Une catálogo, dependências e instalações sem consultar estado global."""
    nodes: dict[str, OperationalNode] = {}
    edges: set[OperationalEdge] = set()

    for manifest in manifests:
        node_id = _capability_node(str(manifest.id), manifest.version)
        nodes[node_id] = OperationalNode(node_id, manifest.kind, str(manifest.id), manifest.version)
        for dependency in manifest.dependencies:
            target = f"capability:{dependency.id}"
            nodes.setdefault(target, OperationalNode(target, "capability", str(dependency.id)))
            edges.add(OperationalEdge(node_id, target, "depends_on", str(dependency.version_range)))

    for consumer in consumers:
        node_id = f"consumer:{consumer.consumer_id}"
        nodes[node_id] = OperationalNode(node_id, "consumer", consumer.consumer_id)

    known_consumers = {consumer.consumer_id for consumer in consumers}
    for consumer_id, lockfile in installations:
        if consumer_id not in known_consumers:
            raise ValueError(f"instalação referencia consumer desconhecido: {consumer_id}")
        consumer_node = f"consumer:{consumer_id}"
        for capability in lockfile.capabilities:
            capability_node = _capability_node(capability.id, capability.version)
            nodes.setdefault(
                capability_node,
                OperationalNode(
                    capability_node, capability.kind, capability.id, capability.version
                ),
            )
            edges.add(OperationalEdge(consumer_node, capability_node, "installed"))
            for locked_dependency in capability.dependencies:
                dep_id, dep_version = locked_dependency.rsplit("@", 1)
                dependency_node = _capability_node(dep_id, dep_version)
                nodes.setdefault(
                    dependency_node,
                    OperationalNode(dependency_node, "capability", dep_id, dep_version),
                )
                edges.add(OperationalEdge(capability_node, dependency_node, "resolved_to"))

    return OperationalGraph(tuple(sorted(nodes.values())), tuple(sorted(edges)))


def _capability_node(capability_id: str, version: str) -> str:
    return f"capability:{capability_id}@{version}"


__all__ = [
    "OperationalEdge",
    "OperationalGraph",
    "OperationalNode",
    "build_operational_graph",
]
