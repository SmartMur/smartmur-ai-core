"""Click command for launching the web dashboard."""

from __future__ import annotations

import click


@click.command("dashboard")
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8200, type=int, help="Port number")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def dashboard_cmd(host: str, port: int, reload: bool):
    """Launch the Claw web dashboard."""
    import uvicorn

    click.echo(f"Starting Claw Dashboard at http://{host}:{port}")
    uvicorn.run(
        "dashboard.app:app",
        host=host,
        port=port,
        reload=reload,
    )
