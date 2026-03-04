from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


class JobType(StrEnum):
    shell = "shell"
    claude = "claude"
    webhook = "webhook"
    skill = "skill"


@dataclass
class Job:
    id: str
    name: str
    schedule: str
    job_type: JobType
    command: str
    args: dict[str, Any] = field(default_factory=dict)
    output_channel: str = "file"
    enabled: bool = True
    llm_model: str = ""  # Per-job model override; empty = use global JOB_MODEL
    created_at: str = ""
    last_run: str = ""
    last_status: str = ""
    last_output_file: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()
        if isinstance(self.job_type, str):
            self.job_type = JobType(self.job_type)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["job_type"] = self.job_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Job:
        return cls(**data)


# --- Schedule parsing ---

_INTERVAL_RE = re.compile(r"^every\s+(\d+)\s*([mhd])$", re.IGNORECASE)
_DAILY_AT_RE = re.compile(r"^daily\s+at\s+(\d{1,2}):(\d{2})$", re.IGNORECASE)
_CRON_RE = re.compile(r"^[\d*/,-]+(\s+[\d*/,-]+){4}$")


def parse_schedule(expr: str) -> CronTrigger | IntervalTrigger:
    expr = expr.strip()

    m = _INTERVAL_RE.match(expr)
    if m:
        amount, unit = int(m.group(1)), m.group(2).lower()
        if unit == "m":
            return IntervalTrigger(minutes=amount)
        elif unit == "h":
            return IntervalTrigger(hours=amount)
        elif unit == "d":
            return IntervalTrigger(days=amount)

    m = _DAILY_AT_RE.match(expr)
    if m:
        return CronTrigger(hour=int(m.group(1)), minute=int(m.group(2)))

    if _CRON_RE.match(expr):
        return CronTrigger.from_crontab(expr)

    raise ValueError(f"Unrecognised schedule expression: {expr!r}")


# --- Module-level registry for APScheduler callbacks ---
# APScheduler pickles the callable ref. Bound methods cause the whole object
# to be pickled, which fails because BackgroundScheduler isn't picklable.
# Instead we register a module-level function and look up the engine at runtime.

_engine_registry: dict[str, CronEngine] = {}


def _dispatch_job(engine_id: str, job_id: str) -> None:
    engine = _engine_registry.get(engine_id)
    if engine is not None:
        engine._execute_job(job_id)


