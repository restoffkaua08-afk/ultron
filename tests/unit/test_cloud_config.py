"""Configuração cloud é verificável sem revelar credenciais."""

from ultron.cloud import cloud_readiness


def test_empty_environment_is_local_and_not_ready() -> None:
    readiness = cloud_readiness({})

    assert readiness.mode == "local"
    assert readiness.ready is False
    assert readiness.supabase is False


def test_complete_environment_is_ready() -> None:
    values = {
        "ULTRON_MODE": "cloud",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "publishable",
        "SUPABASE_SECRET_KEY": "secret",
        "GITHUB_APP_ID": "1",
        "GITHUB_APP_CLIENT_ID": "client",
        "GITHUB_APP_CLIENT_SECRET": "client-secret",
        "GITHUB_APP_PRIVATE_KEY": "private-key",
        "GITHUB_APP_WEBHOOK_SECRET": "webhook",
        "ULTRON_MCP_RESOURCE_URL": "https://ultron.example/mcp",
        "ULTRON_OAUTH_ISSUER": "https://auth.example",
        "ULTRON_OAUTH_AUDIENCE": "https://ultron.example/mcp",
    }

    assert cloud_readiness(values).ready is True


def test_whitespace_is_not_configuration() -> None:
    assert cloud_readiness({"SUPABASE_URL": "   "}).supabase is False
