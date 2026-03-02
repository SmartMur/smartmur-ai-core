"""Host health checker — ping and SSH probes with JSON reporting."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from superpowers.config import get_data_dir
from superpowers.ssh_fabric.base import CommandResult
from superpowers.ssh_fabric.executor import SSHExecutor
from superpowers.ssh_fabric.hosts import HostRegistry

DEFAULT_OUTPUT = get_data_dir() / "ssh" / "health.json"


@dataclass
class HostStatus:
    alias: str
    hostname: str
    ping_ok: bool
    ssh_ok: bool
    uptime: str = ""
    load_avg: str = ""
    latency_ms: float = 0.0
    error: str = ""


@dataclass
class HealthReport:
    timestamp: float
    hosts: list[HostStatus] = field(default_factory=list)
    all_ok: bool = True

    def __post_init__(self):
        self.all_ok = all(h.ping_ok and h.ssh_ok for h in self.hosts)


class HealthChecker:
    def __init__(
        self,
        hosts: HostRegistry,
        executor: SSHExecutor,
        output_path: Path | None = None,
    ):
        self._hosts = hosts
        self._executor = executor
        self._output_path = output_path or DEFAULT_OUTPUT

    def check_all(self) -> HealthReport:
        statuses: list[HostStatus] = []

        for host in self._hosts.list_hosts():
            ping_ok, latency = self._ping(host.hostname)

            uptime = ""
            load_avg = ""
            ssh_ok = False
            error = ""

            results = self._executor.run(host.alias, "uptime", timeout=10)
            if results:
                r: CommandResult = results[0]
                if r.ok:
                    ssh_ok = True
                    uptime = r.stdout.strip()
                    # Parse load average from uptime output
                    if "load average:" in uptime:
                        load_avg = uptime.split("load average:")[-1].strip()
                else:
                    error = r.error or r.stderr

            statuses.append(
                HostStatus(
                    alias=host.alias,
                    hostname=host.hostname,
                    ping_ok=ping_ok,
                    ssh_ok=ssh_ok,
                    uptime=uptime,
                    load_avg=load_avg,
                    latency_ms=latency,
                    error=error,
                )
            )

        report = HealthReport(timestamp=time.time(), hosts=statuses)
        return report

    def write_json(self, report: HealthReport) -> None:
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "timestamp": report.timestamp,
            "all_ok": report.all_ok,
            "hosts": [
                {
                    "alias": h.alias,
                    "hostname": h.hostname,
                    "ping_ok": h.ping_ok,
                    "ssh_ok": h.ssh_ok,
                    "uptime": h.uptime,
                    "load_avg": h.load_avg,
                    "latency_ms": h.latency_ms,
                    "error": h.error,
                }
                for h in report.hosts
            ],
        }

        fd, tmp_path = tempfile.mkstemp(
            dir=self._output_path.parent,
            prefix=".health-",
            suffix=".tmp",
        )
        try:
            os.write(fd, json.dumps(payload, indent=2).encode())
            os.close(fd)
            os.replace(tmp_path, self._output_path)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    @staticmethod
    def _ping(hostname: str) -> tuple[bool, float]:
        start = time.time()
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", hostname],
                capture_output=True,
                timeout=5,
            )
            elapsed = (time.time() - start) * 1000
            return result.returncode == 0, round(elapsed, 1)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            elapsed = (time.time() - start) * 1000
            return False, round(elapsed, 1)
