"""Identidade Ed25519 de publishers e trust store local persistido."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ultron.core.base import BaseManifest


@dataclass(frozen=True, slots=True)
class TrustedPublisherKey:
    publisher: str
    key_id: str
    public_key: str
    revoked: bool = False


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    publisher: str
    key_id: str
    artifact_sha256: str
    signature: str
    algorithm: str = "ed25519"


def generate_signing_key() -> Ed25519PrivateKey:
    """Gera uma chave em memória; o ULTRON nunca persiste a chave privada."""
    return Ed25519PrivateKey.generate()


def sign_artifact(
    private_key: Ed25519PrivateKey,
    manifest: BaseManifest,
    artifact: bytes,
) -> SignatureEnvelope:
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = hashlib.sha256(public).hexdigest()[:16]
    artifact_sha256 = hashlib.sha256(artifact).hexdigest()
    signature = private_key.sign(_signed_payload(manifest, artifact_sha256))
    return SignatureEnvelope(
        publisher=manifest.publisher,
        key_id=key_id,
        artifact_sha256=artifact_sha256,
        signature=base64.b64encode(signature).decode("ascii"),
    )


class PublisherTrustStore:
    """Chaves públicas imutáveis com revogação explícita e escrita atômica."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def register(self, publisher: str, public_key: Ed25519PublicKey) -> TrustedPublisherKey:
        raw = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        key = TrustedPublisherKey(
            publisher=publisher,
            key_id=hashlib.sha256(raw).hexdigest()[:16],
            public_key=base64.b64encode(raw).decode("ascii"),
        )
        keys = self._read()
        existing = next((item for item in keys if item.key_id == key.key_id), None)
        if existing is not None:
            if existing.publisher != publisher:
                raise ValueError("Chave já pertence a outro publisher")
            return existing
        self._write((*keys, key))
        return key

    def revoke(self, publisher: str, key_id: str) -> TrustedPublisherKey:
        keys = self._read()
        target = next(
            (item for item in keys if item.publisher == publisher and item.key_id == key_id),
            None,
        )
        if target is None:
            raise KeyError(key_id)
        revoked = replace(target, revoked=True)
        self._write(tuple(revoked if item == target else item for item in keys))
        return revoked

    def verify(
        self,
        manifest: BaseManifest,
        artifact: bytes,
        envelope: SignatureEnvelope,
    ) -> bool:
        if envelope.algorithm != "ed25519" or envelope.publisher != manifest.publisher:
            return False
        artifact_sha256 = hashlib.sha256(artifact).hexdigest()
        if envelope.artifact_sha256 != artifact_sha256:
            return False
        key = next(
            (
                item
                for item in self._read()
                if item.publisher == envelope.publisher and item.key_id == envelope.key_id
            ),
            None,
        )
        if key is None or key.revoked:
            return False
        try:
            public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key.public_key))
            public.verify(
                base64.b64decode(envelope.signature),
                _signed_payload(manifest, artifact_sha256),
            )
        except (InvalidSignature, ValueError):
            return False
        return True

    def _read(self) -> tuple[TrustedPublisherKey, ...]:
        if not self.path.is_file():
            return ()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return tuple(TrustedPublisherKey(**item) for item in payload["keys"])

    def _write(self, keys: tuple[TrustedPublisherKey, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"version": "1.0.0", "keys": [asdict(key) for key in keys]},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        fd, temporary_name = tempfile.mkstemp(prefix=".ultron-trust-", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(f"{payload}\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


def _signed_payload(manifest: BaseManifest, artifact_sha256: str) -> bytes:
    manifest_payload = json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"ultron-signature-v1\n{artifact_sha256}\n{manifest_payload}\n".encode()


__all__ = [
    "PublisherTrustStore",
    "SignatureEnvelope",
    "TrustedPublisherKey",
    "generate_signing_key",
    "sign_artifact",
]
