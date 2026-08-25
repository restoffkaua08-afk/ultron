"""Propagação fail-closed de revogações para instalações locais."""

from __future__ import annotations

from dataclasses import dataclass

from ultron.lifecycle import LifecycleManager
from ultron.lockfile import LockfileStore
from ultron.registry import Registry, RegistryStatus


@dataclass(frozen=True, slots=True)
class RevocationReport:
    revoked: tuple[str, ...]
    impacted: tuple[str, ...]
    deactivated: tuple[str, ...]


class RevocationManager:
    """Desativa versões revogadas e todos os seus dependentes transitivos."""

    def __init__(
        self,
        registry: Registry,
        lockfiles: LockfileStore,
        lifecycle: LifecycleManager,
    ) -> None:
        self.registry = registry
        self.lockfiles = lockfiles
        self.lifecycle = lifecycle

    async def propagate(self) -> RevocationReport:
        lockfile = self.lockfiles.read()
        if lockfile is None:
            return RevocationReport((), (), ())
        revoked_ids: set[str] = set()
        revoked_refs: set[str] = set()
        for item in lockfile.capabilities:
            entry = await self.registry.get(item.id, item.version)
            if entry.status == RegistryStatus.REVOKED:
                revoked_ids.add(item.id)
                revoked_refs.add(f"{item.id}@{item.version}")

        impacted = set(revoked_ids)
        changed = True
        while changed:
            changed = False
            for item in lockfile.capabilities:
                dependency_ids = {dependency.rsplit("@", 1)[0] for dependency in item.dependencies}
                if item.id not in impacted and dependency_ids & impacted:
                    impacted.add(item.id)
                    changed = True

        state = self.lifecycle.reconcile()
        deactivated = {
            item.id for item in state.capabilities if item.id in impacted and item.active
        }
        if impacted:
            self.lifecycle.deactivate_many(frozenset(impacted))
        return RevocationReport(
            tuple(sorted(revoked_refs)),
            tuple(sorted(impacted)),
            tuple(sorted(deactivated)),
        )


__all__ = ["RevocationManager", "RevocationReport"]
