#!/usr/bin/env python3
"""Discord server bootstrap for branding, channels, and local admin credential."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import secrets
import string
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

API_BASE = "https://discord.com/api/v10"

CHANNEL_TYPE = {
    "text": 0,
    "voice": 2,
    "category": 4,
}


class DiscordApiError(RuntimeError):
    """Raised when the Discord API returns an error."""


def _load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            env[key] = value
    return env


def _clean_env_value(value: str | None) -> str:
    value = (value or "").strip()
    if not value or value.startswith("#"):
        return ""
    return value


def _env(name: str, dotenv: dict[str, str]) -> str:
    return _clean_env_value(os.environ.get(name) or dotenv.get(name, ""))


def _mime_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    raise ValueError(f"Unsupported icon format: {ext}")


def _data_uri_for_icon(icon_path: Path) -> str:
    mime = _mime_for_path(icon_path)
    encoded = base64.b64encode(icon_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _generate_password(length: int) -> str:
    length = max(20, int(length))
    alphabet_lower = string.ascii_lowercase
    alphabet_upper = string.ascii_uppercase
    alphabet_digit = string.digits
    alphabet_punct = "!@#$%^&*()-_=+[]{}"

    required = [
        secrets.choice(alphabet_lower),
        secrets.choice(alphabet_upper),
        secrets.choice(alphabet_digit),
        secrets.choice(alphabet_punct),
    ]
    alphabet = alphabet_lower + alphabet_upper + alphabet_digit + alphabet_punct
    required.extend(secrets.choice(alphabet) for _ in range(length - len(required)))
    secrets.SystemRandom().shuffle(required)
    return "".join(required)


def _hash_password(password: str, iterations: int = 250_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${iterations}${salt_b64}${digest_b64}"


def _parse_color(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError(f"Unsupported color value: {value!r}")


class DiscordApi:
    """Small Discord REST client."""

    def __init__(self, token: str, dry_run: bool = False):
        self.token = token
        self.dry_run = dry_run

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{API_BASE}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
        }

        if self.dry_run and method.upper() in {"POST", "PATCH", "PUT", "DELETE"}:
            print(f"[dry-run] {method} {path} payload={json.dumps(payload or {})}")
            return {}

        req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8")) if body else {}
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise DiscordApiError(f"{method} {path} failed: HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise DiscordApiError(f"{method} {path} failed: {exc}") from exc

    def list_guilds(self) -> list[dict[str, Any]]:
        result = self.request("GET", "/users/@me/guilds")
        return result if isinstance(result, list) else []

    def update_guild(self, guild_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PATCH", f"/guilds/{guild_id}", payload)

    def list_roles(self, guild_id: str) -> list[dict[str, Any]]:
        result = self.request("GET", f"/guilds/{guild_id}/roles")
        return result if isinstance(result, list) else []

    def create_role(self, guild_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", f"/guilds/{guild_id}/roles", payload)

    def update_role(self, guild_id: str, role_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PATCH", f"/guilds/{guild_id}/roles/{role_id}", payload)

    def list_channels(self, guild_id: str) -> list[dict[str, Any]]:
        result = self.request("GET", f"/guilds/{guild_id}/channels")
        return result if isinstance(result, list) else []

    def create_channel(self, guild_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", f"/guilds/{guild_id}/channels", payload)


def _resolve_guild_id(
    api: DiscordApi,
    cfg_guild_id: str,
    env_guild_id: str,
) -> str:
    if cfg_guild_id:
        return cfg_guild_id
    if env_guild_id:
        return env_guild_id

    guilds = api.list_guilds()
    if len(guilds) == 1:
        return str(guilds[0]["id"])
    if not guilds:
        raise DiscordApiError("Bot is not in any Discord guilds.")

    hint = ", ".join(f"{g.get('name')}({g.get('id')})" for g in guilds[:10])
    raise DiscordApiError(
        "Multiple guilds found. Set discord.guild_id in config.yaml or DISCORD_GUILD_ID "
        f"in environment. Visible guilds: {hint}"
    )


def _apply_branding(api: DiscordApi, guild_id: str, cfg: dict[str, Any], config_dir: Path) -> None:
    server_cfg = cfg.get("server", {})
    payload: dict[str, Any] = {}
    if server_cfg.get("name"):
        payload["name"] = server_cfg["name"]
    if server_cfg.get("description"):
        payload["description"] = server_cfg["description"]

    icon_path = server_cfg.get("icon_path", "")
    if icon_path:
        resolved_icon = (config_dir / icon_path).resolve()
        if resolved_icon.is_file():
            payload["icon"] = _data_uri_for_icon(resolved_icon)
        else:
            print(f"[warn] icon_path does not exist, skipping icon update: {resolved_icon}")

    if payload:
        api.update_guild(guild_id, payload)


def _ensure_roles(api: DiscordApi, guild_id: str, cfg: dict[str, Any]) -> tuple[int, int]:
    created = 0
    updated = 0

    desired_roles = cfg.get("roles", [])
    if not desired_roles:
        return created, updated

    existing_roles = api.list_roles(guild_id)
    by_name = {r.get("name", "").lower(): r for r in existing_roles}

    for role_cfg in desired_roles:
        name = str(role_cfg["name"])
        payload = {
            "name": name,
            "color": _parse_color(role_cfg.get("color", 0)),
            "hoist": bool(role_cfg.get("hoist", False)),
            "mentionable": bool(role_cfg.get("mentionable", False)),
            "permissions": str(role_cfg.get("permissions", "0")),
        }

        current = by_name.get(name.lower())
        if current is None:
            new_role = api.create_role(guild_id, payload)
            by_name[name.lower()] = new_role
            created += 1
        else:
            api.update_role(guild_id, str(current["id"]), payload)
            updated += 1

    return created, updated


def _find_channel(
    channels: list[dict[str, Any]],
    *,
    name: str,
    channel_type: int,
    parent_id: str | None,
) -> dict[str, Any] | None:
    low_name = name.lower()
    for ch in channels:
        if int(ch.get("type", -1)) != int(channel_type):
            continue
        if ch.get("name", "").lower() != low_name:
            continue
        if parent_id is None and ch.get("parent_id") in (None, ""):
            return ch
        if parent_id is not None and str(ch.get("parent_id")) == str(parent_id):
            return ch
    return None


def _ensure_categories_and_channels(api: DiscordApi, guild_id: str, cfg: dict[str, Any]) -> tuple[int, int]:
    categories_created = 0
    channels_created = 0
    existing_channels = api.list_channels(guild_id)

    for category_cfg in cfg.get("categories", []):
        cat_name = str(category_cfg["name"])
        category = _find_channel(
            existing_channels,
            name=cat_name,
            channel_type=CHANNEL_TYPE["category"],
            parent_id=None,
        )
        if category is None:
            category = api.create_channel(
                guild_id,
                {
                    "name": cat_name,
                    "type": CHANNEL_TYPE["category"],
                },
            )
            existing_channels.append(category)
            categories_created += 1

        parent_id = str(category["id"])
        for channel_cfg in category_cfg.get("channels", []):
            ch_name = str(channel_cfg["name"])
            ch_type_name = str(channel_cfg.get("type", "text")).lower()
            if ch_type_name not in CHANNEL_TYPE:
                raise ValueError(f"Unsupported channel type in config: {ch_type_name}")
            ch_type = CHANNEL_TYPE[ch_type_name]
            current = _find_channel(
                existing_channels,
                name=ch_name,
                channel_type=ch_type,
                parent_id=parent_id,
            )
            if current is not None:
                continue

            payload = {
                "name": ch_name,
                "type": ch_type,
                "parent_id": parent_id,
            }
            if ch_type_name == "text" and channel_cfg.get("topic"):
                payload["topic"] = str(channel_cfg["topic"])
            new_channel = api.create_channel(guild_id, payload)
            existing_channels.append(new_channel)
            channels_created += 1

    return categories_created, channels_created


def _write_admin_credentials(
    path: Path,
    username: str,
    password_hash: str,
    discord_role: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "username": username,
        "password_hash": password_hash,
        "discord_role": discord_role,
        "algorithm": "pbkdf2_sha256",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Bootstrap Discord branding and structure.")
    parser.add_argument(
        "--config",
        default=str(script_dir / "config.yaml"),
        help="Path to bootstrap config YAML.",
    )
    parser.add_argument(
        "--dotenv",
        default=str(script_dir.parent.parent / ".env"),
        help="Path to .env file for DISCORD_BOT_TOKEN and optional DISCORD_GUILD_ID.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print write operations without changing Discord resources.",
    )
    parser.add_argument(
        "--skip-discord",
        action="store_true",
        help="Skip Discord API provisioning and only generate local admin credentials.",
    )
    parser.add_argument(
        "--rotate-admin-password",
        action="store_true",
        help="Force rotation if admin credential file already exists.",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    dotenv_path = Path(args.dotenv).resolve()
    config_dir = config_path.parent

    if not config_path.is_file():
        print(f"[error] Config not found: {config_path}")
        return 1

    cfg = yaml.safe_load(config_path.read_text()) or {}
    dotenv = _load_dotenv(dotenv_path)

    admin_cfg = cfg.get("admin", {})
    admin_user = str(admin_cfg.get("username", "ray"))
    admin_len = int(admin_cfg.get("password_length", 32))
    admin_role = str(admin_cfg.get("discord_role", "Admin"))
    credentials_file = Path(str(admin_cfg.get("credentials_file", "./admin_credentials.json")))
    credentials_path = (config_dir / credentials_file).resolve()

    admin_password: str | None = None
    if credentials_path.exists() and not args.rotate_admin_password:
        print(f"[info] Admin credentials already exist: {credentials_path}")
        print("[info] Use --rotate-admin-password to generate a new password.")
    else:
        admin_password = _generate_password(admin_len)
        password_hash = _hash_password(admin_password)
        _write_admin_credentials(credentials_path, admin_user, password_hash, admin_role)
        print(f"[ok] Admin credentials written: {credentials_path}")
        print(f"ADMIN_USERNAME={admin_user}")
        print(f"ADMIN_PASSWORD={admin_password}")

    token = _env("DISCORD_BOT_TOKEN", dotenv)
    env_guild_id = _env("DISCORD_GUILD_ID", dotenv)
    cfg_guild_id = str((cfg.get("discord", {}) or {}).get("guild_id", "")).strip()

    summary: dict[str, Any] = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config_path": str(config_path),
        "credentials_path": str(credentials_path),
        "admin_username": admin_user,
        "admin_password_generated": bool(admin_password),
        "discord_provisioned": False,
        "guild_id": "",
        "roles_created": 0,
        "roles_updated": 0,
        "categories_created": 0,
        "channels_created": 0,
    }

    if args.skip_discord:
        print("[info] --skip-discord set, skipping Discord API provisioning.")
    elif not token:
        print("[warn] DISCORD_BOT_TOKEN missing/placeholder; Discord provisioning skipped.")
    else:
        api = DiscordApi(token=token, dry_run=args.dry_run)
        try:
            guild_id = _resolve_guild_id(api, cfg_guild_id, env_guild_id)
            _apply_branding(api, guild_id, cfg, config_dir)
            roles_created, roles_updated = _ensure_roles(api, guild_id, cfg)
            categories_created, channels_created = _ensure_categories_and_channels(api, guild_id, cfg)
        except DiscordApiError as exc:
            print(f"[error] Discord provisioning failed: {exc}")
            return 1

        summary["discord_provisioned"] = True
        summary["guild_id"] = guild_id
        summary["roles_created"] = roles_created
        summary["roles_updated"] = roles_updated
        summary["categories_created"] = categories_created
        summary["channels_created"] = channels_created
        print(f"[ok] Discord provisioning completed for guild_id={guild_id}")
        print(
            "[ok] Roles(created/updated): "
            f"{roles_created}/{roles_updated}, "
            f"Categories created: {categories_created}, "
            f"Channels created: {channels_created}"
        )

    last_run_path = config_dir / "last_run.json"
    last_run_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"[ok] Run summary written: {last_run_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

