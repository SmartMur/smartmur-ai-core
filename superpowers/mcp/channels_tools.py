from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def send_message(channel: str, target: str, message: str) -> str:
        """Send a message via a channel adapter (slack, telegram, discord, email).

        Args:
            channel: Channel name — one of: slack, telegram, discord, email.
            target: Channel-specific target (e.g. Slack channel "#general", email address, Telegram chat ID).
            message: The message body to send.
        """
        try:
            from superpowers.channels.registry import ChannelRegistry
            from superpowers.config import Settings

            settings = Settings.load()
            registry = ChannelRegistry(settings)
            ch = registry.get(channel)
            result = ch.send(target, message)
            if result.ok:
                return f"Sent to {channel}:{target} successfully."
            return f"Failed to send to {channel}:{target} — {result.error}"
        except Exception as exc:
            return f"Error sending message: {exc}"

    @mcp.tool()
    def test_channel(channel: str) -> str:
        """Test channel credentials and connectivity.

        Args:
            channel: Channel name to test — one of: slack, telegram, discord, email.
        """
        try:
            from superpowers.channels.registry import ChannelRegistry
            from superpowers.config import Settings

            settings = Settings.load()
            registry = ChannelRegistry(settings)
            ch = registry.get(channel)
            result = ch.test_connection()
            if result.ok:
                return f"Channel '{channel}' is working. {result.message}"
            return f"Channel '{channel}' test failed: {result.error}"
        except Exception as exc:
            return f"Error testing channel: {exc}"

    @mcp.tool()
    def list_channels() -> str:
        """List all available messaging channels that have credentials configured."""
        try:
            from superpowers.channels.registry import ChannelRegistry
            from superpowers.config import Settings

            settings = Settings.load()
            registry = ChannelRegistry(settings)
            available = registry.available()
            if not available:
                return "No channels configured. Set credentials in .env (SLACK_BOT_TOKEN, TELEGRAM_BOT_TOKEN, etc.)."
            return "Configured channels:\n" + "\n".join(f"  - {name}" for name in available)
        except Exception as exc:
            return f"Error listing channels: {exc}"

    @mcp.tool()
    def send_notification(profile: str, message: str) -> str:
        """Send a message to all targets in a notification profile.

        Args:
            profile: Profile name defined in ~/.claude-superpowers/profiles.yaml.
            message: The message body to send.
        """
        try:
            from superpowers.channels.registry import ChannelRegistry
            from superpowers.config import Settings
            from superpowers.profiles import ProfileManager

            settings = Settings.load()
            registry = ChannelRegistry(settings)
            pm = ProfileManager(registry)
            results = pm.send(profile, message)

            lines = [f"Profile '{profile}' — {len(results)} target(s):"]
            for r in results:
                status = "OK" if r.ok else f"FAIL: {r.error}"
                lines.append(f"  {r.channel}:{r.target} — {status}")
            return "\n".join(lines)
        except KeyError as exc:
            return f"Profile not found: {exc}"
        except Exception as exc:
            return f"Error sending notification: {exc}"

    @mcp.tool()
    def list_profiles() -> str:
        """List notification profiles and their channel/target mappings."""
        try:
            from superpowers.channels.registry import ChannelRegistry
            from superpowers.config import Settings
            from superpowers.profiles import ProfileManager

            settings = Settings.load()
            registry = ChannelRegistry(settings)
            pm = ProfileManager(registry)
            profiles = pm.list_profiles()

            if not profiles:
                return "No profiles configured. Create ~/.claude-superpowers/profiles.yaml."

            lines = []
            for p in profiles:
                lines.append(f"{p.name}:")
                for t in p.targets:
                    lines.append(f"  - {t.channel} -> {t.target}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Error listing profiles: {exc}"
