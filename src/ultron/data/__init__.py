"""Dados isolados por organização e namespace, com lineage explícito."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
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
        await store._conn.execute("PRAGMA foreign_keys=ON")
        await store._conn.commit()
        try:
            yield store
        finally:
            await store._conn.close()

    async def put(self, context: NamespaceContext, namespace: str, key: str, value: dict[str, Any]) -> None:
        self._validate(namespace, key)
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO namespace_records VALUES (?, ?, ?, ?, ?)",
            (context.organization_id, namespace, key, context.consumer_id, _canonical(value)),
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

    @staticmethod
    def _validate(namespace: str, key: str | None = None) -> None:
        if not _SEGMENT.fullmatch(namespace) or (key is not None and not _SEGMENT.fullmatch(key)):
            raise ValueError("namespace ou chave inválida")


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = ["DataRecord", "NamespaceContext", "NamespaceStore"]
