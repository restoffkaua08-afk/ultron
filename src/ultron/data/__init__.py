"""Dados isolados por organização e namespace, com lineage explícito."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from ultron.core.errors import PermissionDeniedError, UltronError

_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


@dataclass(frozen=True, slots=True)
class NamespaceContext:
    organization_id: str
    consumer_id: str

    def __post_init__(self) -> None:
        if not _SEGMENT.fullmatch(self.organization_id) or not _SEGMENT.fullmatch(self.consumer_id):
            raise ValueError("identificador de contexto inválido")


@dataclass(frozen=True, slots=True)
class DataRecord:
    namespace: str
    key: str
    value: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str
    relation: str


@dataclass(frozen=True, slots=True)
class GraphProjection:
    nodes: tuple[DataRecord, ...]
    edges: tuple[GraphEdge, ...]


@dataclass(frozen=True, slots=True)
class RetentionPlan:
    organization_id: str
    namespace: str
    expired_keys: tuple[str, ...]
    evaluated_at: datetime


class NamespaceStore:
    """Store local cuja API não permite consultas sem contexto de organização."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    @classmethod
    @asynccontextmanager
    async def open(cls, path: Path) -> AsyncIterator[NamespaceStore]:
        store = cls(path)
        store._conn = await aiosqlite.connect(path)
        await store._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS namespace_records (
              organization_id TEXT NOT NULL, namespace TEXT NOT NULL,
              key TEXT NOT NULL, owner_consumer_id TEXT NOT NULL, value_json TEXT NOT NULL,
              created_at TEXT NOT NULL, expires_at TEXT,
              PRIMARY KEY (organization_id, namespace, key)
            );
            CREATE TABLE IF NOT EXISTS lineage_edges (
              organization_id TEXT NOT NULL, namespace TEXT NOT NULL,
              source_key TEXT NOT NULL, target_key TEXT NOT NULL, relation TEXT NOT NULL,
              PRIMARY KEY (organization_id, namespace, source_key, target_key, relation),
              FOREIGN KEY (organization_id, namespace, source_key)
                REFERENCES namespace_records(organization_id, namespace, key),
              FOREIGN KEY (organization_id, namespace, target_key)
                REFERENCES namespace_records(organization_id, namespace, key)
            );
            """
        )
        columns = {
            str(row[1])
            for row in await store._conn.execute_fetchall("PRAGMA table_info(namespace_records)")
        }
        if "created_at" not in columns:
            await store._conn.execute("ALTER TABLE namespace_records ADD COLUMN created_at TEXT")
            await store._conn.execute(
                "UPDATE namespace_records SET created_at=? WHERE created_at IS NULL",
                (datetime.now(tz=UTC).isoformat(),),
            )
        if "expires_at" not in columns:
            await store._conn.execute("ALTER TABLE namespace_records ADD COLUMN expires_at TEXT")
        await store._conn.execute("PRAGMA foreign_keys=ON")
        await store._conn.commit()
        try:
            yield store
        finally:
            await store._conn.close()

    async def put(
        self,
        context: NamespaceContext,
        namespace: str,
        key: str,
        value: dict[str, Any],
        *,
        expires_at: datetime | None = None,
    ) -> None:
        self._validate(namespace, key)
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO namespace_records VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                context.organization_id,
                namespace,
                key,
                context.consumer_id,
                _canonical(value),
                datetime.now(tz=UTC).isoformat(),
                expires_at.astimezone(UTC).isoformat() if expires_at is not None else None,
            ),
        )
        await self._conn.commit()

    async def get(self, context: NamespaceContext, namespace: str, key: str) -> DataRecord:
        self._validate(namespace, key)
        assert self._conn is not None
        rows = list(await self._conn.execute_fetchall(
            "SELECT value_json FROM namespace_records WHERE organization_id=? AND namespace=? AND key=?",
            (context.organization_id, namespace, key),
        ))
        if not rows:
            raise UltronError("registro não encontrado no namespace autorizado")
        return DataRecord(namespace, key, json.loads(rows[0][0]))

    async def list(self, context: NamespaceContext, namespace: str) -> list[DataRecord]:
        self._validate(namespace)
        assert self._conn is not None
        rows = await self._conn.execute_fetchall(
            "SELECT key,value_json FROM namespace_records WHERE organization_id=? AND namespace=? ORDER BY key",
            (context.organization_id, namespace),
        )
        return [DataRecord(namespace, row[0], json.loads(row[1])) for row in rows]

    async def add_lineage(self, context: NamespaceContext, namespace: str, source: str, target: str, relation: str) -> None:
        self._validate(namespace, source)
        self._validate(namespace, target)
        if not _SEGMENT.fullmatch(relation):
            raise ValueError("relação de lineage inválida")
        assert self._conn is not None
        try:
            await self._conn.execute(
                "INSERT INTO lineage_edges VALUES (?, ?, ?, ?, ?)",
                (context.organization_id, namespace, source, target, relation),
            )
            await self._conn.commit()
        except aiosqlite.IntegrityError as error:
            raise PermissionDeniedError("lineage não pode atravessar namespace ou organização") from error

    async def project_graph(
        self,
        context: NamespaceContext,
        namespace: str,
        *,
        roots: tuple[str, ...] = (),
        max_depth: int = 5,
    ) -> GraphProjection:
        """Projeta lineage no namespace, opcionalmente a partir de raízes."""
        self._validate(namespace)
        if not 0 <= max_depth <= 20:
            raise ValueError("max_depth deve estar entre 0 e 20")
        for root in roots:
            self._validate(namespace, root)
        assert self._conn is not None
        records = await self.list(context, namespace)
        rows = list(
            await self._conn.execute_fetchall(
                "SELECT source_key,target_key,relation FROM lineage_edges "
                "WHERE organization_id=? AND namespace=? "
                "ORDER BY source_key,target_key,relation",
                (context.organization_id, namespace),
            )
        )
        edges = tuple(GraphEdge(str(row[0]), str(row[1]), str(row[2])) for row in rows)
        if not roots:
            return GraphProjection(tuple(records), edges)

        visible = set(roots)
        frontier = set(roots)
        for _ in range(max_depth):
            next_frontier = {
                edge.target
                for edge in edges
                if edge.source in frontier and edge.target not in visible
            }
            if not next_frontier:
                break
            visible.update(next_frontier)
            frontier = next_frontier
        nodes = tuple(record for record in records if record.key in visible)
        selected_edges = tuple(
            edge for edge in edges if edge.source in visible and edge.target in visible
        )
        return GraphProjection(nodes, selected_edges)

    async def plan_retention(
        self,
        context: NamespaceContext,
        namespace: str,
        *,
        now: datetime | None = None,
    ) -> RetentionPlan:
        """Cria plano sem alterar dados; apenas registros com expiração explícita entram."""
        self._validate(namespace)
        evaluated_at = (now or datetime.now(tz=UTC)).astimezone(UTC)
        assert self._conn is not None
        rows = await self._conn.execute_fetchall(
            "SELECT key FROM namespace_records WHERE organization_id=? AND namespace=? "
            "AND expires_at IS NOT NULL AND expires_at<=? ORDER BY key",
            (context.organization_id, namespace, evaluated_at.isoformat()),
        )
        return RetentionPlan(
            context.organization_id,
            namespace,
            tuple(str(row[0]) for row in rows),
            evaluated_at,
        )

    async def apply_retention(self, context: NamespaceContext, plan: RetentionPlan) -> int:
        """Aplica somente o plano imutável e remove arestas órfãs atomicamente."""
        if context.organization_id != plan.organization_id:
            raise PermissionDeniedError("plano de retenção pertence a outra organização")
        assert self._conn is not None
        await self._conn.execute("BEGIN IMMEDIATE")
        try:
            removed = 0
            for key in plan.expired_keys:
                cursor = await self._conn.execute(
                    "DELETE FROM lineage_edges WHERE organization_id=? AND namespace=? "
                    "AND (source_key=? OR target_key=?)",
                    (plan.organization_id, plan.namespace, key, key),
                )
                await cursor.close()
                cursor = await self._conn.execute(
                    "DELETE FROM namespace_records WHERE organization_id=? AND namespace=? "
                    "AND key=? AND expires_at IS NOT NULL AND expires_at<=?",
                    (plan.organization_id, plan.namespace, key, plan.evaluated_at.isoformat()),
                )
                removed += cursor.rowcount
                await cursor.close()
            await self._conn.commit()
            return removed
        except Exception:
            await self._conn.rollback()
            raise

    @staticmethod
    def _validate(namespace: str, key: str | None = None) -> None:
        if not _SEGMENT.fullmatch(namespace) or (key is not None and not _SEGMENT.fullmatch(key)):
            raise ValueError("namespace ou chave inválida")


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "DataRecord",
    "GraphEdge",
    "GraphProjection",
    "NamespaceContext",
    "NamespaceStore",
    "RetentionPlan",
]
