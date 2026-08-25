from ultron.consumer import CONSUMER_PROTOCOL_VERSION, ConsumerAdapter
from ultron.protocol import OPERATION_BINDINGS, protocol_descriptor


def test_every_python_operation_has_unique_rest_and_mcp_binding() -> None:
    methods = [item.python_method for item in OPERATION_BINDINGS]
    assert set(methods) == set(ConsumerAdapter.__abstractmethods__)
    assert len(methods) == len(set(methods))
    assert len({item.mcp_tool for item in OPERATION_BINDINGS}) == len(OPERATION_BINDINGS)
    assert len({(item.rest_method, item.rest_path) for item in OPERATION_BINDINGS}) == len(
        OPERATION_BINDINGS
    )


def test_every_mutation_requires_confirmation() -> None:
    assert all(item.requires_confirmation for item in OPERATION_BINDINGS if item.mutating)
    assert all(not item.requires_confirmation for item in OPERATION_BINDINGS if not item.mutating)


def test_descriptor_is_versioned() -> None:
    assert protocol_descriptor()["protocol_version"] == CONSUMER_PROTOCOL_VERSION
