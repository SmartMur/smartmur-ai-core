"""Tests for CLI ssh subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_ssh import ssh_group
from superpowers.ssh_fabric.base import AuthMethod, SSHError


def _make_host(alias="host1", hostname="192.168.1.1", port=22, username="ray", groups=None):
    host = MagicMock()
    host.alias = alias
    host.hostname = hostname
    host.port = port
    host.username = username
    host.auth = AuthMethod.key
    host.groups = groups or ["all"]
    return host


def _make_result(host="host1", ok=True, exit_code=0, stdout="output", stderr="", error=""):
    r = MagicMock()
    r.host = host
    r.ok = ok
    r.exit_code = exit_code
    r.stdout = stdout
    r.stderr = stderr
    r.error = error
    return r


# --- ssh hosts ---


@patch("superpowers.cli_ssh.HostRegistry")
def test_ssh_hosts_with_hosts(mock_cls):
    registry = MagicMock()
    registry.list_hosts.return_value = [
        _make_host("proxmox", "10.0.0.1"),
        _make_host("nas", "10.0.0.2", port=2222),
    ]
    mock_cls.return_value = registry
    runner = CliRunner()
    result = runner.invoke(ssh_group, ["hosts"])
    assert result.exit_code == 0
    assert "proxmox" in result.output
    assert "nas" in result.output
    assert "2222" in result.output


@patch("superpowers.cli_ssh.HostRegistry")
def test_ssh_hosts_empty(mock_cls):
    registry = MagicMock()
    registry.list_hosts.return_value = []
    mock_cls.return_value = registry
    runner = CliRunner()
    result = runner.invoke(ssh_group, ["hosts"])
    assert result.exit_code == 0
    assert "No hosts configured" in result.output


# --- ssh run ---


@patch("superpowers.cli_ssh._build_stack")
def test_ssh_run_success(mock_build):
    hosts = MagicMock()
    pool = MagicMock()
    pool.__enter__ = MagicMock(return_value=pool)
    pool.__exit__ = MagicMock(return_value=False)
    executor = MagicMock()
    executor.run.return_value = [_make_result()]
    mock_build.return_value = (hosts, pool, executor)

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["run", "host1", "uptime"])
    assert result.exit_code == 0
    assert "output" in result.output


@patch("superpowers.cli_ssh._build_stack")
def test_ssh_run_failure(mock_build):
    hosts = MagicMock()
    pool = MagicMock()
    pool.__enter__ = MagicMock(return_value=pool)
    pool.__exit__ = MagicMock(return_value=False)
    executor = MagicMock()
    executor.run.return_value = [_make_result(ok=False, exit_code=1, stderr="cmd error")]
    mock_build.return_value = (hosts, pool, executor)

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["run", "host1", "bad-cmd"])
    assert result.exit_code != 0


@patch("superpowers.cli_ssh._build_stack")
def test_ssh_run_bad_target(mock_build):
    hosts = MagicMock()
    hosts.resolve.side_effect = SSHError("unknown host 'xyz'")
    pool = MagicMock()
    executor = MagicMock()
    mock_build.return_value = (hosts, pool, executor)

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["run", "xyz", "echo hi"])
    assert result.exit_code != 0
    assert "unknown host" in result.output


@patch("superpowers.cli_ssh._build_stack")
def test_ssh_run_multiple_results(mock_build):
    hosts = MagicMock()
    pool = MagicMock()
    pool.__enter__ = MagicMock(return_value=pool)
    pool.__exit__ = MagicMock(return_value=False)
    executor = MagicMock()
    executor.run.return_value = [
        _make_result(host="h1", stdout="ok1"),
        _make_result(host="h2", stdout="ok2"),
    ]
    mock_build.return_value = (hosts, pool, executor)

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["run", "all", "uptime"])
    assert result.exit_code == 0
    assert "h1" in result.output
    assert "h2" in result.output


# --- ssh test ---


@patch("superpowers.cli_ssh._build_stack")
def test_ssh_test_pass(mock_build):
    hosts = MagicMock()
    pool = MagicMock()
    pool.__enter__ = MagicMock(return_value=pool)
    pool.__exit__ = MagicMock(return_value=False)
    executor = MagicMock()
    executor.run.return_value = [_make_result(stdout="ok")]
    mock_build.return_value = (hosts, pool, executor)

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["test", "host1"])
    assert result.exit_code == 0
    assert "PASS" in result.output
    assert "All hosts passed" in result.output


@patch("superpowers.cli_ssh._build_stack")
def test_ssh_test_fail(mock_build):
    hosts = MagicMock()
    pool = MagicMock()
    pool.__enter__ = MagicMock(return_value=pool)
    pool.__exit__ = MagicMock(return_value=False)
    executor = MagicMock()
    executor.run.return_value = [_make_result(ok=False, exit_code=1, error="timeout")]
    mock_build.return_value = (hosts, pool, executor)

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["test", "host1"])
    assert result.exit_code != 0
    assert "FAIL" in result.output


# --- ssh health ---


@patch("superpowers.cli_ssh._build_stack")
@patch("superpowers.cli_ssh.HealthChecker")
def test_ssh_health_all_ok(mock_checker_cls, mock_build):
    hosts = MagicMock()
    pool = MagicMock()
    pool.__enter__ = MagicMock(return_value=pool)
    pool.__exit__ = MagicMock(return_value=False)
    executor = MagicMock()
    mock_build.return_value = (hosts, pool, executor)

    host_report = MagicMock()
    host_report.alias = "h1"
    host_report.ping_ok = True
    host_report.ssh_ok = True
    host_report.latency_ms = 5.2
    host_report.load_avg = "0.5 0.3 0.1"
    host_report.error = None

    report = MagicMock()
    report.hosts = [host_report]
    report.all_ok = True

    checker = MagicMock()
    checker.check_all.return_value = report
    checker._output_path = "/tmp/health.json"
    mock_checker_cls.return_value = checker

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["health"])
    assert result.exit_code == 0
    assert "h1" in result.output


@patch("superpowers.cli_ssh._build_stack")
@patch("superpowers.cli_ssh.HealthChecker")
def test_ssh_health_with_failures(mock_checker_cls, mock_build):
    hosts = MagicMock()
    pool = MagicMock()
    pool.__enter__ = MagicMock(return_value=pool)
    pool.__exit__ = MagicMock(return_value=False)
    executor = MagicMock()
    mock_build.return_value = (hosts, pool, executor)

    host_report = MagicMock()
    host_report.alias = "h1"
    host_report.ping_ok = False
    host_report.ssh_ok = False
    host_report.latency_ms = 0.0
    host_report.load_avg = None
    host_report.error = "host unreachable"

    report = MagicMock()
    report.hosts = [host_report]
    report.all_ok = False

    checker = MagicMock()
    checker.check_all.return_value = report
    checker._output_path = "/tmp/health.json"
    mock_checker_cls.return_value = checker

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["health"])
    assert result.exit_code != 0


# --- ha state ---


@patch("superpowers.cli_ssh._ha_client")
def test_ha_state_found(mock_client_fn):
    client = MagicMock()
    client.get_state.return_value = {
        "state": "on",
        "attributes": {"brightness": 255, "friendly_name": "Office Light"},
    }
    mock_client_fn.return_value = client

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["ha", "state", "light.office"])
    assert result.exit_code == 0
    assert "on" in result.output
    assert "brightness" in result.output


@patch("superpowers.cli_ssh._ha_client")
def test_ha_state_not_found(mock_client_fn):
    client = MagicMock()
    client.get_state.return_value = None
    mock_client_fn.return_value = client

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["ha", "state", "light.missing"])
    assert result.exit_code != 0
    assert "Entity not found" in result.output


@patch("superpowers.cli_ssh._ha_client")
def test_ha_state_error(mock_client_fn):
    mock_client_fn.side_effect = SSHError("HA not configured")

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["ha", "state", "light.x"])
    assert result.exit_code != 0
    assert "HA not configured" in result.output


# --- ha call ---


@patch("superpowers.cli_ssh._ha_client")
def test_ha_call_success(mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["ha", "call", "light", "turn_on", "light.office"])
    assert result.exit_code == 0
    assert "OK" in result.output
    client.call_service.assert_called_once_with("light", "turn_on", "light.office")


# --- ha list ---


@patch("superpowers.cli_ssh._ha_client")
def test_ha_list_entities(mock_client_fn):
    client = MagicMock()
    client.get_states.return_value = [
        {"entity_id": "light.office", "state": "on", "attributes": {"friendly_name": "Office"}},
        {"entity_id": "switch.fan", "state": "off", "attributes": {"friendly_name": "Fan"}},
    ]
    mock_client_fn.return_value = client

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["ha", "list"])
    assert result.exit_code == 0
    assert "light.office" in result.output
    assert "switch.fan" in result.output
    assert "2 entities" in result.output


@patch("superpowers.cli_ssh._ha_client")
def test_ha_list_with_filter(mock_client_fn):
    client = MagicMock()
    client.get_states.return_value = [
        {"entity_id": "light.office", "state": "on", "attributes": {"friendly_name": "Office"}},
        {"entity_id": "switch.fan", "state": "off", "attributes": {"friendly_name": "Fan"}},
    ]
    mock_client_fn.return_value = client

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["ha", "list", "-f", "light"])
    assert result.exit_code == 0
    assert "light.office" in result.output
    # switch.fan should be filtered out
    assert "1 entities" in result.output


@patch("superpowers.cli_ssh._ha_client")
def test_ha_list_empty(mock_client_fn):
    client = MagicMock()
    client.get_states.return_value = []
    mock_client_fn.return_value = client

    runner = CliRunner()
    result = runner.invoke(ssh_group, ["ha", "list"])
    assert result.exit_code == 0
    assert "No entities found" in result.output
