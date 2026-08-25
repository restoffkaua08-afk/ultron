"""Lifecycle local: instalar continua separado de ativar e executar."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ultron.core.errors import CapabilityNotInstalledError, InstallationError
from ultron.lockfile import LockfileStore, UltronLockfile


class CapabilityState(BaseModel):
    """Estado operacional sem permissões ou dados de execução."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str
    active: bool = False


class LifecycleState(BaseModel):
    """Estado vinculado exatamente ao conteúdo do lockfile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_version: str = "1.0.0"
    lock_sha256: str
    capabilities: tuple[CapabilityState, ...]

    def canonical_bytes(self) -> bytes:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return f"{encoded}\n".encode()


class LifecycleStore:
    """Persistência atômica do estado operacional."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> LifecycleState | None:
        if not self.path.is_file():
            return None
        return LifecycleState.model_validate_json(self.path.read_bytes())

    def write(self, state: LifecycleState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".ultron-state-", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(state.canonical_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


class LifecycleManager:
    """Reconcilia e altera ativação sem executar código ou conceder grants."""

    def __init__(self, lockfiles: LockfileStore, states: LifecycleStore) -> None:
        self.lockfiles = lockfiles
        self.states = states

    def reconcile(self) -> LifecycleState:
        lockfile = self._lockfile()
        lock_digest = _lock_digest(lockfile)
        previous = self.states.read()
        previous_by_id = (
            {item.id: item for item in previous.capabilities} if previous is not None else {}
        )
        capabilities = tuple(
            CapabilityState(
                id=item.id,
                version=item.version,
                active=(
                    item.id in previous_by_id
                    and previous_by_id[item.id].version == item.version
                    and previous_by_id[item.id].active
                ),
            )
            for item in lockfile.capabilities
        )
        state = LifecycleState(
            lock_sha256=lock_digest,
            capabilities=capabilities,
        )
        self.states.write(state)
        return state

    def activate(self, capability_id: str) -> LifecycleState:
        return self._set_active(capability_id, active=True)

    def deactivate(self, capability_id: str) -> LifecycleState:
        return self._set_active(capability_id, active=False)

    def _set_active(self, capability_id: str, *, active: bool) -> LifecycleState:
        state = self.reconcile()
        if capability_id not in {item.id for item in state.capabilities}:
            raise CapabilityNotInstalledError(
                f"Capability não instalada: {capability_id}",
                context={"id": capability_id},
            )
        updated = state.model_copy(
            update={
                "capabilities": tuple(
                    item.model_copy(update={"active": active}) if item.id == capability_id else item
                    for item in state.capabilities
                )
            }
        )
        self.states.write(updated)
        return updated

    def _lockfile(self) -> UltronLockfile:
        lockfile = self.lockfiles.read()
        if lockfile is None:
            raise InstallationError("Nenhum lockfile instalado")
        return lockfile


def _lock_digest(lockfile: UltronLockfile) -> str:
    return hashlib.sha256(lockfile.canonical_bytes()).hexdigest()


__all__ = [
    "CapabilityState",
    "LifecycleManager",
    "LifecycleState",
    "LifecycleStore",
]
