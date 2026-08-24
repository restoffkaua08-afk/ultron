"""Testes do lockfile canônico e atômico."""

from pathlib import Path

from ultron.lockfile import LockedCapability, LockfileStore, UltronLockfile


def lockfile() -> UltronLockfile:
    return UltronLockfile(
        root="acme/root@1.0.0",
        capabilities=(
            LockedCapability(
                id="acme/root",
                version="1.0.0",
                kind="skill",
                digest="a" * 64,
                dependencies=("acme/search@1.2.0",),
            ),
        ),
    )


def test_canonical_bytes_are_reproducible() -> None:
    first = lockfile().canonical_bytes()
    second = UltronLockfile.from_bytes(first).canonical_bytes()

    assert first == second
    assert first.endswith(b"\n")


def test_store_round_trip_and_atomic_replacement(tmp_path: Path) -> None:
    store = LockfileStore(tmp_path / "state" / "ultron.lock")
    assert store.read() is None

    store.write(lockfile())

    assert store.read() == lockfile()
    assert not list(store.path.parent.glob(".ultron-lock-*"))
