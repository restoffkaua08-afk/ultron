"""Configuração do modo cloud, sem conexão implícita a serviços externos."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CloudReadiness:
    """Presença de configuração; nunca inclui os valores dos secrets."""

    mode: str
    supabase: bool
    github_auth: bool
    github_app: bool
    mcp_oauth: bool

    @property
    def ready(self) -> bool:
        return all((self.supabase, self.github_auth, self.github_app, self.mcp_oauth))


def cloud_readiness(environ: dict[str, str] | None = None) -> CloudReadiness:
    values = os.environ if environ is None else environ

    def present(*keys: str) -> bool:
        return all(bool(values.get(key, "").strip()) for key in keys)

    return CloudReadiness(
        mode=values.get("ULTRON_MODE", "local"),
        supabase=present("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY"),
        github_auth=present("GITHUB_APP_CLIENT_ID", "GITHUB_APP_CLIENT_SECRET"),
        github_app=present("GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY", "GITHUB_APP_WEBHOOK_SECRET"),
        mcp_oauth=present(
            "ULTRON_MCP_RESOURCE_URL", "ULTRON_OAUTH_ISSUER", "ULTRON_OAUTH_AUDIENCE"
        ),
    )


__all__ = ["CloudReadiness", "cloud_readiness"]
