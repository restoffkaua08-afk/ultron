"""Testes do package store imutável do U2."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultron.core.base import IntegrityInfo
from ultron.core.errors import ArtifactNotFoundError, IntegrityError
from ultron.store import PackageStore


def test_put_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    store = PackageStore(tmp_path / "store")
    content = b"ultron-package-v1"

    first = store.put(content)
    second = store.put(content)

    assert first == second
    assert first.digest == hashlib.sha256(content).hexdigest()
    assert store.get(first.digest) == content
    assert store.contains(first.digest)
    assert store.path_for(first.digest).stat().st_mode & 0o222 == 0


def test_put_rejects_integrity_mismatch(tmp_path: Path) -> None:
    store = PackageStore(tmp_path / "store")
    expected = IntegrityInfo(digest="0" * 64)

    with pytest.raises(IntegrityError):
        store.put(b"different", expected)


def test_get_revalidates_stored_content(tmp_path: Path) -> None:
    store = PackageStore(tmp_path / "store")
    integrity = store.put(b"original")
    path = store.path_for(integrity.digest)
    path.chmod(0o644)
    path.write_bytes(b"tampered")

    with pytest.raises(IntegrityError):
        store.get(integrity.digest)


def test_missing_and_invalid_digest_are_explicit(tmp_path: Path) -> None:
    store = PackageStore(tmp_path / "store")

    with pytest.raises(ArtifactNotFoundError):
        store.get("a" * 64)
    with pytest.raises(ValueError):
        store.path_for("../escape")
