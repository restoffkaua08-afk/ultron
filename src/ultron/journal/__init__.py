"""Journal imutável de lockfiles para rollback explícito."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from ultron.core.errors import CheckpointNotFoundError, IntegrityError
from ultron.lockfile import UltronLockfile


class LockfileJournal:
    """Armazena cada lockfile uma vez, endereçado pelo próprio SHA-256."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def checkpoint(self, lockfile: UltronLockfile) -> str:
        content = lockfile.canonical_bytes()
        digest = hashlib.sha256(content).hexdigest()
        target = self._path(digest)
        if target.exists():
            return digest
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".ultron-checkpoint-", dir=self.root)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            target.chmod(0o444)
        finally:
            temporary.unlink(missing_ok=True)
        return digest

    def get(self, digest: str) -> UltronLockfile:
        path = self._path(digest)
        if not path.is_file():
            raise CheckpointNotFoundError(
                f"Checkpoint não encontrado: {digest}", context={"digest": digest}
            )
        content = path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if actual != digest:
            raise IntegrityError(
                "Checkpoint falhou na verificação de integridade",
                context={"expected": digest, "actual": actual},
            )
        return UltronLockfile.from_bytes(content)

    def list(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        return tuple(sorted(path.name for path in self.root.iterdir() if path.is_file()))

    def _path(self, digest: str) -> Path:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Digest SHA-256 inválido")
        return self.root / digest


__all__ = ["LockfileJournal"]
