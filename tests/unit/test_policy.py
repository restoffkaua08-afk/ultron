"""Testes do módulo de policy."""

from __future__ import annotations

import pytest

from ultron.core.base import Permission
from ultron.core.errors import PermissionDeniedError, PolicyViolationError
from ultron.policy import (
    Policy,
    check_manifest_permissions,
    conservative_policy,
    default_deny_policy,
)


class TestPolicyBasics:
    def test_default_deny_nao_concede_nada(self) -> None:
        p = default_deny_policy()
        assert p.allows("network.readonly") is False
        assert p.allows("anything") is False

    def test_conservative_concede_leituras(self) -> None:
        p = conservative_policy()
        assert p.allows("network.readonly") is True
        assert p.allows("fs.read") is True
        assert p.allows("fs.write") is False
        assert p.allows("publish.external") is False

    def test_intersecao_granted_denied_rejeitada(self) -> None:
        with pytest.raises(PolicyViolationError):
            Policy(
                granted=frozenset({"network.readonly"}),
                denied=frozenset({"network.readonly"}),
            )

    def test_permissao_invalida_em_granted(self) -> None:
        with pytest.raises(PolicyViolationError):
            Policy(granted=frozenset({"magic.power"}))

    def test_permissao_invalida_em_denied(self) -> None:
        with pytest.raises(PolicyViolationError):
            Policy(denied=frozenset({"magic.power"}))


class TestCheckManifest:
    def test_tudo_dentro_da_policy(self) -> None:
        p = conservative_policy()
        perms = (
            Permission(capability="network.readonly"),
            Permission(capability="fs.read"),
        )
        check_manifest_permissions(perms, p)  # não deve lançar

    def test_permissao_nao_concedida(self) -> None:
        p = default_deny_policy()
        perms = (Permission(capability="fs.write"),)
        with pytest.raises(PermissionDeniedError):
            check_manifest_permissions(perms, p)
