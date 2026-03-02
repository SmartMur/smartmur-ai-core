"""Tests for credential rotation alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from superpowers.credential_rotation import (
    AlertStatus,
    CredentialRotationChecker,
    RotationPolicy,
    run_rotation_check,
)


@pytest.fixture
def checker(tmp_path):
    return CredentialRotationChecker(policies_path=tmp_path / "policies.yaml")


class TestRotationPolicy:
    def test_defaults(self):
        p = RotationPolicy()
        assert p.max_age_days == 90
        assert p.last_rotated == ""
        assert p.last_rotated_dt is None

    def test_last_rotated_dt_parses(self):
        p = RotationPolicy(last_rotated="2025-01-15T00:00:00+00:00")
        assert p.last_rotated_dt == datetime(2025, 1, 15, tzinfo=UTC)


class TestCredentialRotationChecker:
    def test_get_policy_default(self, checker):
        policy = checker.get_policy("nonexistent")
        assert policy.max_age_days == 90
        assert policy.last_rotated == ""

    def test_set_policy(self, checker):
        checker.set_policy("my-api-key", 30)
        policy = checker.get_policy("my-api-key")
        assert policy.max_age_days == 30

    def test_set_policy_preserves_last_rotated(self, checker):
        checker.mark_rotated("my-key", datetime(2025, 6, 1, tzinfo=UTC))
        checker.set_policy("my-key", 60)
        policy = checker.get_policy("my-key")
        assert policy.max_age_days == 60
        assert "2025-06-01" in policy.last_rotated

    def test_mark_rotated(self, checker):
        when = datetime(2025, 3, 1, tzinfo=UTC)
        checker.mark_rotated("db-pass", when)
        policy = checker.get_policy("db-pass")
        assert policy.last_rotated_dt == when

    def test_persistence(self, tmp_path):
        path = tmp_path / "policies.yaml"
        c1 = CredentialRotationChecker(policies_path=path)
        c1.set_policy("key1", 45)
        c1.mark_rotated("key1", datetime(2025, 1, 1, tzinfo=UTC))

        c2 = CredentialRotationChecker(policies_path=path)
        policy = c2.get_policy("key1")
        assert policy.max_age_days == 45
        assert "2025-01-01" in policy.last_rotated

    def test_check_key_ok(self, checker):
        now = datetime(2025, 6, 1, tzinfo=UTC)
        checker.mark_rotated("key1", datetime(2025, 5, 25, tzinfo=UTC))
        alert = checker.check_key("key1", now)
        assert alert.status == AlertStatus.ok
        assert alert.age_days == 7
        assert alert.max_age_days == 90

    def test_check_key_warning(self, checker):
        now = datetime(2025, 6, 1, tzinfo=UTC)
        # 80 days old, threshold is 72 days (80% of 90)
        checker.mark_rotated("key1", now - timedelta(days=80))
        alert = checker.check_key("key1", now)
        assert alert.status == AlertStatus.warning
        assert alert.age_days == 80

    def test_check_key_expired(self, checker):
        now = datetime(2025, 6, 1, tzinfo=UTC)
        checker.mark_rotated("key1", now - timedelta(days=100))
        alert = checker.check_key("key1", now)
        assert alert.status == AlertStatus.expired
        assert alert.age_days == 100

    def test_check_key_no_rotation_date(self, checker):
        alert = checker.check_key("unknown-key")
        assert alert.status == AlertStatus.expired
        assert alert.age_days == -1

    def test_check_key_custom_policy(self, checker):
        now = datetime(2025, 6, 1, tzinfo=UTC)
        checker.set_policy("short-lived", 7)
        checker.mark_rotated("short-lived", now - timedelta(days=4))
        # 4 days old, warning threshold is int(7*0.8)=5 days -> ok at day 4
        alert = checker.check_key("short-lived", now)
        assert alert.status == AlertStatus.ok

    def test_check_key_custom_policy_expired(self, checker):
        now = datetime(2025, 6, 1, tzinfo=UTC)
        checker.set_policy("short-lived", 7)
        checker.mark_rotated("short-lived", now - timedelta(days=8))
        alert = checker.check_key("short-lived", now)
        assert alert.status == AlertStatus.expired

    def test_check_all(self, checker):
        now = datetime(2025, 6, 1, tzinfo=UTC)
        checker.mark_rotated("key-a", now - timedelta(days=10))
        checker.mark_rotated("key-b", now - timedelta(days=95))

        alerts = checker.check_all(["key-a", "key-b"], now)
        assert len(alerts) == 2
        assert alerts[0].key == "key-a"
        assert alerts[0].status == AlertStatus.ok
        assert alerts[1].key == "key-b"
        assert alerts[1].status == AlertStatus.expired

    def test_check_all_sorted(self, checker):
        now = datetime(2025, 6, 1, tzinfo=UTC)
        alerts = checker.check_all(["z-key", "a-key"], now)
        assert alerts[0].key == "a-key"
        assert alerts[1].key == "z-key"

    def test_list_policies(self, checker):
        checker.set_policy("k1", 30)
        checker.set_policy("k2", 60)
        policies = checker.list_policies()
        assert len(policies) == 2
        assert policies["k1"].max_age_days == 30
        assert policies["k2"].max_age_days == 60

    def test_load_corrupt_yaml(self, tmp_path):
        path = tmp_path / "policies.yaml"
        path.write_text(":::: not valid yaml [[[")
        checker = CredentialRotationChecker(policies_path=path)
        assert checker.list_policies() == {}

    def test_load_missing_file(self, tmp_path):
        checker = CredentialRotationChecker(policies_path=tmp_path / "nope.yaml")
        assert checker.list_policies() == {}


class TestRunRotationCheck:
    def test_sends_alert_on_expired(self, tmp_path):
        policies_path = tmp_path / "policies.yaml"
        checker = CredentialRotationChecker(policies_path=policies_path)
        now = datetime(2025, 6, 1, tzinfo=UTC)
        checker.mark_rotated("old-key", now - timedelta(days=100))

        vault = MagicMock()
        vault.list_keys.return_value = ["old-key"]

        pm = MagicMock()
        pm.send.return_value = []

        settings = MagicMock()
        settings.data_dir = tmp_path

        alerts = run_rotation_check(
            settings,
            profile="critical",
            vault=vault,
            checker=checker,
            profile_manager=pm,
            now=now,
        )

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.expired
        pm.send.assert_called_once()
        call_args = pm.send.call_args
        assert call_args[0][0] == "critical"
        assert "old-key" in call_args[0][1]

    def test_no_alert_when_all_ok(self, tmp_path):
        policies_path = tmp_path / "policies.yaml"
        checker = CredentialRotationChecker(policies_path=policies_path)
        now = datetime(2025, 6, 1, tzinfo=UTC)
        checker.mark_rotated("fresh-key", now - timedelta(days=1))

        vault = MagicMock()
        vault.list_keys.return_value = ["fresh-key"]

        pm = MagicMock()
        settings = MagicMock()
        settings.data_dir = tmp_path

        alerts = run_rotation_check(
            settings,
            vault=vault,
            checker=checker,
            profile_manager=pm,
            now=now,
        )

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.ok
        pm.send.assert_not_called()

    def test_empty_vault(self, tmp_path):
        policies_path = tmp_path / "policies.yaml"
        checker = CredentialRotationChecker(policies_path=policies_path)

        vault = MagicMock()
        vault.list_keys.return_value = []

        pm = MagicMock()
        settings = MagicMock()
        settings.data_dir = tmp_path

        alerts = run_rotation_check(
            settings,
            vault=vault,
            checker=checker,
            profile_manager=pm,
        )

        assert alerts == []
        pm.send.assert_not_called()
