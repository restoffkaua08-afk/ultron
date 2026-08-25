"""Descoberta offline-first para qualquer consumer do ULTRON."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ultron.consumer import CapabilityRef, ConsumerAdapter, InstallPlan
from ultron.core.base import BaseManifest
from ultron.core.errors import ConsumerUnavailableError, IntegrityError, OfflineMutationError


@dataclass(frozen=True, slots=True)
class OfflineDiscovery:
    capabilities: tuple[CapabilityRef, ...]
    source: str
    synchronized_at: datetime


class CatalogSnapshotStore:
    """Snapshot local atômico com hash; nunca representa catálogo vazio silenciosamente."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, capabilities: list[CapabilityRef], synchronized_at: datetime) -> None:
        unique = sorted(set(capabilities), key=lambda item: (item.id, item.version, item.kind))
        payload = {
            "protocol_version": "1.0.0",
            "synchronized_at": synchronized_at.astimezone(UTC).isoformat(),
            "capabilities": [asdict(item) for item in unique],
        }
        encoded = _canonical(payload)
        envelope = _canonical({"payload": payload, "sha256": hashlib.sha256(encoded).hexdigest()})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".ultron-catalog-", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(envelope)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def read(self) -> OfflineDiscovery:
        try:
            envelope = json.loads(self.path.read_bytes())
            payload = envelope["payload"]
            expected = hashlib.sha256(_canonical(payload)).hexdigest()
            if envelope["sha256"] != expected:
                raise IntegrityError("snapshot local do catálogo foi adulterado")
            capabilities = tuple(CapabilityRef(**item) for item in payload["capabilities"])
            return OfflineDiscovery(
                capabilities, "cache", datetime.fromisoformat(payload["synchronized_at"])
            )
        except IntegrityError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ConsumerUnavailableError(
                "snapshot local ausente ou inválido", context={"path": str(self.path)}
            ) from error


class ResilientCatalog:
    def __init__(self, snapshots: CatalogSnapshotStore) -> None:
        self._snapshots = snapshots

    def discover(self, fetch_remote: Callable[[], list[CapabilityRef]]) -> OfflineDiscovery:
        try:
            capabilities = fetch_remote()
        except (ConnectionError, TimeoutError, OSError):
            return self._snapshots.read()
        synchronized_at = datetime.now(tz=UTC)
        self._snapshots.write(capabilities, synchronized_at)
        return OfflineDiscovery(tuple(capabilities), "remote", synchronized_at)


class ResilientConsumerAdapter(ConsumerAdapter):
    """Decorator universal: leitura offline, mutações somente online."""

    def __init__(
        self,
        primary: ConsumerAdapter,
        snapshots: CatalogSnapshotStore,
        is_online: Callable[[], bool],
    ) -> None:
        self._primary = primary
        self._catalog = ResilientCatalog(snapshots)
        self._is_online = is_online

    def get_capabilities(self) -> list[CapabilityRef]:
        def fetch() -> list[CapabilityRef]:
            if not self._is_online():
                raise ConnectionError("registry offline")
            return self._primary.get_capabilities()

        return list(self._catalog.discover(fetch).capabilities)

    def check_compatibility(self, manifest: BaseManifest) -> tuple[bool, list[str]]:
        return self._primary.check_compatibility(manifest)

    def install(self, manifest: BaseManifest) -> InstallPlan:
        self._require_online("install")
        return self._primary.install(manifest)

    def activate(self, capability_id: str) -> None:
        self._require_online("activate")
        self._primary.activate(capability_id)

    def deactivate(self, capability_id: str) -> None:
        self._require_online("deactivate")
        self._primary.deactivate(capability_id)

    def remove(self, capability_id: str) -> None:
        self._require_online("remove")
        self._primary.remove(capability_id)

    def list_installed(self) -> list[CapabilityRef]:
        return self._primary.list_installed()

    def get_status(self, capability_id: str) -> dict[str, object]:
        return self._primary.get_status(capability_id)

    def _require_online(self, operation: str) -> None:
        if not self._is_online():
            raise OfflineMutationError(
                "mutação recusada enquanto o Ultron está offline",
                context={"operation": operation},
            )


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


__all__ = [
    "CatalogSnapshotStore",
    "OfflineDiscovery",
    "ResilientCatalog",
    "ResilientConsumerAdapter",
]