class CronEngine:
    PID_FILENAME = "cron-daemon.pid"

    def __init__(
        self,
        jobs_file: Path | None = None,
        data_dir: Path | None = None,
    ):
        if data_dir is None:
            from superpowers.config import get_data_dir

            data_dir = get_data_dir() / "cron"
        self._data_dir = Path(data_dir)

        if jobs_file is None:
            jobs_file = self._data_dir / "jobs.json"
        self._jobs_file = Path(jobs_file)

        self._output_dir = self._data_dir / "output"
        self._db_path = self._data_dir / "scheduler.db"
        self._pid_file = self._data_dir / self.PID_FILENAME

        self._jobs: dict[str, Job] = {}

        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Unique id for this engine instance in the module-level registry
        self._engine_id = str(uuid.uuid4())
        _engine_registry[self._engine_id] = self

        self._scheduler = BackgroundScheduler(
            jobstores={
                "default": SQLAlchemyJobStore(url=f"sqlite:///{self._db_path}"),
            },
        )

        self._load_jobs()

    # --- Properties ---

    @property
    def jobs(self) -> dict[str, Job]:
        """Public read-only access to the jobs dict."""
        return self._jobs

    @property
    def running(self) -> bool:
        """Whether the underlying APScheduler is running."""
        return self._scheduler.running

    # --- Public API ---

    def add_job(
        self,
        name: str,
        schedule: str,
        job_type: str | JobType,
        command: str,
        args: dict | None = None,
        output_channel: str = "file",
        enabled: bool = True,
        llm_model: str = "",
    ) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            name=name,
            schedule=schedule,
            job_type=JobType(job_type),
            command=command,
            args=args or {},
            output_channel=output_channel,
            enabled=enabled,
            llm_model=llm_model,
        )
        self._jobs[job.id] = job

        if enabled:
            self._register_with_scheduler(job)

        self._save_jobs()
        return job

    def remove_job(self, job_id: str) -> None:
        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")
        self._unregister_from_scheduler(job_id)
        del self._jobs[job_id]
        self._save_jobs()

    def enable_job(self, job_id: str) -> Job:
        job = self._get_or_raise(job_id)
        if not job.enabled:
            job.enabled = True
            self._register_with_scheduler(job)
            self._save_jobs()
        return job

    def disable_job(self, job_id: str) -> Job:
        job = self._get_or_raise(job_id)
        if job.enabled:
            job.enabled = False
            self._unregister_from_scheduler(job_id)
            self._save_jobs()
        return job

    def list_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> Job:
        return self._get_or_raise(job_id)

    def run_job(self, job_id: str) -> Job:
        """Public wrapper: execute a job immediately and return the updated Job."""
        self._execute_job(job_id)
        return self._get_or_raise(job_id)

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
        self._write_pid_file()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=True)
        self._remove_pid_file()
        _engine_registry.pop(self._engine_id, None)

    def _write_pid_file(self) -> None:
        """Write the current PID to the pid file so CLI can detect the daemon."""
        self._pid_file.write_text(str(os.getpid()))

    def _remove_pid_file(self) -> None:
        """Clean up the pid file on shutdown."""
        try:
            self._pid_file.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def daemon_status(data_dir: Path | None = None) -> dict:
        """Check whether the cron daemon is running (via PID file).

        Returns a dict with keys: running (bool), pid (int|None).
        """
        if data_dir is None:
            from superpowers.config import get_data_dir

            data_dir = get_data_dir() / "cron"
        pid_file = data_dir / CronEngine.PID_FILENAME

        if not pid_file.exists():
            return {"running": False, "pid": None}

        try:
            pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return {"running": False, "pid": None}

        # Check if process is actually alive
        try:
            os.kill(pid, 0)  # signal 0: existence check only
            return {"running": True, "pid": pid}
        except (ProcessLookupError, PermissionError):
            # Stale PID file — process no longer running
            try:
                pid_file.unlink(missing_ok=True)
            except OSError:
                pass
            return {"running": False, "pid": None}

    # --- Execution ---

    def _job_env(self, job: Job) -> dict[str, str]:
        """Build environment dict for a job subprocess.

        Sets ``LLM_MODEL`` from the per-job override, falling back to the
        global ``JOB_MODEL`` config (which itself defaults to ``"claude"``).
        """
        env = dict(os.environ)
        model = job.llm_model or os.environ.get("JOB_MODEL", "claude")
        env["LLM_MODEL"] = model
        return env

    def _execute_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return

        output = ""
        exit_code = -1

        try:
            if job.job_type == JobType.shell:
                output, exit_code = self._run_shell(job)
            elif job.job_type == JobType.claude:
                output, exit_code = self._run_claude(job)
            elif job.job_type == JobType.webhook:
                output, exit_code = self._run_webhook(job)
            elif job.job_type == JobType.skill:
                output, exit_code = self._run_skill(job)
        except (subprocess.SubprocessError, OSError, RuntimeError, KeyError, ValueError) as exc:
            output = f"Exception: {exc}"
            exit_code = 1

        job.last_run = datetime.now(UTC).isoformat()
        job.last_status = "ok" if exit_code == 0 else f"error({exit_code})"

        self._route_output(job, output, exit_code)
        self._save_jobs()

    def _run_shell(self, job: Job) -> tuple[str, int]:
        env = self._job_env(job)
        env.update({f"JOB_{k.upper()}": str(v) for k, v in job.args.items()})
        result = subprocess.run(
            shlex.split(job.command),
            shell=False,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        return result.stdout + result.stderr, result.returncode

    def _run_claude(self, job: Job) -> tuple[str, int]:
        from superpowers.llm_provider import get_default_provider

        provider = get_default_provider(role="job")
        try:
            output = provider.invoke(job.command)
            return output, 0
        except (RuntimeError, FileNotFoundError) as exc:
            return str(exc), 1

    def _run_webhook(self, job: Job) -> tuple[str, int]:
        import urllib.error
        import urllib.request

        data = json.dumps(job.args).encode() if job.args else b"{}"
        req = urllib.request.Request(
            job.command,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
                return body, 0
        except urllib.error.URLError as exc:
            return str(exc), 1

    def _run_skill(self, job: Job) -> tuple[str, int]:
        from superpowers.skill_loader import SkillLoader
        from superpowers.skill_registry import SkillRegistry

        registry = SkillRegistry()
        loader = SkillLoader()
        skill = registry.get(job.command)
        result = loader.run(skill, job.args or None)
        return result.stdout + result.stderr, result.returncode

    # --- Output routing ---

    def _route_output(self, job: Job, output: str, exit_code: int) -> None:
        job_output_dir = self._output_dir / job.id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        log_file = job_output_dir / f"{ts}.log"
        log_file.write_text(f"exit_code: {exit_code}\ntimestamp: {ts}\n---\n{output}\n")
        job.last_output_file = str(log_file)

        if job.output_channel != "file":
            self._send_to_channel(job, output, exit_code)

    def _send_to_channel(self, job: Job, output: str, exit_code: int) -> None:
        """Dispatch job output to a messaging channel or profile."""
        from superpowers.channels.base import ChannelError
        from superpowers.channels.registry import ChannelRegistry
        from superpowers.config import Settings
        from superpowers.profiles import ProfileManager

        status = "OK" if exit_code == 0 else f"FAILED({exit_code})"
        message = f"[cron] {job.name} — {status}\n{output[:2000]}"

        try:
            settings = Settings.load()
            registry = ChannelRegistry(settings)
            spec = job.output_channel

            # Format: "channel:#target" (direct) or "profile_name" (profile)
            if ":" in spec:
                channel_name, target = spec.split(":", 1)
                ch = registry.get(channel_name)
                ch.send(target, message)
            else:
                pm = ProfileManager(registry)
                pm.send(spec, message)
        except (ChannelError, KeyError):
            # Messaging failure should not break the cron job
            pass

    # --- Persistence ---

    def _load_jobs(self) -> None:
        if not self._jobs_file.exists():
            self._jobs = {}
            return

        try:
            data = json.loads(self._jobs_file.read_text())
        except (json.JSONDecodeError, OSError):
            self._jobs = {}
            return

        self._jobs = {}
        for raw in data:
            job = Job.from_dict(raw)
            self._jobs[job.id] = job

    def _save_jobs(self) -> None:
        self._jobs_file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            [j.to_dict() for j in self._jobs.values()],
            indent=2,
        )
        # Atomic write: tmp file + rename
        fd, tmp_path = tempfile.mkstemp(
            dir=self._jobs_file.parent,
            prefix=".jobs_",
            suffix=".tmp",
        )
        try:
            os.write(fd, payload.encode())
            os.close(fd)
            os.replace(tmp_path, self._jobs_file)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # --- Scheduler helpers ---

    def _register_with_scheduler(self, job: Job) -> None:
        trigger = parse_schedule(job.schedule)
        self._scheduler.add_job(
            _dispatch_job,
            trigger=trigger,
            id=job.id,
            args=[self._engine_id, job.id],
            replace_existing=True,
            name=job.name,
        )

    def _unregister_from_scheduler(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except (KeyError, OSError):
            pass

    def _get_or_raise(self, job_id: str) -> Job:
        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")
        return self._jobs[job_id]
