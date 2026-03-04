"""Rsync engine — build commands, run transfers, parse progress, manage state."""

from __future__ import annotations

import json
import logging
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Validation patterns
_IPV4_RE = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$")
_IPV6_RE = re.compile(r"^[0-9a-fA-F:]+$")
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$")
_SHELL_META = re.compile(r"[;&|`$(){}!\n\r]")
_PATH_RE = re.compile(r"^/[^\x00;&|`$(){}!\n\r]*$")

# Rsync progress line: e.g. "  1,234,567  45%   12.34MB/s    0:01:23"
_PROGRESS_RE = re.compile(r"^\s*([\d,]+)\s+(\d+)%\s+(\S+/s)\s+([\d:]+)")
# Stats line patterns
_STATS_FILES_RE = re.compile(r"Number of regular files transferred:\s*([\d,]+)")
_STATS_TOTAL_RE = re.compile(r"Total transferred file size:\s*([\d,]+)")
_STATS_SPEED_RE = re.compile(r"sent.*bytes\s+received.*bytes\s+([\d,.]+)\s+bytes/sec")


@dataclass
class RsyncProgress:
    current_file: str = ""
    percent: int = 0
    speed: str = ""
    eta: str = ""
    bytes_transferred: int = 0
    files_transferred: int = 0


@dataclass
class RsyncStats:
    files_transferred: int = 0
    bytes_total: int = 0
    speed_avg: str = ""
    duration_seconds: float = 0.0
    exit_code: int = -1


