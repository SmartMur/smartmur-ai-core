from __future__ import annotations

import json
from pathlib import Path

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from superpowers.cron_engine import CronEngine, Job, JobType, parse_schedule

# --- parse_schedule tests ---


class TestParseSchedule:
    def test_every_minutes(self):
        t = parse_schedule("every 30m")
        assert isinstance(t, IntervalTrigger)
        assert t.interval.total_seconds() == 30 * 60

    def test_every_hours(self):
        t = parse_schedule("every 6h")
        assert isinstance(t, IntervalTrigger)
        assert t.interval.total_seconds() == 6 * 3600

    def test_every_days(self):
        t = parse_schedule("every 1d")
        assert isinstance(t, IntervalTrigger)
        assert t.interval.total_seconds() == 86400

    def test_daily_at(self):
        t = parse_schedule("daily at 09:00")
        assert isinstance(t, CronTrigger)

    def test_daily_at_afternoon(self):
        t = parse_schedule("daily at 14:30")
        assert isinstance(t, CronTrigger)

    def test_cron_expression(self):
        t = parse_schedule("0 */6 * * *")
        assert isinstance(t, CronTrigger)

    def test_cron_every_minute(self):
        t = parse_schedule("* * * * *")
        assert isinstance(t, CronTrigger)

    def test_invalid_expression(self):
        with pytest.raises(ValueError, match="Unrecognised"):
            parse_schedule("whenever you feel like it")

    def test_whitespace_stripped(self):
        t = parse_schedule("  every 5m  ")
        assert isinstance(t, IntervalTrigger)


# --- Job dataclass tests ---


class TestJobDataclass:
    def test_auto_id(self):
        j = Job(id="", name="test", schedule="every 1h", job_type=JobType.shell, command="echo hi")
        assert j.id  # uuid was generated
        assert len(j.id) == 36

    def test_auto_created_at(self):
        j = Job(id="", name="test", schedule="every 1h", job_type="shell", command="echo hi")
        assert j.created_at
        assert j.job_type == JobType.shell

    def test_roundtrip(self):
        j = Job(id="abc-123", name="test", schedule="every 1h", job_type=JobType.claude, command="summarize")
        d = j.to_dict()
        j2 = Job.from_dict(d)
        assert j2.id == j.id
        assert j2.job_type == JobType.claude


# --- CronEngine tests ---


@pytest.fixture
def engine(tmp_path: Path):
    jobs_file = tmp_path / "cron" / "jobs.json"
    e = CronEngine(jobs_file=jobs_file, data_dir=tmp_path / "cron")
    e.start()
    yield e
    e.stop()


class TestCronEngineAddRemoveList:
    def test_add_job(self, engine: CronEngine):
        job = engine.add_job("hello", "every 1h", "shell", "echo hello")
        assert job.name == "hello"
        assert job.job_type == JobType.shell
        assert job.enabled is True
        assert len(engine.list_jobs()) == 1

    def test_add_multiple(self, engine: CronEngine):
        engine.add_job("a", "every 1h", "shell", "echo a")
        engine.add_job("b", "every 2h", "shell", "echo b")
        assert len(engine.list_jobs()) == 2

    def test_get_job(self, engine: CronEngine):
        job = engine.add_job("x", "every 30m", "shell", "pwd")
        fetched = engine.get_job(job.id)
        assert fetched.name == "x"

    def test_get_job_missing(self, engine: CronEngine):
        with pytest.raises(KeyError):
            engine.get_job("nonexistent")

    def test_remove_job(self, engine: CronEngine):
        job = engine.add_job("rm", "every 1h", "shell", "true")
        engine.remove_job(job.id)
        assert len(engine.list_jobs()) == 0

    def test_remove_missing(self, engine: CronEngine):
        with pytest.raises(KeyError):
            engine.remove_job("nope")


class TestCronEngineEnableDisable:
    def test_disable(self, engine: CronEngine):
        job = engine.add_job("tog", "every 1h", "shell", "echo tog")
        engine.disable_job(job.id)
        assert engine.get_job(job.id).enabled is False

    def test_enable(self, engine: CronEngine):
        job = engine.add_job("tog2", "every 1h", "shell", "echo tog2")
        engine.disable_job(job.id)
        engine.enable_job(job.id)
        assert engine.get_job(job.id).enabled is True

    def test_disable_idempotent(self, engine: CronEngine):
        job = engine.add_job("idem", "every 1h", "shell", "echo hi")
        engine.disable_job(job.id)
        engine.disable_job(job.id)  # should not raise
        assert engine.get_job(job.id).enabled is False

    def test_enable_idempotent(self, engine: CronEngine):
        job = engine.add_job("idem2", "every 1h", "shell", "echo hi")
        engine.enable_job(job.id)  # already enabled
        assert engine.get_job(job.id).enabled is True


class TestCronEnginePersistence:
    def test_save_and_reload(self, tmp_path: Path):
        jobs_file = tmp_path / "cron" / "jobs.json"

        e1 = CronEngine(jobs_file=jobs_file, data_dir=tmp_path / "cron")
        e1.start()
        j = e1.add_job("persist", "every 2h", "shell", "date")
        e1.add_job("persist2", "daily at 08:00", "claude", "summarize news")
        e1.disable_job(j.id)
        e1.stop()

        # Reload from disk
        e2 = CronEngine(jobs_file=jobs_file, data_dir=tmp_path / "cron")
        jobs = e2.list_jobs()
        assert len(jobs) == 2

        reloaded = e2.get_job(j.id)
        assert reloaded.name == "persist"
        assert reloaded.enabled is False
        assert reloaded.job_type == JobType.shell

        enabled_jobs = [j for j in jobs if j.enabled]
        assert len(enabled_jobs) == 1
        assert enabled_jobs[0].job_type == JobType.claude
        e2.stop()

    def test_jobs_json_is_valid(self, engine: CronEngine, tmp_path: Path):
        engine.add_job("jsontest", "every 1h", "shell", "echo 1")
        jobs_file = tmp_path / "cron" / "jobs.json"
        data = json.loads(jobs_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "jsontest"


class TestCronEngineExecution:
    def test_shell_execution(self, engine: CronEngine, tmp_path: Path):
        job = engine.add_job("echo-test", "every 1h", "shell", "echo hello-from-cron")
        engine._execute_job(job.id)

        updated = engine.get_job(job.id)
        assert updated.last_run != ""
        assert updated.last_status == "ok"
        assert updated.last_output_file != ""

        log_content = Path(updated.last_output_file).read_text()
        assert "hello-from-cron" in log_content
        assert "exit_code: 0" in log_content

    def test_shell_failure(self, engine: CronEngine):
        job = engine.add_job("fail", "every 1h", "shell", "exit 42")
        engine._execute_job(job.id)
        assert "error" in engine.get_job(job.id).last_status

    def test_output_file_structure(self, engine: CronEngine, tmp_path: Path):
        job = engine.add_job("outtest", "every 1h", "shell", "echo structured")
        engine._execute_job(job.id)

        output_dir = tmp_path / "cron" / "output" / job.id
        assert output_dir.exists()
        logs = list(output_dir.glob("*.log"))
        assert len(logs) == 1

    def test_disabled_job_not_registered(self, engine: CronEngine):
        job = engine.add_job(
            "disabled-add", "every 1h", "shell", "echo nope", enabled=False
        )
        # The job should exist in our registry but not in APScheduler
        assert engine.get_job(job.id).enabled is False
        scheduler_job = engine._scheduler.get_job(job.id)
        assert scheduler_job is None
