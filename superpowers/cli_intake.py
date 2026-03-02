"""Click commands for mandatory request intake workflow."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

import click
from rich.console import Console
from rich.table import Table

from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings, get_data_dir
from superpowers.intake import clear_context, run_intake
from superpowers.intake_telemetry import IntakeTelemetry

console = Console()
PENDING_TELEGRAM_UPDATES = get_data_dir() / "runtime" / "pending_telegram_updates.jsonl"


def _discover_telegram_chat_id(bot_token: str) -> str:
    """Best-effort chat_id discovery from recent bot updates."""
    if not bot_token:
        return ""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?limit=25"
    data: dict = {}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            break
        except (urllib.error.URLError, json.JSONDecodeError):
            if attempt >= 2:
                return ""
            time.sleep(1.0 * (2 ** attempt))
    else:
        return ""

    if not data.get("ok"):
        return ""

    for upd in reversed(data.get("result", [])):
        msg = upd.get("message") or upd.get("channel_post") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is not None:
            return str(chat_id)
    return ""


def _send_telegram_update(message: str, chat_id: str = "") -> tuple[bool, str]:
    settings = Settings.load()
    if not settings.telegram_bot_token:
        return False, "telegram token not configured"

    target = chat_id or settings.telegram_default_chat_id or _discover_telegram_chat_id(settings.telegram_bot_token)
    if not target:
        _queue_telegram_update(message)
        return False, "telegram chat_id unavailable; update queued (set TELEGRAM_DEFAULT_CHAT_ID or message bot once)"

    reg = ChannelRegistry(settings)
    try:
        ch = reg.get("telegram")
        result = ch.send(target, message)
    except Exception as exc:
        return False, f"telegram send exception: {exc}"

    if result.ok:
        _flush_pending_telegram_updates(target)
        return True, f"sent to telegram:{target}"
    return False, result.error or "telegram send failed"


def _queue_telegram_update(message: str) -> None:
    PENDING_TELEGRAM_UPDATES.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "message": message,
    }
    with open(PENDING_TELEGRAM_UPDATES, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _flush_pending_telegram_updates(chat_id: str) -> int:
    if not PENDING_TELEGRAM_UPDATES.exists():
        return 0

    settings = Settings.load()
    reg = ChannelRegistry(settings)
    ch = reg.get("telegram")

    lines = PENDING_TELEGRAM_UPDATES.read_text().splitlines()
    pending = []
    sent = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = item.get("message", "")
        if not message:
            continue
        result = ch.send(chat_id, message)
        if result.ok:
            sent += 1
        else:
            pending.append(line)

    if pending:
        PENDING_TELEGRAM_UPDATES.write_text("\n".join(pending) + "\n")
    else:
        PENDING_TELEGRAM_UPDATES.unlink(missing_ok=True)

    return sent


@click.group("intake")
def intake_group():
    """Clear context, plan requirements, and dispatch skills."""


@intake_group.command("clear")
def intake_clear():
    """Clear runtime context before handling a new request."""
    marker = clear_context()
    console.print(f"[green]Context cleared.[/green] {marker}")


@intake_group.command("run")
@click.argument("request_text")
@click.option("--execute", is_flag=True, help="Execute mapped skills in parallel.")
@click.option("--max-workers", default=4, show_default=True, type=int)
@click.option("--notify-telegram/--no-notify-telegram", default=True, show_default=True, help="Send start/finish updates to Telegram.")
@click.option("--telegram-chat", default="", help="Override Telegram chat_id for progress updates.")
@click.option("--role", type=click.Choice(["planner", "executor", "verifier", "all"], case_sensitive=False), default="all", show_default=True, help="Only run tasks assigned to this role.")
def intake_run(request_text: str, execute: bool, max_workers: int, notify_telegram: bool, telegram_chat: str, role: str):
    """Run intake pipeline: clear -> plan -> dispatch (-> execute optional)."""
    telemetry = IntakeTelemetry()

    if notify_telegram:
        ok, detail = _send_telegram_update(
            (
                "Intake started\n"
                f"execute={execute}\n"
                f"role={role}\n"
                f"request={request_text[:300]}"
            ),
            chat_id=telegram_chat,
        )
        telemetry.notification_sent("telegram", "start", ok)
        if ok:
            console.print(f"[green]Telegram:[/green] {detail}")
        else:
            console.print(f"[yellow]Telegram skipped:[/yellow] {detail}")

    payload = run_intake(request_text, execute=execute, max_workers=max_workers, telemetry=telemetry, role=role)

    table = Table(title="Request Intake")
    table.add_column("#", style="dim", width=3)
    table.add_column("Requirement", style="cyan")
    table.add_column("Role", style="blue")
    table.add_column("Skill", style="magenta")
    table.add_column("Status")
    table.add_column("Error")

    for task in payload["tasks"]:
        status = task["status"]
        if status == "ok":
            status = "[green]ok[/green]"
        elif status == "failed":
            status = "[red]failed[/red]"
        elif status == "running":
            status = "[yellow]running[/yellow]"
        else:
            status = f"[dim]{task['status']}[/dim]"

        table.add_row(
            str(task["id"]),
            task["requirement"][:80],
            task.get("assigned_role", "executor"),
            task["skill"] or "-",
            status,
            (task.get("error") or "")[:60],
        )

    console.print(table)
    console.print("[dim]Session saved to ~/.claude-superpowers/runtime/current_request.json[/dim]")

    if notify_telegram:
        counts = {
            "ok": sum(1 for t in payload["tasks"] if t["status"] == "ok"),
            "failed": sum(1 for t in payload["tasks"] if t["status"] == "failed"),
            "planned": sum(1 for t in payload["tasks"] if t["status"] == "planned"),
            "running": sum(1 for t in payload["tasks"] if t["status"] == "running"),
            "skipped": sum(1 for t in payload["tasks"] if t["status"] == "skipped"),
        }
        ok, detail = _send_telegram_update(
            (
                "Intake finished\n"
                f"execute={execute}\n"
                f"tasks={len(payload['tasks'])}\n"
                f"ok={counts['ok']} failed={counts['failed']} planned={counts['planned']} skipped={counts['skipped']}"
            ),
            chat_id=telegram_chat,
        )
        telemetry.notification_sent("telegram", "finish", ok)
        if ok:
            console.print(f"[green]Telegram:[/green] {detail}")
        else:
            console.print(f"[yellow]Telegram skipped:[/yellow] {detail}")

    if execute and any(t["status"] == "failed" for t in payload["tasks"]):
        raise SystemExit(1)


@intake_group.command("show")
def intake_show():
    """Show current intake session JSON."""
    from superpowers.intake import SESSION_FILE

    if not SESSION_FILE.exists():
        console.print("[dim]No intake session found.[/dim]")
        return
    data = json.loads(SESSION_FILE.read_text())
    console.print_json(data=data)


@intake_group.command("flush-telegram")
@click.option("--telegram-chat", default="", help="Override Telegram chat_id target.")
def intake_flush_telegram(telegram_chat: str):
    """Flush queued Telegram updates once a chat_id is known."""
    settings = Settings.load()
    target = telegram_chat or settings.telegram_default_chat_id or _discover_telegram_chat_id(settings.telegram_bot_token)
    if not target:
        console.print("[yellow]No Telegram chat_id available.[/yellow] Message the bot once or set TELEGRAM_DEFAULT_CHAT_ID.")
        raise SystemExit(1)

    sent = _flush_pending_telegram_updates(target)
    console.print(f"[green]Flushed[/green] {sent} queued Telegram updates to {target}.")
