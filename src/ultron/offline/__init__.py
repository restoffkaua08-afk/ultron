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

from ultron.consumer import CapabilityRef
from ultron.core.errors import ConsumerUnavailableError, IntegrityError


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


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


__all__ = ["CatalogSnapshotStore", "OfflineDiscovery", "ResilientCatalog"]
