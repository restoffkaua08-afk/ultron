"""Teste de smoke do CLI via Typer CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from ultron.cli import app


class TestCli:
    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout

    def test_hello(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["hello", "--name", "Kauã"])
        assert result.exit_code == 0
        assert "Kauã" in result.stdout
