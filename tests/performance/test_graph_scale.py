"""Contrato de escala da projeção em memória, sem depender de tempo de máquina."""

from ultron.graph import OperationalEdge, OperationalGraph, OperationalNode


def test_graph_search_stays_bounded_and_consistent_at_ten_thousand_nodes() -> None:
    nodes = tuple(
        OperationalNode(
            id=f"capability:acme/node-{index:05d}@1.0.0",
            kind="skill",
            label=f"acme/node-{index:05d}",
            version="1.0.0",
        )
        for index in range(10_000)
    )
    edges = tuple(
        OperationalEdge(nodes[index].id, nodes[index + 1].id, "depends_on")
        for index in range(len(nodes) - 1)
    )
    graph = OperationalGraph(nodes, edges)

    result = graph.search("node-09", kind="skill", relation="depends_on", limit=50)

    assert len(result.nodes) == 50
    visible = {node.id for node in result.nodes}
    assert all(edge.source in visible and edge.target in visible for edge in result.edges)
    assert result == graph.search("NODE-09", kind="skill", relation="depends_on", limit=50)
