"""Testes de ManifestId e UltronVersion."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ultron.core.ids import ManifestId, UltronVersion


class TestManifestId:
    def test_construir_e_serializar(self) -> None:
        mid = ManifestId("acme", "research-agent")
        assert str(mid) == "acme/research-agent"
        assert mid.publisher == "acme"
        assert mid.name == "research-agent"

    def test_parse_roundtrip(self) -> None:
        mid = ManifestId.parse("restoff/cool-pack")
        assert mid.publisher == "restoff"
        assert mid.name == "cool-pack"
        assert str(mid) == "restoff/cool-pack"

    def test_hash_e_igualdade(self) -> None:
        a = ManifestId("acme", "x")
        b = ManifestId("acme", "x")
        c = ManifestId("acme", "y")
        assert a == b
        assert a != c
        assert {a, b, c} == {a, c}

    @pytest.mark.parametrize(
        "raw",
        ["sem-slash", "/", "acme/", "ACME/x", "acme/X", "a" * 64 + "/b"],
    )
    def test_parse_invalido(self, raw: str) -> None:
        with pytest.raises(ValueError):
            ManifestId.parse(raw)

    @pytest.mark.parametrize(
        "publisher",
        ["", "ACME", "-acme", "acme!", "a" * 64, "acme/bad"],
    )
    def test_publisher_invalido(self, publisher: str) -> None:
        with pytest.raises(ValueError):
            ManifestId(publisher, "name")

    def test_imutavel(self) -> None:
        mid = ManifestId("acme", "x")
        with pytest.raises(AttributeError):
            mid.publisher = "outro"  # type: ignore[misc]


class TestUltronVersion:
    adapter = TypeAdapter(UltronVersion)

    @pytest.mark.parametrize(
        "v",
        ["0.0.0", "1.0.0", "10.20.30", "1.0.0-rc.1", "2.3.1-beta.1+build.42"],
    )
    def test_semver_validas(self, v: str) -> None:
        assert self.adapter.validate_python(v) == v

    @pytest.mark.parametrize(
        "v",
        ["1.0", "1", "v1.0.0", "1.0.0.0", "01.0.0", "1.0.0-", "latest"],
    )
    def test_semver_invalidas(self, v: str) -> None:
        with pytest.raises(ValidationError):
            self.adapter.validate_python(v)
