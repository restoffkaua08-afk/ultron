from __future__ import annotations

from dataclasses import replace

import pytest

from ultron.core.base import Permission
from ultron.core.errors import PermissionDeniedError, PolicyViolationError
from ultron.policy import Policy, default_deny_policy
from ultron.sandbox import SandboxExecutor, SandboxRequest, SandboxResult

IMAGE = "registry.example/agent@sha256:" + "a" * 64


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[SandboxRequest, bool]] = []

    def run(self, request: SandboxRequest, *, network_enabled: bool) -> SandboxResult:
        self.calls.append((request, network_enabled))
        return SandboxResult(exit_code=0, stdout=b"x" * 20, stderr=b"")


def test_default_deny_never_reaches_backend() -> None:
    backend = RecordingBackend()
    request = SandboxRequest("acme/agent", IMAGE, ("python", "-m", "agent"))

    with pytest.raises(PermissionDeniedError):
        SandboxExecutor(backend).execute(request, default_deny_policy())

    assert backend.calls == []


def test_execution_is_delegated_with_network_disabled_and_bounded_output() -> None:
    backend = RecordingBackend()
    request = SandboxRequest("acme/agent", IMAGE, ("agent",))
    request = replace(request, limits=replace(request.limits, output_bytes=8))
    policy = Policy(granted=frozenset({"process.spawn"}))

    result = SandboxExecutor(backend).execute(request, policy)

    assert backend.calls == [(request, False)]
    assert result.stdout == b"x" * 8


def test_declared_network_requires_policy_and_enables_backend_network() -> None:
    backend = RecordingBackend()
    request = SandboxRequest(
        "acme/agent",
        IMAGE,
        ("agent",),
        permissions=(Permission(capability="network.readonly"),),
    )
    policy = Policy(granted=frozenset({"process.spawn", "network.readonly"}))

    SandboxExecutor(backend).execute(request, policy)

    assert backend.calls[0][1] is True


def test_unpinned_image_and_invalid_limits_are_rejected() -> None:
    with pytest.raises(PolicyViolationError):
        SandboxRequest("acme/agent", "registry.example/agent:latest", ("agent",))
    request = SandboxRequest("acme/agent", IMAGE, ("agent",))
    with pytest.raises(PolicyViolationError):
        replace(request.limits, timeout_seconds=0)


def test_approval_required_fails_closed() -> None:
    backend = RecordingBackend()
    policy = Policy(
        granted=frozenset({"process.spawn"}),
        require_approval_for=frozenset({"process.spawn"}),
    )
    with pytest.raises(PermissionDeniedError, match="aprovação"):
        SandboxExecutor(backend).execute(SandboxRequest("acme/agent", IMAGE, ("agent",)), policy)
    assert backend.calls == []
