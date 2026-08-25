from typing import Any

import pytest

from ultron.consumer import CapabilityRef, ConsumerAdapter, InstallPlan
from ultron.core.base import BaseManifest
from ultron.core.errors import OfflineMutationError
from ultron.offline import CatalogSnapshotStore, ResilientConsumerAdapter


class ReferenceConsumer(ConsumerAdapter):
    def __init__(self) -> None:
        self.native_tools = {"chat", "files"}
        self.catalog = [CapabilityRef("acme/search", "1.0.0", "skill")]
        self.mutations: list[str] = []

    def get_capabilities(self) -> list[CapabilityRef]:
        return self.catalog

    def check_compatibility(self, manifest: BaseManifest) -> tuple[bool, list[str]]:
        return True, []

    def install(self, manifest: BaseManifest) -> InstallPlan:
        self.mutations.append("install")
        return InstallPlan("plan", ())

    def activate(self, capability_id: str) -> None:
        self.mutations.append("activate")

    def deactivate(self, capability_id: str) -> None:
        self.mutations.append("deactivate")

    def remove(self, capability_id: str) -> None:
        self.mutations.append("remove")

    def list_installed(self) -> list[CapabilityRef]:
        return []

    def get_status(self, capability_id: str) -> dict[str, Any]:
        return {"installed": False}


def test_consumer_keeps_native_tools_and_cached_catalog_when_ultron_goes_offline(tmp_path) -> None:
    online = True
    primary = ReferenceConsumer()
    adapter = ResilientConsumerAdapter(
        primary, CatalogSnapshotStore(tmp_path / "catalog.json"), lambda: online
    )
    assert adapter.get_capabilities() == primary.catalog
    online = False

    assert adapter.get_capabilities() == primary.catalog
    assert primary.native_tools == {"chat", "files"}
    for mutation in (adapter.activate, adapter.deactivate, adapter.remove):
        with pytest.raises(OfflineMutationError):
            mutation("acme/search")
    assert primary.mutations == []


def test_mutations_delegate_normally_online(tmp_path) -> None:
    primary = ReferenceConsumer()
    adapter = ResilientConsumerAdapter(
        primary, CatalogSnapshotStore(tmp_path / "catalog.json"), lambda: True
    )
    adapter.activate("acme/search")
    adapter.deactivate("acme/search")
    adapter.remove("acme/search")
    assert primary.mutations == ["activate", "deactivate", "remove"]
