"""Click subcommands for setup wizard and Telegram configuration."""

from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.group("setup")
def setup_group():
    """First-run setup and configuration wizard."""


@setup_group.command("run")
@click.option("--non-interactive", is_flag=True, help="Skip prompts, use defaults.")
def setup_run(non_interactive: bool):
    """Run the full setup wizard."""
    from superpowers.setup_wizard import SetupWizard

    wizard = SetupWizard(non_interactive=non_interactive)
    wizard.run()


@setup_group.command("check")
def setup_check():
    """Check prerequisites (Python, Docker, Redis, age)."""
    from superpowers.setup_wizard import SetupWizard

    wizard = SetupWizard()
    results = wizard.check_prereqs()
    wizard.print_prereqs(results)

    all_ok = all(results.values())
    if all_ok:
        console.print("\n[green]All prerequisites satisfied.[/green]")
    else:
        missing = [k for k, v in results.items() if not v]
        console.print(f"\n[yellow]Missing:[/yellow] {', '.join(missing)}")


@setup_group.command("env")
@click.option("--non-interactive", is_flag=True, help="Use default values.")
def setup_env(non_interactive: bool):
    """Create .env file from .env.example."""
    from superpowers.setup_wizard import SetupWizard

    wizard = SetupWizard(non_interactive=non_interactive)
    try:
        path = wizard.create_env()
        console.print(f"[green]Created:[/green] {path}")
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)


@setup_group.command("vault")
def setup_vault():
    """Initialize the encrypted vault."""
    from superpowers.setup_wizard import SetupWizard

    wizard = SetupWizard()
    ok = wizard.init_vault()
    if ok:
        console.print("[green]Vault initialized.[/green]")
    else:
        console.print("[yellow]Vault initialization skipped (age-keygen not found).[/yellow]")


@setup_group.command("telegram")
@click.option("--token", default=None, help="Telegram Bot API token.")
@click.option("--webhook-url", default=None, help="Webhook URL for the bot.")
@click.option("--chat-ids", default=None, help="Comma-separated allowed chat IDs.")
def setup_telegram(token: str | None, webhook_url: str | None, chat_ids: str | None):
    """Configure Telegram bot integration."""
    from superpowers.setup_wizard import SetupWizard

    wizard = SetupWizard()
    wizard.print_telegram_instructions()

    result = wizard.setup_telegram(
        bot_token=token,
        webhook_url=webhook_url,
        allowed_chat_ids=chat_ids,
    )

    if result["valid"]:
        bot = result["bot_info"]
        console.print(f"[green]Bot validated:[/green] @{bot.get('username', '?')}")
        if result["webhook_set"]:
            console.print("[green]Webhook configured.[/green]")
    else:
        console.print("[yellow]Bot token not provided or invalid.[/yellow]")

    if result["config"].get("ALLOWED_CHAT_IDS"):
        console.print(
            f"  Allowed chats: [cyan]{result['config']['ALLOWED_CHAT_IDS']}[/cyan]"
        )
