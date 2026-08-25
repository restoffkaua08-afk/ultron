from datetime import UTC, datetime

import pytest

from ultron.consumer import CapabilityRef
from ultron.core.errors import ConsumerUnavailableError, IntegrityError
from ultron.offline import CatalogSnapshotStore, ResilientCatalog


def _catalog() -> list[CapabilityRef]:
    return [CapabilityRef("acme/search", "1.0.0", "skill")]


def test_remote_catalog_is_cached_and_reused_offline(tmp_path) -> None:
    resilient = ResilientCatalog(CatalogSnapshotStore(tmp_path / "catalog.json"))
    online = resilient.discover(_catalog)
    offline = resilient.discover(lambda: (_ for _ in ()).throw(ConnectionError()))
    assert online.source == "remote"
    assert offline.source == "cache"
    assert offline.capabilities == tuple(_catalog())


def test_offline_without_snapshot_fails_typed_instead_of_returning_empty(tmp_path) -> None:
    resilient = ResilientCatalog(CatalogSnapshotStore(tmp_path / "missing.json"))
    with pytest.raises(ConsumerUnavailableError) as caught:
        resilient.discover(lambda: (_ for _ in ()).throw(TimeoutError()))
    assert caught.value.code == "CONSUMER_OFFLINE_UNAVAILABLE"


def test_tampered_snapshot_is_rejected(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    store = CatalogSnapshotStore(path)
    store.write(_catalog(), datetime.now(tz=UTC))
    path.write_bytes(path.read_bytes().replace(b"acme/search", b"evil/search"))
    with pytest.raises(IntegrityError):
        store.read()


def test_snapshot_is_deterministic_and_deduplicated(tmp_path) -> None:
    store = CatalogSnapshotStore(tmp_path / "catalog.json")
    timestamp = datetime(2026, 8, 25, tzinfo=UTC)
    store.write(_catalog() * 2, timestamp)
    first = store.path.read_bytes()
    store.write(_catalog(), timestamp)
    assert store.path.read_bytes() == first
    assert len(store.read().capabilities) == 1
