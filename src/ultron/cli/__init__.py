"""CLI do ULTRON — entry point ``ultron``.

No U0 só temos o esqueleto e dois comandos de inspeção. Comandos de
CRUD do registry entram no U1.
"""

from __future__ import annotations

import typer

from ultron import __version__

app = typer.Typer(
    name="ultron",
    help="ULTRON — plataforma independente de capacidades versionadas.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def version() -> None:
    """Mostra a versão do ULTRON."""
    typer.echo(f"ultron {__version__}")


@app.command()
def hello(name: str = "world") -> None:
    """Comando de smoke-test do CLI."""
    typer.echo(f"Hello, {name}! ULTRON está pronto.")
