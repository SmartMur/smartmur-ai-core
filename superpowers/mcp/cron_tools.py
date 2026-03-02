from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def cron_add_job(
        name: str,
        schedule: str,
        job_type: str,
        command: str,
        output_channel: str = "file",
    ) -> str:
        """Add a new cron job and return its ID.

        Args:
            name: Human-readable job name.
            schedule: Schedule expression — cron syntax ("*/5 * * * *"), interval ("every 10m"), or daily ("daily at 09:00").
            job_type: One of: shell, claude, webhook, skill.
            command: The command/prompt/URL/skill-name to execute.
            output_channel: Where to route output — "file" (default), a profile name, or "channel:#target".
        """
        try:
            from superpowers.cron_engine import CronEngine

            engine = CronEngine()
            job = engine.add_job(
                name=name,
                schedule=schedule,
                job_type=job_type,
                command=command,
                output_channel=output_channel,
            )
            engine.stop()
            return f"Job added: {job.id} ({job.name}, {job.schedule}, {job.job_type.value})"
        except Exception as exc:
            return f"Error adding job: {exc}"

    @mcp.tool()
    def cron_remove_job(job_id: str) -> str:
        """Remove a cron job by ID.

        Args:
            job_id: The UUID of the job to remove.
        """
        try:
            from superpowers.cron_engine import CronEngine

            engine = CronEngine()
            engine.remove_job(job_id)
            engine.stop()
            return f"Job removed: {job_id}"
        except KeyError:
            return f"Job not found: {job_id}"
        except Exception as exc:
            return f"Error removing job: {exc}"

    @mcp.tool()
    def cron_list_jobs() -> str:
        """List all cron jobs with their status."""
        try:
            from superpowers.cron_engine import CronEngine

            engine = CronEngine()
            jobs = engine.list_jobs()
            engine.stop()

            if not jobs:
                return "No cron jobs configured."

            lines = [f"{len(jobs)} job(s):"]
            for j in jobs:
                status = "enabled" if j.enabled else "disabled"
                last = j.last_status or "never run"
                lines.append(
                    f"  {j.id[:8]}  {j.name}  [{status}]  {j.schedule}  "
                    f"{j.job_type.value}: {j.command[:60]}  last: {last}"
                )
            return "\n".join(lines)
        except Exception as exc:
            return f"Error listing jobs: {exc}"

    @mcp.tool()
    def cron_enable_job(job_id: str) -> str:
        """Enable a disabled cron job.

        Args:
            job_id: The UUID of the job to enable.
        """
        try:
            from superpowers.cron_engine import CronEngine

            engine = CronEngine()
            job = engine.enable_job(job_id)
            engine.stop()
            return f"Job enabled: {job.name} ({job_id[:8]})"
        except KeyError:
            return f"Job not found: {job_id}"
        except Exception as exc:
            return f"Error enabling job: {exc}"

    @mcp.tool()
    def cron_disable_job(job_id: str) -> str:
        """Disable a cron job without removing it.

        Args:
            job_id: The UUID of the job to disable.
        """
        try:
            from superpowers.cron_engine import CronEngine

            engine = CronEngine()
            job = engine.disable_job(job_id)
            engine.stop()
            return f"Job disabled: {job.name} ({job_id[:8]})"
        except KeyError:
            return f"Job not found: {job_id}"
        except Exception as exc:
            return f"Error disabling job: {exc}"

    @mcp.tool()
    def cron_job_logs(job_id: str, limit: int = 5) -> str:
        """Read recent output logs for a cron job.

        Args:
            job_id: The UUID of the job.
            limit: Maximum number of log entries to return (default 5).
        """
        try:
            from superpowers.config import get_data_dir

            log_dir = get_data_dir() / "cron" / "output" / job_id
            if not log_dir.is_dir():
                return f"No logs found for job {job_id}"

            log_files = sorted(log_dir.glob("*.log"), reverse=True)[:limit]
            if not log_files:
                return f"No log files in {log_dir}"

            lines = [f"Last {len(log_files)} log(s) for job {job_id[:8]}:"]
            for lf in log_files:
                content = lf.read_text().strip()
                lines.append(f"\n--- {lf.name} ---")
                # Truncate very long outputs
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                lines.append(content)
            return "\n".join(lines)
        except Exception as exc:
            return f"Error reading logs: {exc}"
