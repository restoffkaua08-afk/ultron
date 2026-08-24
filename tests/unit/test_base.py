"""Testes de tipos base e invariantes anti-gate."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ultron.core.base import (
    VALID_PERMISSIONS,
    IntegrityInfo,
    Permission,
    Provenance,
)
from ultron.core.errors import UltronError
from ultron.core.ids import ManifestId


class TestProvenance:
    def test_default_source_local(self) -> None:
        p = Provenance(source="local")
        assert p.source == "local"
        assert p.built_at is not None

    def test_source_git_exige_repo(self) -> None:
        with pytest.raises(ValidationError):
            Provenance(source="git")  # repository é None

    def test_imutavel(self) -> None:
        p = Provenance(source="local")
        with pytest.raises(ValidationError):
            p.source = "git"  # type: ignore[misc]


class TestIntegrityInfo:
    def test_sha256_valido(self) -> None:
        digest = "a" * 64
        info = IntegrityInfo(digest=digest)
        assert info.algorithm == "sha256"
        assert info.digest == digest

    @pytest.mark.parametrize(
        "digest",
        ["short", "g" * 64, "A" * 64, ""],
    )
    def test_sha256_invalido(self, digest: str) -> None:
        with pytest.raises(ValidationError):
            IntegrityInfo(digest=digest)


class TestPermission:
    def test_cria_valida(self) -> None:
        p = Permission(capability="network.readonly", scope="user:1")
        assert p.capability == "network.readonly"
        assert p.scope == "user:1"

    def test_allowlist_esta_fechada(self) -> None:
        # Garante que a lista cobre exatamente o que esperamos no U0.
        # Se alguém adicionar uma nova, é decisão consciente.
        assert "approve-all" not in VALID_PERMISSIONS
        assert "*" not in VALID_PERMISSIONS

    def test_permissao_desconhecida_rejeitada(self) -> None:
        with pytest.raises(ValidationError):
            Permission(capability="root.all")

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            Permission(capability="network.readonly", evil=True)  # type: ignore[call-arg]


class TestErrorToDict:
    def test_serializavel(self) -> None:
        e = UltronError("oi", context={"x": 1})
        d = e.to_dict()
        assert d["code"] == "ULTRON_ERROR"
        assert d["message"] == "oi"
        assert d["context"] == {"x": 1}


class TestManifestId:
    def test_round_trip(self) -> None:
        mid = ManifestId("acme", "x")
        assert ManifestId.parse(str(mid)) == mid
