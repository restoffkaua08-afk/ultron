"""Persistência transacional de instalações por organização e consumer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from ultron.core.errors import (
    CapabilityNotInstalledError,
    InstallationError,
    UnsafeRemovalError,
)

_SCOPE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS consumer_installations (
    organization_id TEXT NOT NULL,
    consumer_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    version TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('agent', 'skill', 'workflow', 'pack')),
    payload_sha256 TEXT NOT NULL CHECK (
        length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    is_root INTEGER NOT NULL DEFAULT 0 CHECK (is_root IN (0, 1)),
    active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
    installed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (organization_id, consumer_id, capability_id)
);

CREATE INDEX IF NOT EXISTS consumer_installations_scope_idx
ON consumer_installations (organization_id, consumer_id, active, capability_id);

CREATE TABLE IF NOT EXISTS consumer_installation_dependencies (
    organization_id TEXT NOT NULL,
    consumer_id TEXT NOT NULL,
    dependent_id TEXT NOT NULL,
    dependency_id TEXT NOT NULL,
    PRIMARY KEY (organization_id, consumer_id, dependent_id, dependency_id),
    FOREIGN KEY (organization_id, consumer_id, dependent_id)
      REFERENCES consumer_installations (organization_id, consumer_id, capability_id)
      ON DELETE CASCADE,
    FOREIGN KEY (organization_id, consumer_id, dependency_id)
      REFERENCES consumer_installations (organization_id, consumer_id, capability_id)
      ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS consumer_dependencies_target_idx
ON consumer_installation_dependencies (
    organization_id, consumer_id, dependency_id, dependent_id
);

CREATE TABLE IF NOT EXISTS consumer_installation_audit (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id TEXT NOT NULL,
    consumer_id TEXT NOT NULL,
    action TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS consumer_installation_audit_scope_idx
ON consumer_installation_audit (organization_id, consumer_id, occurred_at DESC);
"""


@dataclass(frozen=True, slots=True)
class InstallationRecord:
    capability_id: str
    version: str
    kind: str
    payload_sha256: str
    dependencies: tuple[str, ...] = ()
    is_root: bool = False
    active: bool = False


