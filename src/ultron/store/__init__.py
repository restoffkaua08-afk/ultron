"""Package store local, imutável e endereçado por conteúdo."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from ultron.core.base import IntegrityInfo
from ultron.core.errors import ArtifactNotFoundError, IntegrityError


class PackageStore:
    """Persiste bytes em ``<root>/<prefixo>/<sha256>`` sem executá-los."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser()

    def put(self, content: bytes, expected: IntegrityInfo | None = None) -> IntegrityInfo:
        digest = hashlib.sha256(content).hexdigest()
        if expected is not None and expected.digest != digest:
            raise IntegrityError(
                "SHA-256 do artefato não corresponde ao manifesto",
                context={"expected": expected.digest, "actual": digest},
            )
        target = self.path_for(digest)
        if target.exists():
            return IntegrityInfo(digest=digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".ultron-", dir=target.parent)
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
        return IntegrityInfo(digest=digest)

    def get(self, digest: str) -> bytes:
        path = self.path_for(digest)
        if not path.is_file():
            raise ArtifactNotFoundError(
                f"Artefato {digest} não encontrado", context={"digest": digest}
            )
        content = path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if actual != digest:
            raise IntegrityError(
                "Artefato armazenado falhou na verificação de integridade",
                context={"expected": digest, "actual": actual},
            )
        return content

    def contains(self, digest: str) -> bool:
        return self.path_for(digest).is_file()

    def path_for(self, digest: str) -> Path:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Digest SHA-256 inválido")
        return self.root / digest[:2] / digest


__all__ = ["PackageStore"]
