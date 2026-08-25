"""Registry — fonte de metadados das capabilities publicadas.

Implementa o gate U1 do ULTRON:

* CRUD sobre manifests (publish, get, list, delete)
* Busca via SQLite FTS5
* Filtros (tipo, capability, runtime, publisher, license, risk, status)
* Imutabilidade: manifest publicado nunca é mutado (só nova versão)

Armazenamento: ``~/.ultron/registry.db`` (criado sob demanda).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import aiosqlite
import structlog

from ultron.core.base import BaseManifest
from ultron.core.errors import (
    InvalidManifestError,
    UltronError,
    VersionConflictError,
)
from ultron.core.ids import ManifestId

_log = structlog.get_logger("ultron.registry")

DEFAULT_REGISTRY_PATH = Path(
    os.environ.get("ULTRON_REGISTRY_PATH", "~/.ultron/registry.db")
).expanduser()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS manifests (
    id TEXT NOT NULL,
    version TEXT NOT NULL,
    kind TEXT NOT NULL,
    publisher TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    license TEXT NOT NULL,
    risk TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    published_at TEXT NOT NULL,
    PRIMARY KEY (id, version)
);

CREATE INDEX IF NOT EXISTS ix_manifests_publisher ON manifests(publisher);
CREATE INDEX IF NOT EXISTS ix_manifests_kind ON manifests(kind);
CREATE INDEX IF NOT EXISTS ix_manifests_risk ON manifests(risk);

CREATE VIRTUAL TABLE IF NOT EXISTS manifests_fts USING fts5(
    id UNINDEXED,
    version UNINDEXED,
    kind UNINDEXED,
    publisher UNINDEXED,
    name,
    description,
    capabilities,
    tags,
    license UNINDEXED,
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target_id TEXT,
    target_version TEXT,
    payload_hash TEXT,
    correlation_id TEXT
);

CREATE INDEX IF NOT EXISTS ix_audit_occurred ON audit(occurred_at);
CREATE INDEX IF NOT EXISTS ix_audit_target ON audit(target_id, target_version);
"""


class RegistryStatus(str, Enum):  # noqa: UP042 — compatibility w/ existing usage
    """Estado de uma capability no registry."""

    PUBLISHED = "published"  # visível, pode ser instalada
    DEPRECATED = "deprecated"  # marcada como antiga, ainda instalável
    QUARANTINED = "quarantined"  # retida pela validação de segurança
    REVOKED = "revoked"  # removida de novas instalações


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """Manifest + metadados de registro."""

    manifest: BaseManifest
    status: RegistryStatus
    published_at: datetime
    payload_hash: str


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """Query de busca com filtros."""

    text: str = ""
    kind: Literal["agent", "skill", "workflow", "pack"] | None = None
    capability: str | None = None
    runtime: str | None = None
    publisher: str | None = None
    license: str | None = None
    risk: str | None = None
    status: RegistryStatus | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 500:
            raise ValueError("limit deve estar entre 1 e 500")
        if self.offset < 0:
            raise ValueError("offset deve ser >= 0")


@dataclass(frozen=True, slots=True)
class RegistryStats:
    """Estatísticas agregadas do registry."""

    total: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    by_publisher: dict[str, int] = field(default_factory=dict)
    by_risk: dict[str, int] = field(default_factory=dict)
    latest_migration: int = 0
    last_audit_event: datetime | None = None


# ---- Operações de I/O -----------------------------------------------------


def _manifest_to_row(
    manifest: BaseManifest,
) -> tuple[str, str, str, str, str, str, str, str, str, str, str]:
    """Serializa um manifest para a linha do SQLite."""
    payload = manifest.model_dump_json()
    return (
        str(manifest.id),
        manifest.version,
        manifest.kind,
        manifest.publisher,
        manifest.id.name,
        manifest.description,
        manifest.license,
        manifest.risks.value,
        manifest.schema_version,
        payload,
        _hash_payload(payload),
    )


