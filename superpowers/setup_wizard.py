"""Setup wizard for claude-superpowers first-run and upgrades.

Handles prerequisite checking, .env creation, vault initialization,
and Telegram bot setup. Supports both interactive and non-interactive modes.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from superpowers.config import Settings, get_data_dir

console = Console()

# Minimum Python version required
MIN_PYTHON = (3, 12)

# Prerequisites and the shell commands to check them
PREREQS: dict[str, list[str]] = {
    "python": [sys.executable, "--version"],
    "docker": ["docker", "--version"],
    "docker-compose": ["docker", "compose", "version"],
    "redis-cli": ["redis-cli", "--version"],
    "age": ["age", "--version"],
    "age-keygen": ["age-keygen", "--version"],
}


class SetupWizard:
    """Orchestrates first-run setup and configuration."""

    def __init__(
        self,
        project_dir: Path | None = None,
        data_dir: Path | None = None,
        non_interactive: bool = False,
        values: dict[str, str] | None = None,
    ):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.data_dir = Path(data_dir) if data_dir else get_data_dir()
        self.non_interactive = non_interactive
        self.values = values or {}

    # ------------------------------------------------------------------
    # E1: Prerequisite checking
    # ------------------------------------------------------------------

    def check_prereqs(self) -> dict[str, bool]:
        """Check whether required tools are available.

        Returns a dict mapping tool name to availability (True/False).
        Python version is also validated (must be >= MIN_PYTHON).
        """
        results: dict[str, bool] = {}

        for name, cmd in PREREQS.items():
            results[name] = self._check_command(cmd)

        # Extra: verify Python version meets minimum
        if sys.version_info[:2] < MIN_PYTHON:
            results["python"] = False

        return results

    @staticmethod
    def _check_command(cmd: list[str]) -> bool:
        """Run a command and return True if it exits successfully."""
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def print_prereqs(self, results: dict[str, bool] | None = None) -> None:
        """Pretty-print prerequisite check results."""
        if results is None:
            results = self.check_prereqs()

        table = Table(title="Prerequisite Check", show_lines=False)
        table.add_column("Tool", style="cyan")
        table.add_column("Status")
        table.add_column("Required")

        required = {"python", "docker", "docker-compose"}

        for name, ok in results.items():
            status = "[green]found[/green]" if ok else "[red]missing[/red]"
            req = "[bold]yes[/bold]" if name in required else "optional"
            table.add_row(name, status, req)

        console.print(table)

    # ------------------------------------------------------------------
    # E1: .env creation
    # ------------------------------------------------------------------

    def create_env(self, target: Path | None = None) -> Path:
        """Create a .env file from .env.example, filling in values.

        In non-interactive mode, uses ``self.values`` dict.
        In interactive mode, prompts for each variable with defaults.
        Returns the path to the created .env file.
        """
        target = target or (self.project_dir / ".env")
        example = self.project_dir / ".env.example"

        if not example.exists():
            raise FileNotFoundError(f".env.example not found at {example}")

        lines = example.read_text().splitlines()
        output_lines: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Preserve comments and blank lines
            if not stripped or stripped.startswith("#"):
                output_lines.append(line)
                continue

            # Parse KEY=VALUE
            if "=" not in stripped:
                output_lines.append(line)
                continue

            key, _, default = stripped.partition("=")
            key = key.strip()
            default = default.strip().strip("\"'")

            # Check if a value was provided via dict
            if key in self.values:
                value = self.values[key]
            elif self.non_interactive:
                value = default
            else:
                value = self._prompt_value(key, default)

            output_lines.append(f"{key}={value}")

        target.write_text("\n".join(output_lines) + "\n")
        target.chmod(0o600)
        return target

    @staticmethod
    def _prompt_value(key: str, default: str) -> str:
        """Prompt user for a config value with a default."""
        display_default = default if default else "(empty)"
        try:
            answer = console.input(
                f"  [cyan]{key}[/cyan] [{display_default}]: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        return answer if answer else default

    # ------------------------------------------------------------------
    # E1: Vault initialization
    # ------------------------------------------------------------------

    def init_vault(self) -> bool:
        """Initialize the encrypted vault if it does not already exist.

        Returns True if vault was initialized (or already existed).
        Returns False if age is not available.
        """
        if not shutil.which("age-keygen"):
            return False

        try:
            from superpowers.vault import Vault

            v = Vault(
                vault_path=self.data_dir / "vault.enc",
                identity_file=self.data_dir / "age-identity.txt",
            )
            v.init()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # E2: Telegram setup
    # ------------------------------------------------------------------

    def setup_telegram(
        self,
        bot_token: str | None = None,
        webhook_url: str | None = None,
        allowed_chat_ids: str | None = None,
    ) -> dict[str, Any]:
        """Configure Telegram bot integration.

        Args:
            bot_token: Telegram Bot API token from BotFather.
            webhook_url: Optional HTTPS URL for webhook mode.
            allowed_chat_ids: Comma-separated allowlist of chat IDs.

        Returns:
            Dict with keys: valid (bool), bot_info (dict|None),
            webhook_set (bool), config (dict).
        """
        result: dict[str, Any] = {
            "valid": False,
            "bot_info": None,
            "webhook_set": False,
            "config": {},
        }

        # Get token from args, values dict, or prompt
        token = (
            bot_token
            or self.values.get("TELEGRAM_BOT_TOKEN")
            or (
                ""
                if self.non_interactive
                else self._prompt_value("TELEGRAM_BOT_TOKEN", "")
            )
        )

        if not token:
            return result

        # Validate token via getMe API
        bot_info = self._validate_telegram_token(token)
        if bot_info:
            result["valid"] = True
            result["bot_info"] = bot_info

        # Webhook URL
        wh_url = (
            webhook_url
            or self.values.get("TELEGRAM_WEBHOOK_URL")
            or (
                ""
                if self.non_interactive
                else self._prompt_value("TELEGRAM_WEBHOOK_URL", "")
            )
        )

        if wh_url and result["valid"]:
            result["webhook_set"] = self._set_telegram_webhook(token, wh_url)

        # Allowed chat IDs
        chat_ids = (
            allowed_chat_ids
            or self.values.get("ALLOWED_CHAT_IDS")
            or (
                ""
                if self.non_interactive
                else self._prompt_value("ALLOWED_CHAT_IDS", "")
            )
        )

        result["config"] = {
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_WEBHOOK_URL": wh_url or "",
            "ALLOWED_CHAT_IDS": chat_ids or "",
            "TELEGRAM_MODE": "webhook" if wh_url else "polling",
        }

        return result

    @staticmethod
    def _validate_telegram_token(token: str) -> dict | None:
        """Call Telegram getMe API to validate the bot token.

        Returns the bot info dict on success, None on failure.
        """
        try:
            import urllib.request
            import json

            url = f"https://api.telegram.org/bot{token}/getMe"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data.get("ok"):
                    return data.get("result")
        except Exception:
            pass
        return None

    @staticmethod
    def _set_telegram_webhook(token: str, webhook_url: str) -> bool:
        """Set the Telegram bot webhook URL.

        Returns True on success.
        """
        try:
            import urllib.request
            import urllib.parse
            import json

            params = urllib.parse.urlencode({"url": webhook_url})
            url = f"https://api.telegram.org/bot{token}/setWebhook?{params}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return bool(data.get("ok"))
        except Exception:
            return False

    @staticmethod
    def print_telegram_instructions() -> None:
        """Print instructions for creating a Telegram bot."""
        instructions = (
            "[bold]Telegram Bot Setup[/bold]\n\n"
            "1. Open Telegram and search for [cyan]@BotFather[/cyan]\n"
            "2. Send [cyan]/newbot[/cyan] and follow the prompts\n"
            "3. Copy the HTTP API token (looks like: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)\n"
            "4. To get your chat ID, send a message to your bot, then visit:\n"
            "   https://api.telegram.org/bot<TOKEN>/getUpdates\n"
            "5. Set TELEGRAM_BOT_TOKEN and ALLOWED_CHAT_IDS in your .env\n\n"
            "[dim]For webhook mode, you also need a public HTTPS URL.[/dim]"
        )
        console.print(Panel(instructions, border_style="blue"))

    # ------------------------------------------------------------------
    # E1: Ensure data directories
    # ------------------------------------------------------------------

    def ensure_dirs(self) -> None:
        """Create the data directory structure."""
        settings = Settings(data_dir=self.data_dir)
        settings.ensure_dirs()

    # ------------------------------------------------------------------
    # E1: Full orchestration
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Run the full setup wizard, skipping already-completed steps.

        Returns a summary dict with the status of each step.
        """
        summary: dict[str, Any] = {}

        # Step 1: Prerequisites
        console.print("\n[bold]Step 1: Checking prerequisites...[/bold]")
        prereqs = self.check_prereqs()
        self.print_prereqs(prereqs)
        summary["prereqs"] = prereqs

        missing_required = []
        for tool in ("python", "docker", "docker-compose"):
            if not prereqs.get(tool, False):
                missing_required.append(tool)

        if missing_required:
            console.print(
                f"[yellow]Warning:[/yellow] Missing required tools: "
                f"{', '.join(missing_required)}"
            )

        # Step 2: Data directories
        console.print("\n[bold]Step 2: Creating data directories...[/bold]")
        self.ensure_dirs()
        console.print(f"  Data dir: [cyan]{self.data_dir}[/cyan]")
        summary["data_dir"] = str(self.data_dir)

        # Step 3: .env file
        env_path = self.project_dir / ".env"
        if env_path.exists():
            console.print("\n[bold]Step 3: .env file[/bold] [green]already exists[/green]")
            summary["env_created"] = False
        else:
            console.print("\n[bold]Step 3: Creating .env file...[/bold]")
            try:
                created = self.create_env()
                console.print(f"  Created: [cyan]{created}[/cyan]")
                summary["env_created"] = True
            except FileNotFoundError:
                console.print("  [yellow]Skipped:[/yellow] .env.example not found")
                summary["env_created"] = False

        # Step 4: Vault
        vault_path = self.data_dir / "vault.enc"
        if vault_path.exists():
            console.print("\n[bold]Step 4: Vault[/bold] [green]already initialized[/green]")
            summary["vault_initialized"] = True
        else:
            console.print("\n[bold]Step 4: Initializing vault...[/bold]")
            ok = self.init_vault()
            if ok:
                console.print("  [green]Vault initialized[/green]")
            else:
                console.print(
                    "  [yellow]Skipped:[/yellow] age-keygen not available"
                )
            summary["vault_initialized"] = ok

        # Step 5: Telegram (optional)
        console.print("\n[bold]Step 5: Telegram setup (optional)[/bold]")
        if self.non_interactive and "TELEGRAM_BOT_TOKEN" not in self.values:
            console.print("  [dim]Skipped (non-interactive, no token provided)[/dim]")
            summary["telegram"] = {"valid": False}
        else:
            tg = self.setup_telegram()
            if tg["valid"]:
                bot_name = tg["bot_info"].get("username", "unknown")
                console.print(f"  Bot: [cyan]@{bot_name}[/cyan] [green]validated[/green]")
            else:
                console.print("  [dim]Skipped or token invalid[/dim]")
            summary["telegram"] = tg

        console.print("\n[bold green]Setup complete![/bold green]\n")
        return summary
