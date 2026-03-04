"""Tests for the SSH fabric module."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from superpowers.ssh_fabric.base import AuthMethod, CommandResult, HostConfig, SSHError
from superpowers.ssh_fabric.executor import SSHExecutor
from superpowers.ssh_fabric.health import HealthChecker, HealthReport, HostStatus
from superpowers.ssh_fabric.homeassistant import HomeAssistantClient
from superpowers.ssh_fabric.hosts import HostRegistry
from superpowers.ssh_fabric.pool import ConnectionPool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

HOSTS_YAML = """\
hosts:
  - alias: proxmox
    hostname: 192.168.30.10
    port: 22
    username: root
    auth: key
    key_file: ~/.ssh/id_ed25519
    groups:
      - servers
      - hypervisors
    tags:
      role: hypervisor
  - alias: truenas
    hostname: 192.168.13.69
    username: ray
    auth: password
    groups:
      - storage
  - alias: pihole
    hostname: 192.168.30.53
    auth: agent
    groups:
      - dns
"""


@pytest.fixture
def hosts_yaml(tmp_path):
    path = tmp_path / "hosts.yaml"
    path.write_text(HOSTS_YAML)
    return path


@pytest.fixture
def registry(hosts_yaml):
    return HostRegistry(hosts_path=hosts_yaml)


def _mock_paramiko():
    """Return a mock paramiko module with SSHClient and exceptions."""
    mock_mod = MagicMock()
    mock_client_instance = MagicMock()
    mock_mod.SSHClient.return_value = mock_client_instance
    mock_mod.AutoAddPolicy.return_value = "auto-add"
    mock_mod.RejectPolicy.return_value = "reject"

    transport = MagicMock()
    transport.is_active.return_value = True
    mock_client_instance.get_transport.return_value = transport

    mock_mod.AuthenticationException = type("AuthenticationException", (Exception,), {})
    mock_mod.SSHException = type("SSHException", (Exception,), {})

    return mock_mod, mock_client_instance


# ---------------------------------------------------------------------------
# TestAuthMethod
# ---------------------------------------------------------------------------


class TestAuthMethod:
    def test_key_value(self):
        assert AuthMethod.key == "key"

    def test_password_value(self):
        assert AuthMethod.password == "password"

    def test_agent_value(self):
        assert AuthMethod.agent == "agent"

    def test_all_members(self):
        assert len(AuthMethod) == 3


# ---------------------------------------------------------------------------
# TestHostConfig
# ---------------------------------------------------------------------------


class TestHostConfig:
    def test_defaults(self):
        h = HostConfig(alias="test", hostname="1.2.3.4")
        assert h.port == 22
        assert h.username == "root"
        assert h.auth == AuthMethod.key
        assert h.groups == ["all"]
        assert h.key_file == ""
        assert h.tags == {}

    def test_custom_values(self):
        h = HostConfig(
            alias="nas",
            hostname="10.0.0.5",
            port=2222,
            username="admin",
            auth=AuthMethod.password,
            key_file="/path/to/key",
            groups=["storage", "backup"],
            tags={"dc": "us-east"},
        )
        assert h.alias == "nas"
        assert h.hostname == "10.0.0.5"
        assert h.port == 2222
        assert h.username == "admin"
        assert h.auth == AuthMethod.password
        assert h.key_file == "/path/to/key"
        assert h.groups == ["storage", "backup"]
        assert h.tags == {"dc": "us-east"}


# ---------------------------------------------------------------------------
# TestCommandResult
# ---------------------------------------------------------------------------


class TestCommandResult:
    def test_ok_when_exit_zero_no_error(self):
        r = CommandResult(host="h", command="ls", stdout="out", stderr="", exit_code=0)
        assert r.ok is True

    def test_not_ok_when_exit_nonzero(self):
        r = CommandResult(host="h", command="ls", stdout="", stderr="err", exit_code=1)
        assert r.ok is False

    def test_not_ok_when_error_set(self):
        r = CommandResult(host="h", command="ls", stdout="", stderr="", exit_code=0, error="boom")
        assert r.ok is False

    def test_not_ok_when_both_bad(self):
        r = CommandResult(
            host="h", command="ls", stdout="", stderr="err", exit_code=127, error="nope"
        )
        assert r.ok is False


# ---------------------------------------------------------------------------
# TestHostRegistry
# ---------------------------------------------------------------------------


class TestHostRegistry:
    def test_load_valid_hosts(self, registry):
        hosts = registry.list_hosts()
        assert len(hosts) == 3
        aliases = {h.alias for h in hosts}
        assert aliases == {"proxmox", "truenas", "pihole"}

    def test_missing_file_returns_empty(self, tmp_path):
        reg = HostRegistry(hosts_path=tmp_path / "nonexistent.yaml")
        assert reg.list_hosts() == []

    def test_corrupt_yaml_returns_empty(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{{not valid yaml!!!")
        reg = HostRegistry(hosts_path=bad)
        assert reg.list_hosts() == []

    def test_get_returns_correct_host(self, registry):
        h = registry.get("proxmox")
        assert h.hostname == "192.168.30.10"
        assert h.username == "root"
        assert h.auth == AuthMethod.key

    def test_get_unknown_raises(self, registry):
        with pytest.raises(SSHError, match="Host not found"):
            registry.get("nonexistent")

    def test_resolve_by_alias(self, registry):
        result = registry.resolve("truenas")
        assert len(result) == 1
        assert result[0].alias == "truenas"

    def test_resolve_by_group(self, registry):
        result = registry.resolve("servers")
        assert len(result) == 1
        assert result[0].alias == "proxmox"

    def test_resolve_all(self, registry):
        result = registry.resolve("all")
        assert len(result) == 3

    def test_resolve_unknown_raises(self, registry):
        with pytest.raises(SSHError, match="No hosts or groups match"):
            registry.resolve("ghosts")

    def test_list_hosts(self, registry):
        assert len(registry.list_hosts()) == 3

    def test_groups_mapping(self, registry):
        grps = registry.groups()
        assert "all" in grps
        assert len(grps["all"]) == 3
        assert "servers" in grps
        assert grps["servers"] == ["proxmox"]
        assert "storage" in grps
        assert grps["storage"] == ["truenas"]

    def test_all_group_auto_appended(self, registry):
        h = registry.get("truenas")
        assert "all" in h.groups

    def test_host_port_defaults(self, registry):
        h = registry.get("truenas")
        assert h.port == 22

    def test_host_tags_parsed(self, registry):
        h = registry.get("proxmox")
        assert h.tags == {"role": "hypervisor"}


# ---------------------------------------------------------------------------
# TestConnectionPool
# ---------------------------------------------------------------------------


class TestConnectionPool:
    def test_get_client_creates_new(self, registry):
        mock_mod, mock_client = _mock_paramiko()

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry)
            client = pool.get_client("proxmox")

        assert client is mock_client
        mock_mod.SSHClient.assert_called_once()
        mock_client.load_system_host_keys.assert_called_once()
        mock_client.set_missing_host_key_policy.assert_called_with("reject")
        mock_client.connect.assert_called_once()

    def test_get_client_allows_auto_add_policy_when_enabled(self, registry):
        mock_mod, mock_client = _mock_paramiko()

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry, auto_add_host_keys=True)
            pool.get_client("proxmox")

        mock_client.set_missing_host_key_policy.assert_called_with("auto-add")

    def test_get_client_returns_cached(self, registry):
        mock_mod, mock_client = _mock_paramiko()

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry)
            c1 = pool.get_client("proxmox")
            c2 = pool.get_client("proxmox")

        assert c1 is c2
        # connect called only once because second call returns cached
        assert mock_client.connect.call_count == 1

    def test_stale_client_reconnects(self, registry):
        mock_mod, mock_client = _mock_paramiko()
        transport = mock_client.get_transport.return_value
        transport.is_active.return_value = True

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry)
            c1 = pool.get_client("proxmox")  # creates + caches

            # Now mark transport as dead so next call triggers reconnect
            transport.is_active.return_value = False

            # New client for the reconnection
            mock_client2 = MagicMock()
            transport2 = MagicMock()
            transport2.is_active.return_value = True
            mock_client2.get_transport.return_value = transport2
            mock_mod.SSHClient.return_value = mock_client2

            c2 = pool.get_client("proxmox")  # should reconnect

        assert c2 is mock_client2
        assert c2 is not c1
        mock_client2.connect.assert_called_once()

    def test_key_auth_with_key_file(self, registry):
        mock_mod, mock_client = _mock_paramiko()

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry)
            pool.get_client("proxmox")

        call_kwargs = mock_client.connect.call_args[1]
        assert call_kwargs["key_filename"] == "~/.ssh/id_ed25519"
        assert call_kwargs["hostname"] == "192.168.30.10"
        assert call_kwargs["username"] == "root"

    def test_password_auth_fetches_from_vault(self, registry):
        mock_mod, mock_client = _mock_paramiko()
        mock_vault = MagicMock()
        mock_vault.get.return_value = "s3cret"

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry, vault=mock_vault)
            pool.get_client("truenas")

        mock_vault.get.assert_called_with("ssh:truenas:password")
        call_kwargs = mock_client.connect.call_args[1]
        assert call_kwargs["password"] == "s3cret"
        assert call_kwargs["hostname"] == "192.168.13.69"
        assert call_kwargs["username"] == "ray"

    def test_password_auth_requires_vault(self, registry):
        mock_mod, mock_client = _mock_paramiko()

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry, vault=None)
            with pytest.raises(SSHError, match="Vault required"):
                pool.get_client("truenas")

    def test_password_auth_requires_vault_entry(self, registry):
        mock_mod, mock_client = _mock_paramiko()
        mock_vault = MagicMock()
        mock_vault.get.return_value = None

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry, vault=mock_vault)
            with pytest.raises(SSHError, match="No password in vault"):
                pool.get_client("truenas")

    def test_agent_auth_uses_allow_agent(self, registry):
        mock_mod, mock_client = _mock_paramiko()

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry)
            pool.get_client("pihole")

        call_kwargs = mock_client.connect.call_args[1]
        assert call_kwargs["allow_agent"] is True
        assert call_kwargs["hostname"] == "192.168.30.53"

    def test_close_all_closes_clients(self, registry):
        mock_mod, mock_client = _mock_paramiko()

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry)
            pool.get_client("proxmox")
            pool.close_all()

        mock_client.close.assert_called()

    def test_context_manager_calls_close_all(self, registry):
        mock_mod, mock_client = _mock_paramiko()

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            with ConnectionPool(registry) as pool:
                pool.get_client("proxmox")

        mock_client.close.assert_called()

    def test_connect_failure_raises_ssh_error(self, registry):
        mock_mod, mock_client = _mock_paramiko()
        mock_client.connect.side_effect = OSError("Connection refused")

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry)
            with pytest.raises(SSHError, match="Connection failed"):
                pool.get_client("proxmox")

    def test_auth_failure_raises_ssh_error(self, registry):
        mock_mod, mock_client = _mock_paramiko()
        mock_client.connect.side_effect = mock_mod.AuthenticationException("bad key")

        with patch.dict("sys.modules", {"paramiko": mock_mod}):
            pool = ConnectionPool(registry)
            with pytest.raises(SSHError, match="Authentication failed"):
                pool.get_client("proxmox")


# ---------------------------------------------------------------------------
# TestSSHExecutor
# ---------------------------------------------------------------------------


class TestSSHExecutor:
    def _make_exec_command(self, stdout_data, stderr_data, exit_code):
        """Build a mock return for client.exec_command()."""
        stdin = MagicMock()
        stdout_ch = MagicMock()
        stdout_ch.read.return_value = stdout_data.encode()
        stdout_ch.channel.recv_exit_status.return_value = exit_code
        stderr_ch = MagicMock()
        stderr_ch.read.return_value = stderr_data.encode()
        return stdin, stdout_ch, stderr_ch

    def test_run_single_host(self, registry):
        mock_pool = MagicMock(spec=ConnectionPool)
        mock_client = MagicMock()
        mock_pool.get_client.return_value = mock_client
        mock_client.exec_command.return_value = self._make_exec_command("hello\n", "", 0)

        executor = SSHExecutor(mock_pool, registry)
        results = executor.run("proxmox", "echo hello")

        assert len(results) == 1
        assert results[0].host == "proxmox"
        assert results[0].stdout == "hello\n"
        assert results[0].ok is True

    def test_run_group_returns_multiple(self, registry):
        mock_pool = MagicMock(spec=ConnectionPool)
        mock_client = MagicMock()
        mock_pool.get_client.return_value = mock_client
        mock_client.exec_command.return_value = self._make_exec_command("up", "", 0)

        executor = SSHExecutor(mock_pool, registry)
        results = executor.run("all", "uptime")

        assert len(results) == 3
        assert all(r.ok for r in results)

    def test_connection_failure_doesnt_abort_others(self, registry):
        mock_pool = MagicMock(spec=ConnectionPool)

        call_count = {"n": 0}

        def side_effect(alias):
            call_count["n"] += 1
            if alias == "truenas":
                raise SSHError("Connection refused")
            client = MagicMock()
            client.exec_command.return_value = self._make_exec_command("ok", "", 0)
            return client

        mock_pool.get_client.side_effect = side_effect

        executor = SSHExecutor(mock_pool, registry)
        results = executor.run("all", "hostname")

        assert len(results) == 3
        ok_results = [r for r in results if r.ok]
        failed = [r for r in results if not r.ok]
        assert len(ok_results) == 2
        assert len(failed) == 1
        assert failed[0].host == "truenas"
        assert "Connection refused" in failed[0].error

    def test_exit_code_captured(self, registry):
        mock_pool = MagicMock(spec=ConnectionPool)
        mock_client = MagicMock()
        mock_pool.get_client.return_value = mock_client
        mock_client.exec_command.return_value = self._make_exec_command("", "not found", 127)

        executor = SSHExecutor(mock_pool, registry)
        results = executor.run("proxmox", "nonexistent-cmd")

        assert results[0].exit_code == 127
        assert results[0].ok is False
        assert results[0].stderr == "not found"

    def test_stdout_and_stderr_captured(self, registry):
        mock_pool = MagicMock(spec=ConnectionPool)
        mock_client = MagicMock()
        mock_pool.get_client.return_value = mock_client
        mock_client.exec_command.return_value = self._make_exec_command(
            "output line\n", "warning: something\n", 0
        )

        executor = SSHExecutor(mock_pool, registry)
        results = executor.run("proxmox", "some-cmd")

        assert results[0].stdout == "output line\n"
        assert results[0].stderr == "warning: something\n"
        assert results[0].ok is True


# ---------------------------------------------------------------------------
# TestHealthChecker
# ---------------------------------------------------------------------------


class TestHealthChecker:
    def test_check_all_returns_health_report(self, registry):
        mock_executor = MagicMock(spec=SSHExecutor)
        mock_executor.run.return_value = [
            CommandResult(
                host="h",
                command="uptime",
                stdout="up 5 days, load average: 0.1, 0.2, 0.3",
                stderr="",
                exit_code=0,
            )
        ]

        with patch.object(HealthChecker, "_ping", return_value=(True, 1.5)):
            checker = HealthChecker(registry, mock_executor)
            report = checker.check_all()

        assert isinstance(report, HealthReport)
        assert len(report.hosts) == 3

    def test_ping_success_sets_ping_ok(self, registry):
        mock_executor = MagicMock(spec=SSHExecutor)
        mock_executor.run.return_value = [
            CommandResult(host="h", command="uptime", stdout="up", stderr="", exit_code=0)
        ]

        with patch.object(HealthChecker, "_ping", return_value=(True, 2.0)):
            checker = HealthChecker(registry, mock_executor)
            report = checker.check_all()

        assert all(h.ping_ok for h in report.hosts)

    def test_ping_failure_sets_ping_not_ok(self, registry):
        mock_executor = MagicMock(spec=SSHExecutor)
        mock_executor.run.return_value = [
            CommandResult(host="h", command="uptime", stdout="up", stderr="", exit_code=0)
        ]

        with patch.object(HealthChecker, "_ping", return_value=(False, 5000.0)):
            checker = HealthChecker(registry, mock_executor)
            report = checker.check_all()

        assert all(not h.ping_ok for h in report.hosts)

    def test_ssh_failure_sets_ssh_not_ok(self, registry):
        mock_executor = MagicMock(spec=SSHExecutor)
        mock_executor.run.return_value = [
            CommandResult(
                host="h", command="uptime", stdout="", stderr="", exit_code=-1, error="conn refused"
            )
        ]

        with patch.object(HealthChecker, "_ping", return_value=(True, 1.0)):
            checker = HealthChecker(registry, mock_executor)
            report = checker.check_all()

        assert all(not h.ssh_ok for h in report.hosts)

    def test_all_ok_computed_correctly_true(self, registry):
        mock_executor = MagicMock(spec=SSHExecutor)
        mock_executor.run.return_value = [
            CommandResult(host="h", command="uptime", stdout="up", stderr="", exit_code=0)
        ]

        with patch.object(HealthChecker, "_ping", return_value=(True, 1.0)):
            checker = HealthChecker(registry, mock_executor)
            report = checker.check_all()

        assert report.all_ok is True

    def test_all_ok_false_when_one_fails(self, registry):
        mock_executor = MagicMock(spec=SSHExecutor)
        call_count = {"n": 0}

        def run_side_effect(alias, cmd, timeout=30):
            call_count["n"] += 1
            if call_count["n"] == 2:
                return [
                    CommandResult(
                        host=alias, command=cmd, stdout="", stderr="", exit_code=-1, error="fail"
                    )
                ]
            return [CommandResult(host=alias, command=cmd, stdout="up", stderr="", exit_code=0)]

        mock_executor.run.side_effect = run_side_effect

        with patch.object(HealthChecker, "_ping", return_value=(True, 1.0)):
            checker = HealthChecker(registry, mock_executor)
            report = checker.check_all()

        assert report.all_ok is False

    def test_write_json_creates_valid_file(self, tmp_path, registry):
        output = tmp_path / "ssh" / "health.json"
        mock_executor = MagicMock(spec=SSHExecutor)

        checker = HealthChecker(registry, mock_executor, output_path=output)

        report = HealthReport(
            timestamp=1700000000.0,
            hosts=[
                HostStatus(
                    alias="proxmox",
                    hostname="192.168.30.10",
                    ping_ok=True,
                    ssh_ok=True,
                    uptime="up 5d",
                    latency_ms=1.2,
                ),
                HostStatus(
                    alias="truenas",
                    hostname="192.168.13.69",
                    ping_ok=True,
                    ssh_ok=False,
                    error="timeout",
                ),
            ],
        )

        checker.write_json(report)

        assert output.exists()
        data = json.loads(output.read_text())
        assert data["timestamp"] == 1700000000.0
        assert data["all_ok"] is False  # truenas ssh_ok=False
        assert len(data["hosts"]) == 2
        assert data["hosts"][0]["alias"] == "proxmox"
        assert data["hosts"][1]["error"] == "timeout"

    def test_ping_method_success(self):
        result = MagicMock()
        result.returncode = 0

        with patch("subprocess.run", return_value=result):
            ok, latency = HealthChecker._ping("192.168.1.1")

        assert ok is True
        assert latency >= 0

    def test_ping_method_failure(self):
        result = MagicMock()
        result.returncode = 1

        with patch("subprocess.run", return_value=result):
            ok, latency = HealthChecker._ping("192.168.1.1")

        assert ok is False

    def test_ping_method_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ping", 5)):
            ok, latency = HealthChecker._ping("192.168.1.1")

        assert ok is False

    def test_load_avg_parsed(self, registry):
        mock_executor = MagicMock(spec=SSHExecutor)
        mock_executor.run.return_value = [
            CommandResult(
                host="proxmox",
                command="uptime",
                stdout=" 14:30:00 up 5 days, load average: 0.15, 0.20, 0.18",
                stderr="",
                exit_code=0,
            )
        ]

        with patch.object(HealthChecker, "_ping", return_value=(True, 1.0)):
            checker = HealthChecker(registry, mock_executor)
            report = checker.check_all()

        proxmox_status = next(h for h in report.hosts if h.alias == "proxmox")
        assert proxmox_status.load_avg == "0.15, 0.20, 0.18"


# ---------------------------------------------------------------------------
# TestHomeAssistantClient
# ---------------------------------------------------------------------------


class TestHomeAssistantClient:
    def test_requires_url_and_token(self):
        with pytest.raises(SSHError, match="URL and token are required"):
            HomeAssistantClient(url="", token="tok")
        with pytest.raises(SSHError, match="URL and token are required"):
            HomeAssistantClient(url="http://ha.local:8123", token="")

    def test_get_state_returns_parsed(self, monkeypatch):
        client = HomeAssistantClient(url="http://ha.local:8123", token="test-token")

        response_data = json.dumps(
            {
                "entity_id": "light.office",
                "state": "on",
                "attributes": {"brightness": 255},
            }
        ).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured_req = {}

        def mock_urlopen(req, **kw):
            captured_req["url"] = req.full_url
            captured_req["method"] = req.method
            captured_req["headers"] = dict(req.headers)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        result = client.get_state("light.office")

        assert result["entity_id"] == "light.office"
        assert result["state"] == "on"
        assert "states/light.office" in captured_req["url"]
        assert "Bearer test-token" in captured_req["headers"].get("Authorization", "")

    def test_call_service_sends_post(self, monkeypatch):
        client = HomeAssistantClient(url="http://ha.local:8123", token="tok")

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["method"] = req.method
            captured["body"] = req.data
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        client.call_service("light", "turn_on", "light.office", {"brightness": 128})

        assert "services/light/turn_on" in captured["url"]
        assert captured["method"] == "POST"
        body = json.loads(captured["body"])
        assert body["entity_id"] == "light.office"
        assert body["brightness"] == 128

    def test_turn_on_convenience(self, monkeypatch):
        client = HomeAssistantClient(url="http://ha.local:8123", token="tok")

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["body"] = req.data
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        client.turn_on("light.kitchen")

        assert "services/light/turn_on" in captured["url"]
        body = json.loads(captured["body"])
        assert body["entity_id"] == "light.kitchen"

    def test_turn_off_convenience(self, monkeypatch):
        client = HomeAssistantClient(url="http://ha.local:8123", token="tok")

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["body"] = req.data
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        client.turn_off("switch.fan")

        assert "services/switch/turn_off" in captured["url"]
        body = json.loads(captured["body"])
        assert body["entity_id"] == "switch.fan"

    def test_turn_on_without_domain_uses_homeassistant(self, monkeypatch):
        client = HomeAssistantClient(url="http://ha.local:8123", token="tok")

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        client.turn_on("nodot")

        assert "services/homeassistant/turn_on" in captured["url"]

    def test_http_error_handled(self, monkeypatch):
        import urllib.error

        client = HomeAssistantClient(url="http://ha.local:8123", token="tok")

        def mock_urlopen(req, **kw):
            raise urllib.error.HTTPError(
                req.full_url, 401, "Unauthorized", {}, MagicMock(read=lambda: b"bad token")
            )

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        with pytest.raises(SSHError, match="API error 401"):
            client.get_state("light.office")

    def test_url_error_handled(self, monkeypatch):
        import urllib.error

        client = HomeAssistantClient(url="http://ha.local:8123", token="tok")

        def mock_urlopen(req, **kw):
            raise urllib.error.URLError("Connection refused")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        with pytest.raises(SSHError, match="connection error"):
            client.get_state("light.office")

    def test_get_states_returns_list(self, monkeypatch):
        client = HomeAssistantClient(url="http://ha.local:8123", token="tok")

        response_data = json.dumps(
            [
                {"entity_id": "light.a", "state": "on"},
                {"entity_id": "light.b", "state": "off"},
            ]
        ).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        result = client.get_states()
        assert len(result) == 2
        assert result[0]["entity_id"] == "light.a"

    def test_set_temperature(self, monkeypatch):
        client = HomeAssistantClient(url="http://ha.local:8123", token="tok")

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["body"] = req.data
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        client.set_temperature("climate.living_room", 72.0)

        assert "services/climate/set_temperature" in captured["url"]
        body = json.loads(captured["body"])
        assert body["entity_id"] == "climate.living_room"
        assert body["temperature"] == 72.0

    def test_trailing_slash_stripped_from_url(self, monkeypatch):
        client = HomeAssistantClient(url="http://ha.local:8123/", token="tok")

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        client.get_states()
        assert "//" not in captured["url"].replace("http://", "")