def _hash_payload(payload: str) -> str:
    """Hash SHA-256 determinístico do payload JSON canônico."""
    import hashlib

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_to_entry(
    row: aiosqlite.Row,
) -> RegistryEntry:
    """Desserializa uma linha do SQLite em ``RegistryEntry``."""
    from ultron.core.manifests import (
        AgentManifest,
        PackManifest,
        SkillManifest,
        WorkflowManifest,
    )

    payload = json.loads(row["payload_json"])
    # id pode estar como dict {publisher,name} (Pydantic default) ou string "pub/name"
    raw_id = payload["id"]
    if isinstance(raw_id, dict):
        payload["id"] = ManifestId(
            publisher=raw_id["publisher"],
            name=raw_id["name"],
        )
    else:
        payload["id"] = ManifestId.parse(raw_id)
    kind = row["kind"]
    cls = {
        "agent": AgentManifest,
        "skill": SkillManifest,
        "workflow": WorkflowManifest,
        "pack": PackManifest,
    }[kind]
    # mypy: cls[Any] não tem model_validate exposto estaticamente, mas funciona em runtime
    manifest = cls.model_validate(payload)  # type: ignore[attr-defined]
    fallback_status = RegistryStatus.PUBLISHED
    actual_status = RegistryStatus(row["status"]) if "status" in row.keys() else fallback_status
    return RegistryEntry(
        manifest=manifest,
        status=actual_status,
        published_at=datetime.fromisoformat(row["published_at"]),
        payload_hash=row["payload_hash"],
    )