@dataclass
class _RunningJob:
    """Internal tracking for a running rsync process."""

    process: subprocess.Popen | None = None
    progress_queue: queue.Queue = field(default_factory=queue.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    done_event: threading.Event = field(default_factory=threading.Event)


def _parse_comma_int(s: str) -> int:
    """Parse a comma-separated integer like '1,234,567'."""
    try:
        return int(s.replace(",", ""))
    except (ValueError, AttributeError):
        return 0


class RsyncEngine:
    """Manages rsync transfers with progress tracking and audit logging."""

    def __init__(self, db, audit=None):
        self._db = db
        self._audit = audit
        self._running: dict[str, _RunningJob] = {}
        self._lock = threading.Lock()

    def validate(
        self,
        source_host: str,
        source_path: str,
        dest_host: str,
        dest_path: str,
        source_user: str = "",
        dest_user: str = "",
        ssh_key: str = "",
    ) -> list[str]:
        """Return a list of validation errors (empty = valid)."""
        errors = []

        # Validate paths
        if not source_path:
            errors.append("Source path is required")
        elif not _PATH_RE.match(source_path):
            errors.append("Source path must be absolute and contain no shell metacharacters")

        if not dest_path:
            errors.append("Destination path is required")
        elif not _PATH_RE.match(dest_path):
            errors.append("Destination path must be absolute and contain no shell metacharacters")

        # Validate hosts (if provided)
        for label, host in [("Source host", source_host), ("Dest host", dest_host)]:
            if host and not (
                _IPV4_RE.match(host) or _IPV6_RE.match(host) or _HOSTNAME_RE.match(host)
            ):
                errors.append(f"{label} '{host}' is not a valid IP or hostname")

        # Validate users
        for label, user in [("Source user", source_user), ("Dest user", dest_user)]:
            if user and _SHELL_META.search(user):
                errors.append(f"{label} contains invalid characters")

        # Validate SSH key path
        if ssh_key:
            if _SHELL_META.search(ssh_key):
                errors.append("SSH key path contains invalid characters")

        # At least check metachar injection on paths
        if source_path and _SHELL_META.search(source_path):
            errors.append("Source path contains shell metacharacters")
        if dest_path and _SHELL_META.search(dest_path):
            errors.append("Dest path contains shell metacharacters")

        return errors

    def build_command(self, job: dict) -> list[str]:
        """Build the rsync command arguments list."""
        opts = job.get("options", {})
        source_host = job.get("source_host", "")
        source_path = job["source_path"]
        source_user = job.get("source_user", "root")
        dest_host = job.get("dest_host", "")
        dest_path = job["dest_path"]
        dest_user = job.get("dest_user", "root")
        ssh_key = job.get("ssh_key", "")

        cmd = ["rsync", "-avz", "--progress", "--itemize-changes", "--stats"]

        # SSH options
        ssh_cmd_parts = ["ssh"]
        if ssh_key:
            ssh_cmd_parts.extend(["-i", ssh_key])
        ssh_cmd_parts.append("-o")
        ssh_cmd_parts.append("StrictHostKeyChecking=accept-new")
        cmd.extend(["-e", " ".join(ssh_cmd_parts)])

        # Optional flags
        if opts.get("delete"):
            cmd.append("--delete")
        if opts.get("dry_run"):
            cmd.append("--dry-run")
        for pattern in opts.get("exclude_patterns", []):
            if pattern and not _SHELL_META.search(pattern):
                cmd.extend(["--exclude", pattern])
        bw = opts.get("bandwidth_limit_kbps", 0)
        if bw and isinstance(bw, int) and bw > 0:
            cmd.extend(["--bwlimit", str(bw)])

        # Source
        if source_host:
            cmd.append(f"{source_user}@{source_host}:{source_path}")
        else:
            cmd.append(source_path)

        # Destination
        if dest_host:
            cmd.append(f"{dest_user}@{dest_host}:{dest_path}")
        else:
            cmd.append(dest_path)

        return cmd

    def start(self, job_id: str) -> None:
        """Start an rsync job in a background thread."""
        job = self._db.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        running = _RunningJob()
        with self._lock:
            self._running[job_id] = running

        thread = threading.Thread(target=self._run_job, args=(job_id, job, running), daemon=True)
        thread.start()

    def _run_job(self, job_id: str, job: dict, running: _RunningJob) -> None:
        """Execute rsync in a subprocess and track progress."""
        cmd = self.build_command(job)
        logger.info("rsync start job=%s cmd=%s", job_id, " ".join(cmd))

        if self._audit:
            src = (
                f"{job.get('source_user', '')}@{job.get('source_host', '')}:{job['source_path']}"
                if job.get("source_host")
                else job["source_path"]
            )
            dst = (
                f"{job.get('dest_user', '')}@{job.get('dest_host', '')}:{job['dest_path']}"
                if job.get("dest_host")
                else job["dest_path"]
            )
            self._audit.log(
                "rsync_start", f"{src} -> {dst}", source="rsync", metadata={"job_id": job_id}
            )

        start_time = time.time()
        self._db.update_status(job_id, "running", started_at=start_time)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            running.process = proc
            self._db.update_status(job_id, "running", pid=proc.pid)

            output_lines: list[str] = []
            current_file = ""
            last_update = 0.0
            files_count = 0

            for line in iter(proc.stdout.readline, ""):  # type: ignore[union-attr]
                if running.cancel_event.is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    self._db.complete(
                        job_id, "cancelled", "{}", "\n".join(output_lines), "Cancelled by user"
                    )
                    if self._audit:
                        self._audit.log("rsync_cancel", f"job {job_id} cancelled", source="rsync")
                    return

                output_lines.append(line.rstrip())
                progress = self._parse_progress(line)

                if progress:
                    progress.current_file = current_file
                    progress.files_transferred = files_count
                    now = time.time()
                    if now - last_update >= 0.5:
                        pdata = {
                            "current_file": progress.current_file,
                            "percent": progress.percent,
                            "speed": progress.speed,
                            "eta": progress.eta,
                            "bytes_transferred": progress.bytes_transferred,
                            "files_transferred": progress.files_transferred,
                        }
                        self._db.update_progress(job_id, json.dumps(pdata))
                        running.progress_queue.put(pdata)
                        last_update = now
                else:
                    stripped = line.strip()
                    if stripped and not stripped.startswith(
                        ("sending", "sent ", "total ", "Number", "File list")
                    ):
                        current_file = stripped
                        # Lines like ">f+++++++ path/file" indicate a transferred file
                        if stripped.startswith(">f") or stripped.startswith("cd"):
                            files_count += 1

            stderr = proc.stderr.read() if proc.stderr else ""  # type: ignore[union-attr]
            proc.wait()

            duration = time.time() - start_time
            stats = self._parse_stats("\n".join(output_lines))
            stats.exit_code = proc.returncode
            stats.duration_seconds = duration

            stats_dict = {
                "files_transferred": stats.files_transferred,
                "bytes_total": stats.bytes_total,
                "speed_avg": stats.speed_avg,
                "duration_seconds": round(stats.duration_seconds, 1),
                "exit_code": stats.exit_code,
            }

            is_dry = job.get("options", {}).get("dry_run", False)
            if proc.returncode == 0:
                final_status = "dry-run" if is_dry else "completed"
            else:
                final_status = "failed"

            self._db.complete(
                job_id,
                final_status,
                json.dumps(stats_dict),
                "\n".join(output_lines[-500:]),
                stderr[:5000],
            )

            # Final progress push
            running.progress_queue.put(
                {
                    "current_file": "",
                    "percent": 100 if proc.returncode == 0 else -1,
                    "speed": "",
                    "eta": "",
                    "files_transferred": stats.files_transferred,
                    "bytes_transferred": stats.bytes_total,
                    "done": True,
                    "status": final_status,
                }
            )

            if self._audit:
                self._audit.log(
                    "rsync_complete",
                    f"job {job_id} {final_status} ({stats.files_transferred} files, {duration:.1f}s)",
                    source="rsync",
                    metadata={"job_id": job_id, "exit_code": proc.returncode},
                )

        except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
            logger.exception("rsync job %s failed: %s", job_id, exc)
            self._db.complete(job_id, "failed", "{}", "", str(exc))
            running.progress_queue.put({"done": True, "status": "failed", "error": str(exc)})
            if self._audit:
                self._audit.log("rsync_error", f"job {job_id}: {exc}", source="rsync")
        finally:
            running.done_event.set()
            # Clean up after a delay so SSE clients can read final event
            threading.Timer(30.0, self._cleanup_job, args=(job_id,)).start()

    def cancel(self, job_id: str) -> bool:
        """Cancel a running rsync job."""
        with self._lock:
            running = self._running.get(job_id)
        if not running:
            return False
        running.cancel_event.set()
        if running.process and running.process.poll() is None:
            try:
                running.process.terminate()
                running.process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    running.process.kill()
                except OSError:
                    pass
        return True

    def get_progress_stream(self, job_id: str):
        """Yield progress dicts for SSE streaming."""
        with self._lock:
            running = self._running.get(job_id)

        if not running:
            # Job might already be done — return the stored state
            job = self._db.get(job_id)
            if job and job.get("status") in ("completed", "failed", "cancelled", "dry-run"):
                yield {"done": True, "status": job["status"], **job.get("progress", {})}
            return

        while True:
            try:
                data = running.progress_queue.get(timeout=2)
                yield data
                if data.get("done"):
                    return
            except queue.Empty:
                if running.done_event.is_set():
                    return
                # Send keepalive
                yield {"keepalive": True}

    def _cleanup_job(self, job_id: str) -> None:
        with self._lock:
            self._running.pop(job_id, None)

    @staticmethod
    def _parse_progress(line: str) -> RsyncProgress | None:
        """Parse a progress line from rsync output."""
        m = _PROGRESS_RE.search(line)
        if not m:
            return None
        return RsyncProgress(
            bytes_transferred=_parse_comma_int(m.group(1)),
            percent=int(m.group(2)),
            speed=m.group(3),
            eta=m.group(4),
        )

    @staticmethod
    def _parse_stats(output: str) -> RsyncStats:
        """Parse the final --stats summary from rsync output."""
        stats = RsyncStats()

        m = _STATS_FILES_RE.search(output)
        if m:
            stats.files_transferred = _parse_comma_int(m.group(1))

        m = _STATS_TOTAL_RE.search(output)
        if m:
            stats.bytes_total = _parse_comma_int(m.group(1))

        m = _STATS_SPEED_RE.search(output)
        if m:
            stats.speed_avg = m.group(1) + " bytes/sec"

        return stats
