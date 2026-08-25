import pytest

from ultron.consumer import CONSUMER_PROTOCOL_VERSION, ConsumerDescriptor
from ultron.core.base import DependencyRef
from ultron.core.ids import ManifestId, UltronVersionRange
from ultron.graph import build_operational_graph
from ultron.lockfile import LockedCapability, UltronLockfile


def test_graph_combines_manifests_dependencies_and_installations(make_agent, make_skill):
    skill = make_skill(version="1.0.0")
    agent = make_agent(
        dependencies=(
            DependencyRef(
                id=ManifestId.parse("acme/summarize"),
                version_range=UltronVersionRange(">=1.0.0,<2.0.0"),
            ),
        )
    )
    consumer = ConsumerDescriptor("claude-main", CONSUMER_PROTOCOL_VERSION, ("mcp",))
    lockfile = UltronLockfile(
        root="acme/research-agent@1.0.0",
        capabilities=(
            LockedCapability(
                id="acme/research-agent",
                version="1.0.0",
                kind="agent",
                digest="a" * 64,
                dependencies=("acme/summarize@1.0.0",),
            ),
            LockedCapability(id="acme/summarize", version="1.0.0", kind="skill", digest="b" * 64),
        ),
    )

    graph = build_operational_graph(
        (agent, skill), (consumer,), ((consumer.consumer_id, lockfile),)
    )

    assert any(edge.relation == "depends_on" for edge in graph.edges)
    assert any(edge.relation == "installed" for edge in graph.edges)
    assert any(edge.relation == "resolved_to" for edge in graph.edges)
    assert [node.id for node in graph.neighbors("consumer:claude-main")] == [
        "capability:acme/research-agent@1.0.0",
        "capability:acme/summarize@1.0.0",
    ]


def test_graph_rejects_installation_for_unknown_consumer():
    lockfile = UltronLockfile(root="acme/x@1.0.0", capabilities=())
    with pytest.raises(ValueError, match="consumer desconhecido"):
        build_operational_graph((), installations=(("missing", lockfile),))


def test_graph_output_is_deterministic(make_agent, make_skill):
    left = build_operational_graph((make_agent(), make_skill()))
    right = build_operational_graph((make_skill(), make_agent()))
    assert left == right