class Registry:
    """Registry local do ULTRON. Thread-safe e async.

    Uso::

        async with Registry.open() as reg:
            await reg.publish(agent_manifest)
            results = await reg.search(SearchQuery(text="search"))
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def start(self, *, read_only: bool = False) -> None:
        """Inicializa a conexão + schema. Use com close() no fim.

        Para uso dentro do lifespan do FastAPI. Para scripts curtos,
        prefira o context manager ``Registry.open()``.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await self._connect(read_only=read_only)
        await self._ensure_schema()

    @classmethod
    @asynccontextmanager
    async def open(
        cls,
        path: Path | None = None,
        *,
        read_only: bool = False,
    ) -> AsyncIterator[Registry]:
        """Abre o registry. Use como async context manager.

        ``read_only=True`` abre o banco em modo somente-leitura (SQLite URI).
        """
        path = (path or DEFAULT_REGISTRY_PATH).expanduser()
        self = cls(path)
        await self.start(read_only=read_only)
        try:
            yield self
        finally:
            await self.close()

    async def _connect(self, *, read_only: bool) -> None:
        if read_only:
            uri = f"file:{self.path}?mode=ro"
            self._conn = await aiosqlite.connect(uri, uri=True)
        else:
            self._conn = await aiosqlite.connect(self.path)
        assert self._conn is not None
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def _ensure_schema(self) -> None:
        assert self._conn is not None
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()
        # Migration 1: schema inicial (já idempotente)
        applied = await self._conn.execute_fetchall(
            "SELECT version FROM migrations WHERE version = 1"
        )
        if not applied:
            await self._conn.execute(
                "INSERT INTO migrations (version, applied_at, description) VALUES (?, ?, ?)",
                (
                    1,
                    datetime.now(tz=UTC).isoformat(),
                    "Schema inicial: manifests, manifests_fts, migrations, audit",
                ),
            )
            await self._conn.commit()

        # Migration 2: estado persistido do manifesto. A checagem por PRAGMA
        # mantém a migração idempotente tanto em bancos U1 existentes quanto
        # em instalações novas.
        columns = await self._conn.execute_fetchall("PRAGMA table_info(manifests)")
        if "status" not in {str(column[1]) for column in columns}:
            await self._conn.execute(
                "ALTER TABLE manifests ADD COLUMN status TEXT NOT NULL DEFAULT 'published'"
            )
        migration_2 = await self._conn.execute_fetchall(
            "SELECT version FROM migrations WHERE version = 2"
        )
        if not migration_2:
            await self._conn.execute(
                "INSERT INTO migrations (version, applied_at, description) VALUES (?, ?, ?)",
                (
                    2,
                    datetime.now(tz=UTC).isoformat(),
                    "Estado persistido de manifests (published/deprecated/revoked)",
                ),
            )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ---- CRUD ------------------------------------------------------------

    async def publish(
        self,
        manifest: BaseManifest,
        *,
        status: RegistryStatus = RegistryStatus.PUBLISHED,
        actor: str = "system",
        correlation_id: str | None = None,
    ) -> RegistryEntry:
        """Publica um manifest. Falha se já existir (id, version)."""
        assert self._conn is not None
        row = _manifest_to_row(manifest)
        try:
            await self._conn.execute(
                """
                INSERT INTO manifests
                (id, version, kind, publisher, name, description, license, risk,
                 schema_version, payload_json, payload_hash, published_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*row, datetime.now(tz=UTC).isoformat(), status.value),
            )
        except aiosqlite.IntegrityError as e:
            raise VersionConflictError(
                f"Manifest {manifest.id}@{manifest.version} já publicado",
                context={"id": str(manifest.id), "version": manifest.version},
            ) from e

        # Indexação FTS — campos derivados do payload
        await self._conn.execute(
            """
            INSERT INTO manifests_fts
            (rowid, id, version, kind, publisher, name, description, capabilities, tags, license)
            VALUES ((SELECT rowid FROM manifests WHERE id = ? AND version = ?),
                    ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(manifest.id),
                manifest.version,
                str(manifest.id),
                manifest.version,
                manifest.kind,
                manifest.publisher,
                manifest.id.name,
                manifest.description,
                " ".join(manifest.capabilities),
                " ".join(manifest.tags),
                manifest.license,
            ),
        )
        await self._audit(
            actor=actor,
            action="quarantine" if status == RegistryStatus.QUARANTINED else "publish",
            target_id=str(manifest.id),
            target_version=manifest.version,
            payload_hash=row[10],
            correlation_id=correlation_id,
        )
        await self._conn.commit()
        _log.info(
            "manifest.published",
            id=str(manifest.id),
            version=manifest.version,
            kind=manifest.kind,
        )
        return RegistryEntry(
            manifest=manifest,
            status=status,
            published_at=datetime.now(tz=UTC),
            payload_hash=row[10],
        )

    async def get(
        self,
        manifest_id: str | ManifestId,
        version: str | None = None,
    ) -> RegistryEntry:
        """Busca um manifest por id (+ versão opcional).

        Sem versão, devolve a versão publicada mais recentemente.
        """
        assert self._conn is not None
        mid = str(manifest_id)
        if version is not None:
            rows = await self._conn.execute_fetchall(
                "SELECT * FROM manifests WHERE id = ? AND version = ?",
                (mid, version),
            )
        else:
            # Ordenação SemVer completa pertence ao resolver do U2.
            rows = await self._conn.execute_fetchall(
                """
                SELECT * FROM manifests
                WHERE id = ?
                ORDER BY published_at DESC
                LIMIT 1
                """,
                (mid,),
            )
        if not rows:
            raise UltronError(
                f"Manifest {mid} não encontrado",
                context={"id": mid, "version": version},
            )
        row = next(iter(rows))
        # Enriquecer com status quando coluna existir (reservado p/ U3)
        return _row_to_entry(row)

    async def list_all(
        self,
        *,
        kind: str | None = None,
        publisher: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RegistryEntry]:
        """Lista manifests com paginação e filtros simples."""
        assert self._conn is not None
        sql = "SELECT * FROM manifests WHERE 1=1"
        params: list[Any] = []
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if publisher:
            sql += " AND publisher = ?"
            params.append(publisher)
        sql += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = await self._conn.execute_fetchall(sql, params)
        return [_row_to_entry(r) for r in rows]

    async def list_versions(self, manifest_id: str | ManifestId) -> list[RegistryEntry]:
        """Lista todas as versões publicadas de um ID para resolução no U2."""
        assert self._conn is not None
        rows = await self._conn.execute_fetchall(
            "SELECT * FROM manifests WHERE id = ? ORDER BY published_at DESC",
            (str(manifest_id),),
        )
        return [_row_to_entry(row) for row in rows]

    async def search(self, query: SearchQuery) -> list[RegistryEntry]:
        """Busca via FTS5 + filtros estruturados.

        Estratégia:

        1. Filtros puramente estruturados (kind, publisher, license, risk) → SQL direto.
        2. Texto ou capability → SQLite FTS5 para casar ``(id, version)``, depois
           cruzamos com ``manifests`` para aplicar os filtros restantes.
        3. Combinação: juntar e deduplicar.
        """
        assert self._conn is not None
        sql, params = await self._build_search_sql(query)
        rows = await self._conn.execute_fetchall(sql, params)
        return [_row_to_entry(r) for r in rows]

    async def count_search(self, query: SearchQuery) -> int:
        """Conta todos os resultados de uma busca, sem aplicar paginação."""
        assert self._conn is not None
        sql, params = await self._build_search_sql(query, count_only=True)
        rows = list(await self._conn.execute_fetchall(sql, params))
        return int(rows[0][0])

    async def _build_search_sql(
        self, query: SearchQuery, *, count_only: bool = False
    ) -> tuple[str, list[Any]]:
        """Monta a consulta compartilhada por ``search`` e ``count_search``."""
        where: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("kind", query.kind),
            ("publisher", query.publisher),
            ("license", query.license),
            ("risk", query.risk),
            ("status", query.status.value if query.status else None),
        ):
            if value:
                where.append(f"{column} = ?")
                params.append(value)
        if query.runtime:
            where.append("json_extract(payload_json, '$.runtime') = ?")
            params.append(query.runtime)

        fts_pairs: list[tuple[str, str]] | None = None
        if query.text or query.capability:
            try:
                fts_pairs = await self._fts_query(
                    _build_fts_query(query.text or query.capability or ""),
                    column="" if query.text else "capabilities",
                )
            except aiosqlite.Error:
                fts_pairs = []
            if not fts_pairs:
                return (
                    ("SELECT COUNT(*) FROM manifests WHERE 0", [])
                    if count_only
                    else (
                        "SELECT * FROM manifests WHERE 0",
                        [],
                    )
                )
            pair_clauses: list[str] = []
            for manifest_id, version in fts_pairs:
                pair_clauses.append("(id = ? AND version = ?)")
                params.extend([manifest_id, version])
            where.append(f"({' OR '.join(pair_clauses)})")

        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        if count_only:
            return f"SELECT COUNT(*) FROM manifests{where_sql}", params
        params.extend([query.limit, query.offset])
        return (
            f"SELECT * FROM manifests{where_sql} ORDER BY published_at DESC LIMIT ? OFFSET ?",
            params,
        )

    async def set_status(
        self,
        manifest_id: str | ManifestId,
        version: str,
        status: RegistryStatus,
        *,
        actor: str = "system",
        audit_action: str = "status_changed",
        correlation_id: str | None = None,
    ) -> RegistryEntry:
        """Altera somente o estado operacional, preservando o payload imutável."""
        assert self._conn is not None
        mid = str(manifest_id)
        current = await self.get(mid, version)
        await self._conn.execute(
            "UPDATE manifests SET status = ? WHERE id = ? AND version = ?",
            (status.value, mid, version),
        )
        await self._audit(
            actor=actor,
            action=audit_action,
            target_id=mid,
            target_version=version,
            payload_hash=current.payload_hash,
            correlation_id=correlation_id,
        )
        await self._conn.commit()
        return await self.get(mid, version)

    async def _fts_query(self, fts_expr: str, column: str = "") -> list[tuple[str, str]]:
        """Roda MATCH na FTS5 e retorna lista de (id, version)."""
        assert self._conn is not None
        target = f"f.{column}" if column else "manifests_fts"
        sql = (
            "SELECT m.id, m.version FROM manifests m "
            "JOIN manifests_fts f ON f.id = m.id AND f.version = m.version "
            f"WHERE {target} MATCH ?"
        )
        rows = await self._conn.execute_fetchall(sql, (fts_expr,))
        return [(r[0], r[1]) for r in rows]

    async def delete(
        self,
        manifest_id: str | ManifestId,
        version: str,
        *,
        actor: str = "system",
        correlation_id: str | None = None,
    ) -> None:
        """Remove permanentemente um manifest (id, version).

        Use com cuidado — operação destrutiva. Para "marcar como removido"
        use um workflow de status (previsto em U3).
        """
        assert self._conn is not None
        mid = str(manifest_id)
        # Pegar hash + rowid antes de deletar
        rows = list(
            await self._conn.execute_fetchall(
                "SELECT payload_hash, rowid FROM manifests WHERE id = ? AND version = ?",
                (mid, version),
            )
        )
        if not rows:
            raise UltronError(
                f"Manifest {mid}@{version} não encontrado",
                context={"id": mid, "version": version},
            )
        payload_hash: str = rows[0][0]
        rowid: int = rows[0][1]
        await self._conn.execute(
            "DELETE FROM manifests WHERE rowid = ?",
            (rowid,),
        )
        await self._conn.execute(
            "DELETE FROM manifests_fts WHERE rowid = ?",
            (rowid,),
        )
        await self._audit(
            actor=actor,
            action="delete",
            target_id=mid,
            target_version=version,
            payload_hash=payload_hash,
            correlation_id=correlation_id,
        )
        await self._conn.commit()
        _log.warning(
            "manifest.deleted",
            id=mid,
            version=version,
        )

    async def count(
        self,
        *,
        kind: str | None = None,
        publisher: str | None = None,
    ) -> int:
        """Conta manifests com filtros opcionais."""
        assert self._conn is not None
        sql = "SELECT COUNT(*) AS n FROM manifests WHERE 1=1"
        params: list[Any] = []
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if publisher:
            sql += " AND publisher = ?"
            params.append(publisher)
        rows = list(await self._conn.execute_fetchall(sql, params))
        return int(rows[0][0])

    async def stats(self) -> RegistryStats:
        """Estatísticas agregadas para o portal."""
        assert self._conn is not None
        total_rows = list(await self._conn.execute_fetchall("SELECT COUNT(*) FROM manifests"))
        total: int = int(total_rows[0][0])

        by_kind = await _by_kind(self._conn)
        by_publisher = await _by_publisher(self._conn)
        by_risk = await _by_risk(self._conn)

        mig = list(await self._conn.execute_fetchall("SELECT MAX(version) FROM migrations"))
        latest_migration = int(mig[0][0] or 0)

        last_audit_rows = list(
            await self._conn.execute_fetchall("SELECT MAX(occurred_at) FROM audit")
        )
        last_audit_dt = (
            datetime.fromisoformat(last_audit_rows[0][0]) if last_audit_rows[0][0] else None
        )

        return RegistryStats(
            total=int(total),
            by_kind=by_kind,
            by_publisher=by_publisher,
            by_risk=by_risk,
            latest_migration=latest_migration,
            last_audit_event=last_audit_dt,
        )

    # ---- Audit -----------------------------------------------------------

    async def _audit(
        self,
        *,
        actor: str,
        action: str,
        target_id: str | None,
        target_version: str | None,
        payload_hash: str | None,
        correlation_id: str | None,
    ) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT INTO audit
            (occurred_at, actor, action, target_id, target_version, payload_hash, correlation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(tz=UTC).isoformat(),
                actor,
                action,
                target_id,
                target_version,
                payload_hash,
                correlation_id,
            ),
        )

    async def recent_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        """Últimos eventos de auditoria (para o portal)."""
        assert self._conn is not None
        rows = await self._conn.execute_fetchall(
            """
            SELECT occurred_at, actor, action, target_id, target_version,
                   payload_hash, correlation_id
            FROM audit ORDER BY event_id DESC LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in rows]


# ---- Helpers de FTS --------------------------------------------------------


def _build_fts_query(text: str) -> str:
    """Constrói uma query FTS5 a partir de texto livre.

    Cada palavra recebe um sufixo ``*`` (prefix match) para search-as-you-type.
    Caracteres especiais FTS5 (``.``, ``:``, etc) são removidos.
    """
    sanitized = _WS_SPLIT_RE.sub(" ", text)
    tokens = [t for t in sanitized.split() if t]
    if not tokens:
        return '""'
    return " ".join(f"{t}*" for t in tokens)


_WS_SPLIT_RE = re.compile(r"[^\w\s\-_]")


# ---- Funções auxiliares async (precisam de conexão) ----------------------


async def _by_kind(conn: aiosqlite.Connection) -> dict[str, int]:
    rows = await conn.execute_fetchall("SELECT kind, COUNT(*) AS n FROM manifests GROUP BY kind")
    return {str(r[0]): int(r[1]) for r in rows}


async def _by_publisher(conn: aiosqlite.Connection) -> dict[str, int]:
    rows = await conn.execute_fetchall(
        "SELECT publisher, COUNT(*) AS n FROM manifests GROUP BY publisher"
    )
    return {str(r[0]): int(r[1]) for r in rows}


async def _by_risk(conn: aiosqlite.Connection) -> dict[str, int]:
    rows = await conn.execute_fetchall("SELECT risk, COUNT(*) AS n FROM manifests GROUP BY risk")
    return {str(r[0]): int(r[1]) for r in rows}


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "InvalidManifestError",  # re-export pra conveniência
    "Registry",
    "RegistryEntry",
    "RegistryStats",
    "RegistryStatus",
    "SearchQuery",
]
