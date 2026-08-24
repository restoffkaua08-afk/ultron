"""Lockfile canônico e determinístico do ULTRON."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class LockedCapability(BaseModel):
    """Capability fixada em uma versão e um artefato exatos."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str
    kind: str
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependencies: tuple[str, ...] = ()


class UltronLockfile(BaseModel):
    """Estado reproduzível de uma instalação ULTRON."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lock_version: str = "1.0.0"
    root: str
    capabilities: tuple[LockedCapability, ...]

    def canonical_bytes(self) -> bytes:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return f"{encoded}\n".encode()

    @classmethod
    def from_bytes(cls, content: bytes) -> UltronLockfile:
        return cls.model_validate_json(content)


class LockfileStore:
    """Leitura e substituição atômica de um lockfile."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> UltronLockfile | None:
        if not self.path.is_file():
            return None
        return UltronLockfile.from_bytes(self.path.read_bytes())

    def write(self, lockfile: UltronLockfile) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".ultron-lock-", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(lockfile.canonical_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


__all__ = ["LockedCapability", "LockfileStore", "UltronLockfile"]
