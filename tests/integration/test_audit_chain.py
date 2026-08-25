"""Audit chain detecta alteração e truncamento do log."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultron.core.base import IntegrityInfo, Provenance, RiskLevel
from ultron.core.ids import ManifestId
from ultron.core.manifests import SkillManifest
from ultron.registry import Registry

pytestmark = pytest.mark.integration


def manifest(name: str) -> SkillManifest:
    return SkillManifest(
        id=ManifestId("acme", name),
        version="1.0.0",
        publisher="acme",
        description=name,
        risks=RiskLevel.SAFE,
        skill_type="prompt",
        provenance=Provenance(source="local"),
        integrity=IntegrityInfo(digest=hashlib.sha256(name.encode()).hexdigest()),
    )


@pytest.mark.asyncio
async def test_chain_is_valid_and_exposes_link_hashes(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.db")
    await registry.start()
    try:
        await registry.publish(manifest("one"), actor="alice", correlation_id="audit-1")
        await registry.publish(manifest("two"), actor="bob", correlation_id="audit-2")

        verification = await registry.verify_audit_chain()
        events = list(reversed(await registry.recent_audit()))

        assert verification.valid and verification.event_count == 2
        assert events[0]["previous_hash"] is None
        assert events[1]["previous_hash"] == events[0]["event_hash"]
    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_chain_detects_event_edit_and_tail_deletion(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.db")
    await registry.start()
    try:
        await registry.publish(manifest("one"))
        await registry.publish(manifest("two"))
        assert registry._conn is not None
        await registry._conn.execute("UPDATE audit SET actor = 'tampered' WHERE event_id = 1")
        await registry._conn.commit()
        edited = await registry.verify_audit_chain()
        assert not edited.valid and edited.broken_event_id == 1

        await registry._conn.execute("UPDATE audit SET actor = 'system' WHERE event_id = 1")
        await registry._backfill_audit_chain()
        await registry._conn.commit()
        assert (await registry.verify_audit_chain()).valid
        await registry._conn.execute("DELETE FROM audit WHERE event_id = 2")
        await registry._conn.commit()
        truncated = await registry.verify_audit_chain()
        assert not truncated.valid and truncated.broken_event_id == 0
    finally:
        await registry.close()
