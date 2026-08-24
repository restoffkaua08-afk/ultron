"""Policy — deny-by-default, allowlist explícita."""

from __future__ import annotations

from dataclasses import dataclass, field

from ultron.core.base import VALID_PERMISSIONS, Permission
from ultron.core.errors import PermissionDeniedError, PolicyViolationError


@dataclass(frozen=True, slots=True)
class Policy:
    """Política de um consumer: o que está *concedido* e o que está *negado*.

    Invariante: a interseção entre ``denied`` e ``granted`` deve ser vazia
    (verificada no ``__post_init__``).
    """

    granted: frozenset[str] = field(default_factory=frozenset)
    denied: frozenset[str] = field(default_factory=frozenset)
    require_approval_for: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        invalid_grant = self.granted - VALID_PERMISSIONS
        if invalid_grant:
            raise PolicyViolationError(
                f"granted contém permissões inválidas: {sorted(invalid_grant)}",
                context={"granted": sorted(self.granted)},
            )
        invalid_deny = self.denied - VALID_PERMISSIONS
        if invalid_deny:
            raise PolicyViolationError(
                f"denied contém permissões inválidas: {sorted(invalid_deny)}",
                context={"denied": sorted(self.denied)},
            )
        overlap = self.granted & self.denied
        if overlap:
            raise PolicyViolationError(
                f"granted e denied se sobrepõem: {sorted(overlap)}",
                context={"overlap": sorted(overlap)},
            )

    def allows(self, permission: str) -> bool:
        if permission in self.denied:
            return False
        return permission in self.granted

    def needs_approval(self, permission: str) -> bool:
        return permission in self.require_approval_for


# ---- API de checagem -------------------------------------------------------


def check_manifest_permissions(
    requested: tuple[Permission, ...],
    policy: Policy,
) -> None:
    """Garante que toda permissão solicitada está dentro da policy.

    Lança ``PermissionDeniedError`` se o consumer não concede.
    """
    for perm in requested:
        if not policy.allows(perm.capability):
            raise PermissionDeniedError(
                f"Consumer não concede permissão {perm.capability!r}",
                context={
                    "permission": perm.capability,
                    "scope": perm.scope,
                    "granted": sorted(policy.granted),
                },
            )


def default_deny_policy() -> Policy:
    """Policy mais restritiva: nada é concedido.

    Use como base ao criar policies específicas.
    """
    return Policy(granted=frozenset(), denied=frozenset(VALID_PERMISSIONS))


def conservative_policy() -> Policy:
    """Policy segura: somente leituras e operações claramente reversíveis.

    Adequada para bootstrap e para agents/skills que ainda não foram
    auditados.
    """
    return Policy(
        granted=frozenset(
            {
                "network.readonly",
                "fs.read",
                "system.time",
                "system.env.read",
                "memory.read",
            }
        ),
        denied=frozenset(VALID_PERMISSIONS)
        - frozenset(
            {
                "network.readonly",
                "fs.read",
                "system.time",
                "system.env.read",
                "memory.read",
            }
        ),
        require_approval_for=frozenset({"memory.write", "publish.external"}),
    )
