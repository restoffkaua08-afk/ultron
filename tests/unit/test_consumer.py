"""Testes do contrato do Consumer Adapter."""

from __future__ import annotations

import pytest

from ultron.consumer import (
    CONSUMER_PROTOCOL_VERSION,
    CapabilityRef,
    ConsumerAdapter,
    InstallPlan,
)


class _FakeAdapter(ConsumerAdapter):
    """Adapter mínimo para validar o contrato abstrato."""

    def __init__(self) -> None:
        self.installed: dict[str, CapabilityRef] = {}
        self.activated: set[str] = set()

    def get_capabilities(self):
        return list(self.installed.values())

    def check_compatibility(self, manifest):
        return True, []

    def install(self, manifest):
        self.installed[str(manifest.id)] = CapabilityRef(
            id=str(manifest.id),
            version=manifest.version,
            kind=manifest.kind,
        )
        return InstallPlan(
            plan_id=f"plan-{manifest.version}",
            to_install=(self.installed[str(manifest.id)],),
        )

    def activate(self, capability_id):
        if capability_id not in self.installed:
            raise KeyError(capability_id)
        self.activated.add(capability_id)

    def deactivate(self, capability_id):
        self.activated.discard(capability_id)

    def remove(self, capability_id):
        self.installed.pop(capability_id, None)
        self.activated.discard(capability_id)

    def list_installed(self):
        return list(self.installed.values())

    def get_status(self, capability_id):
        return {
            "id": capability_id,
            "installed": capability_id in self.installed,
            "activated": capability_id in self.activated,
        }


class TestConsumerContract:
    def test_protocol_version_inicia_em_1(self) -> None:
        assert CONSUMER_PROTOCOL_VERSION == "1.0.0"

    def test_classe_abstrata_nao_instanciavel(self) -> None:
        with pytest.raises(TypeError):
            ConsumerAdapter()  # type: ignore[abstract]

    def test_fake_adapter_implementa_contrato(self, make_agent) -> None:
        adapter = _FakeAdapter()
        agent = make_agent()
        plan = adapter.install(agent)
        assert plan.to_install[0].id == "acme/research-agent"
        assert adapter.get_status("acme/research-agent")["installed"] is True
        adapter.activate("acme/research-agent")
        assert adapter.get_status("acme/research-agent")["activated"] is True
        adapter.remove("acme/research-agent")
        assert adapter.get_status("acme/research-agent")["installed"] is False