class ConsumerInstallationStore:
    """Store local equivalente ao modelo cloud, sem estado global entre tenants."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def install(
        self,
        organization_id: str,
        consumer_id: str,
        records: tuple[InstallationRecord, ...],
    ) -> tuple[InstallationRecord, ...]:
        self._scope(organization_id, consumer_id)
        if not records or sum(record.is_root for record in records) != 1:
            raise InstallationError("Plano precisa conter exatamente uma capability raiz")
        ids = [record.capability_id for record in records]
        if len(ids) != len(set(ids)):
            raise InstallationError("Plano contém capabilities duplicadas")
        planned = set(ids)
        if any(set(record.dependencies) - planned for record in records):
            raise InstallationError("Plano referencia dependência ausente")

        conn = self._connection()
        now = datetime.now(tz=UTC).isoformat()
        await conn.execute("BEGIN IMMEDIATE")
        try:
            placeholders = ",".join("?" for _ in records)
            existing = await conn.execute_fetchall(
                f"""SELECT capability_id, version FROM consumer_installations
                    WHERE organization_id = ? AND consumer_id = ?
                      AND capability_id IN ({placeholders})""",
                (organization_id, consumer_id, *ids),
            )
            versions = {str(row["capability_id"]): str(row["version"]) for row in existing}
            conflicts = [
                record.capability_id
                for record in records
                if record.capability_id in versions
                and versions[record.capability_id] != record.version
            ]
            if conflicts:
                raise InstallationError(
                    "Plano conflita com versões já instaladas",
                    context={"capability_ids": sorted(conflicts)},
                )
            for record in records:
                await conn.execute(
                    """INSERT INTO consumer_installations (
                        organization_id, consumer_id, capability_id, version, kind,
                        payload_sha256, is_root, active, installed_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                    ON CONFLICT (organization_id, consumer_id, capability_id) DO UPDATE SET
                        is_root = max(is_root, excluded.is_root),
                        updated_at = excluded.updated_at""",
                    (
                        organization_id,
                        consumer_id,
                        record.capability_id,
                        record.version,
                        record.kind,
                        record.payload_sha256,
                        int(record.is_root),
                        now,
                        now,
                    ),
                )
            for record in records:
                for dependency_id in record.dependencies:
                    await conn.execute(
                        """INSERT OR IGNORE INTO consumer_installation_dependencies (
                            organization_id, consumer_id, dependent_id, dependency_id
                        ) VALUES (?, ?, ?, ?)""",
                        (organization_id, consumer_id, record.capability_id, dependency_id),
                    )
            root = next(record for record in records if record.is_root)
            await self._audit(conn, organization_id, consumer_id, "install", root.capability_id)
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        return await self.list(organization_id, consumer_id)

    async def list(self, organization_id: str, consumer_id: str) -> tuple[InstallationRecord, ...]:
        self._scope(organization_id, consumer_id)
        conn = self._connection()
        rows = await conn.execute_fetchall(
            """SELECT * FROM consumer_installations
               WHERE organization_id = ? AND consumer_id = ?
               ORDER BY capability_id""",
            (organization_id, consumer_id),
        )
        return tuple([await self._record(row) for row in rows])

    async def status(
        self, organization_id: str, consumer_id: str, capability_id: str
    ) -> InstallationRecord:
        self._scope(organization_id, consumer_id)
        rows = list(
            await self._connection().execute_fetchall(
                """SELECT * FROM consumer_installations
               WHERE organization_id = ? AND consumer_id = ? AND capability_id = ?""",
                (organization_id, consumer_id, capability_id),
            )
        )
        if not rows:
            raise CapabilityNotInstalledError(
                f"Capability não instalada: {capability_id}", context={"id": capability_id}
            )
        return await self._record(rows[0])

    async def set_active(
        self, organization_id: str, consumer_id: str, capability_id: str, *, active: bool
    ) -> InstallationRecord:
        await self.status(organization_id, consumer_id, capability_id)
        conn = self._connection()
        now = datetime.now(tz=UTC).isoformat()
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await conn.execute(
                """UPDATE consumer_installations SET active = ?, updated_at = ?
                   WHERE organization_id = ? AND consumer_id = ? AND capability_id = ?""",
                (int(active), now, organization_id, consumer_id, capability_id),
            )
            await self._audit(
                conn,
                organization_id,
                consumer_id,
                "activate" if active else "deactivate",
                capability_id,
            )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        return await self.status(organization_id, consumer_id, capability_id)

    async def remove(self, organization_id: str, consumer_id: str, capability_id: str) -> None:
        current = await self.status(organization_id, consumer_id, capability_id)
        if current.is_root:
            raise UnsafeRemovalError("A capability raiz não pode ser removida")
        if current.active:
            raise UnsafeRemovalError("Desative a capability antes de removê-la")
        conn = self._connection()
        dependents = await conn.execute_fetchall(
            """SELECT dependent_id FROM consumer_installation_dependencies
               WHERE organization_id = ? AND consumer_id = ? AND dependency_id = ?""",
            (organization_id, consumer_id, capability_id),
        )
        if dependents:
            raise UnsafeRemovalError(
                "Capability ainda possui dependentes",
                context={"dependents": sorted(str(row["dependent_id"]) for row in dependents)},
            )
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await conn.execute(
                """DELETE FROM consumer_installations
                   WHERE organization_id = ? AND consumer_id = ? AND capability_id = ?""",
                (organization_id, consumer_id, capability_id),
            )
            await self._audit(conn, organization_id, consumer_id, "remove", capability_id)
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    async def _record(self, row: aiosqlite.Row) -> InstallationRecord:
        dependencies = await self._connection().execute_fetchall(
            """SELECT dependency_id FROM consumer_installation_dependencies
               WHERE organization_id = ? AND consumer_id = ? AND dependent_id = ?
               ORDER BY dependency_id""",
            (row["organization_id"], row["consumer_id"], row["capability_id"]),
        )
        return InstallationRecord(
            capability_id=str(row["capability_id"]),
            version=str(row["version"]),
            kind=str(row["kind"]),
            payload_sha256=str(row["payload_sha256"]),
            dependencies=tuple(str(item["dependency_id"]) for item in dependencies),
            is_root=bool(row["is_root"]),
            active=bool(row["active"]),
        )

    async def _audit(
        self,
        conn: aiosqlite.Connection,
        organization_id: str,
        consumer_id: str,
        action: str,
        capability_id: str,
    ) -> None:
        await conn.execute(
            """INSERT INTO consumer_installation_audit (
                organization_id, consumer_id, action, capability_id, occurred_at
            ) VALUES (?, ?, ?, ?, ?)""",
            (organization_id, consumer_id, action, capability_id, datetime.now(tz=UTC).isoformat()),
        )

    def _connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("ConsumerInstallationStore não inicializado")
        return self._conn

    @staticmethod
    def _scope(organization_id: str, consumer_id: str) -> None:
        if not _SCOPE_PATTERN.fullmatch(organization_id) or not _SCOPE_PATTERN.fullmatch(
            consumer_id
        ):
            raise ValueError("organization_id ou consumer_id inválido")


__all__ = ["ConsumerInstallationStore", "InstallationRecord"]
