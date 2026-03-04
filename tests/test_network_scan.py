"""Tests for the network scanner — superpowers/network_scanner.py + skills/network-scan/run.py."""

from __future__ import annotations

import importlib.util
import socket
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from superpowers.network_scanner import (
    DEFAULT_HOSTS,
    DEFAULT_PORTS,
    DEFAULT_TIMEOUT,
    HostResult,
    PortResult,
    ScanReport,
    check_port,
    expand_subnet,
    format_port_detail,
    format_table,
    load_config,
    ping_host,
    run_scan,
    scan_host,
)

# Import skill runner via file path (avoids collision with other run.py files)
_skill_run = Path(__file__).resolve().parent.parent / "skills" / "network-scan" / "run.py"
_spec = importlib.util.spec_from_file_location("network_scan_run", _skill_run)
skill_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skill_mod)


# ── ping_host tests ──────────────────────────────────────────────────


class TestPingHost:
    def test_ping_success(self):
        """ping_host returns (True, latency) when ping succeeds."""
        fake = subprocess.CompletedProcess(
            args=["ping", "-c", "1", "-W", "2", "10.0.0.1"],
            returncode=0,
            stdout="64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=1.23 ms\n",
            stderr="",
        )
        with patch("superpowers.network_scanner.subprocess.run", return_value=fake):
            alive, latency = ping_host("10.0.0.1", timeout=2)
            assert alive is True
            assert latency == 1.23

    def test_ping_failure(self):
        """ping_host returns (False, None) when ping fails."""
        fake = subprocess.CompletedProcess(
            args=["ping", "-c", "1", "-W", "2", "10.0.0.1"],
            returncode=1,
            stdout="",
            stderr="",
        )
        with patch("superpowers.network_scanner.subprocess.run", return_value=fake):
            alive, latency = ping_host("10.0.0.1", timeout=2)
            assert alive is False
            assert latency is None

    def test_ping_timeout_exception(self):
        """ping_host returns (False, None) when subprocess times out."""
        with patch(
            "superpowers.network_scanner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ping", timeout=4),
        ):
            alive, latency = ping_host("10.0.0.1", timeout=2)
            assert alive is False
            assert latency is None

    def test_ping_parses_linux_output(self):
        """Extracts time= value from typical Linux ping output."""
        output = (
            "PING 192.168.1.1 (192.168.1.1) 56(84) bytes of data.\n"
            "64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=0.456 ms\n"
            "\n"
            "--- 192.168.1.1 ping statistics ---\n"
        )
        fake = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        with patch("superpowers.network_scanner.subprocess.run", return_value=fake):
            alive, latency = ping_host("192.168.1.1")
            assert alive is True
            assert latency == 0.46  # rounded to 2 decimal places


# ── check_port tests ─────────────────────────────────────────────────


class TestCheckPort:
    def test_port_open(self):
        """check_port returns open=True when connection succeeds."""
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.connect_ex.return_value = 0
        with patch("superpowers.network_scanner.socket.socket", return_value=mock_sock):
            result = check_port("10.0.0.1", 22, timeout=2)
            assert result.port == 22
            assert result.open is True
            assert result.response_time_ms is not None
            mock_sock.close.assert_called_once()

    def test_port_closed(self):
        """check_port returns open=False when connection refused."""
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.connect_ex.return_value = 111  # ECONNREFUSED
        with patch("superpowers.network_scanner.socket.socket", return_value=mock_sock):
            result = check_port("10.0.0.1", 22, timeout=2)
            assert result.port == 22
            assert result.open is False
            assert result.response_time_ms is None

    def test_port_timeout(self):
        """check_port returns open=False on socket timeout."""
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.connect_ex.side_effect = socket.timeout("timed out")
        with patch("superpowers.network_scanner.socket.socket", return_value=mock_sock):
            result = check_port("10.0.0.1", 443, timeout=1)
            assert result.open is False


# ── expand_subnet tests ──────────────────────────────────────────────


class TestExpandSubnet:
    def test_expand_24(self):
        """Expanding a /24 yields 254 host addresses."""
        hosts = expand_subnet("192.168.1.0/24")
        assert len(hosts) == 254
        assert "192.168.1.1" in hosts
        assert "192.168.1.254" in hosts
        # Network and broadcast excluded
        assert "192.168.1.0" not in hosts
        assert "192.168.1.255" not in hosts

    def test_expand_30(self):
        """Expanding a /30 yields 2 host addresses."""
        hosts = expand_subnet("10.0.0.0/30")
        assert len(hosts) == 2
        assert "10.0.0.1" in hosts
        assert "10.0.0.2" in hosts

    def test_expand_invalid(self):
        """Invalid CIDR returns empty list."""
        assert expand_subnet("not-a-cidr") == []

    def test_expand_single_host(self):
        """A /32 yields no hosts (network == broadcast)."""
        hosts = expand_subnet("10.0.0.1/32")
        assert len(hosts) == 1
        assert hosts[0] == "10.0.0.1"


# ── scan_host tests ──────────────────────────────────────────────────


class TestScanHost:
    def test_scan_live_host(self):
        """scan_host checks ports when host is alive."""
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.connect_ex.return_value = 0  # All ports open

        fake_ping = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="64 bytes: time=2.00 ms\n", stderr=""
        )

        with (
            patch("superpowers.network_scanner.subprocess.run", return_value=fake_ping),
            patch("superpowers.network_scanner.socket.socket", return_value=mock_sock),
        ):
            result = scan_host("10.0.0.1", "TestHost", ports=[22, 80])
            assert result.alive is True
            assert result.label == "TestHost"
            assert len(result.ports) == 2

    def test_scan_dead_host_skips_ports(self):
        """scan_host skips port scan when host is down."""
        fake_ping = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )
        with patch("superpowers.network_scanner.subprocess.run", return_value=fake_ping):
            result = scan_host("10.0.0.1", "DeadHost", ports=[22, 80])
            assert result.alive is False
            assert len(result.ports) == 0

    def test_scan_host_default_label(self):
        """scan_host uses IP as label when label is empty."""
        fake_ping = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )
        with patch("superpowers.network_scanner.subprocess.run", return_value=fake_ping):
            result = scan_host("10.0.0.1", "", ports=[])
            assert result.label == "10.0.0.1"


# ── run_scan tests ───────────────────────────────────────────────────


class TestRunScan:
    def test_scan_all_up(self):
        """run_scan with all hosts up returns healthy report."""
        hosts = [("10.0.0.1", "Host1"), ("10.0.0.2", "Host2")]

        fake_ping = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="64 bytes: time=1.00 ms\n", stderr=""
        )
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.connect_ex.return_value = 111  # closed

        with (
            patch("superpowers.network_scanner.subprocess.run", return_value=fake_ping),
            patch("superpowers.network_scanner.socket.socket", return_value=mock_sock),
        ):
            report = run_scan(hosts=hosts, ports=[22], critical=["10.0.0.1", "10.0.0.2"])
            assert report.total_hosts == 2
            assert report.hosts_up == 2
            assert report.hosts_down == 0
            assert report.all_critical_up is True
            assert report.critical_down == []

    def test_scan_critical_down(self):
        """run_scan detects critical host failures."""
        hosts = [("10.0.0.1", "Host1")]

        fake_ping = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )
        with patch("superpowers.network_scanner.subprocess.run", return_value=fake_ping):
            report = run_scan(hosts=hosts, ports=[], critical=["10.0.0.1"])
            assert report.hosts_down == 1
            assert report.all_critical_up is False
            assert "10.0.0.1" in report.critical_down

    def test_scan_non_critical_down_is_ok(self):
        """run_scan returns all_critical_up=True when only non-critical hosts are down."""
        hosts = [("10.0.0.1", "Critical"), ("10.0.0.2", "Optional")]

        def fake_run(cmd, **kwargs):
            ip = cmd[-1]
            if ip == "10.0.0.1":
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0,
                    stdout="time=1.00 ms\n", stderr=""
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr=""
            )

        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.connect_ex.return_value = 111

        with (
            patch("superpowers.network_scanner.subprocess.run", side_effect=fake_run),
            patch("superpowers.network_scanner.socket.socket", return_value=mock_sock),
        ):
            report = run_scan(
                hosts=hosts,
                ports=[22],
                critical=["10.0.0.1"],  # Only 10.0.0.1 is critical
            )
            assert report.hosts_up == 1
            assert report.hosts_down == 1
            assert report.all_critical_up is True

    def test_scan_with_subnet(self):
        """run_scan expands subnets and includes them in scan."""
        fake_ping = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )
        with patch("superpowers.network_scanner.subprocess.run", return_value=fake_ping):
            report = run_scan(
                hosts=[],
                subnets=["10.0.0.0/30"],  # 2 hosts
                ports=[],
                critical=[],
                workers=2,
            )
            assert report.total_hosts == 2


# ── load_config tests ────────────────────────────────────────────────


class TestLoadConfig:
    def test_defaults(self):
        """load_config returns defaults when no env vars are set."""
        env = {
            k: v for k, v in {}.items()
        }
        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            assert config["hosts"] == list(DEFAULT_HOSTS)
            assert config["ports"] == list(DEFAULT_PORTS)
            assert config["timeout"] == DEFAULT_TIMEOUT
            assert config["subnets"] == []

    def test_custom_hosts(self):
        """load_config parses NETWORK_SCAN_HOSTS correctly."""
        env = {"NETWORK_SCAN_HOSTS": "10.0.0.1:Router, 10.0.0.2:NAS"}
        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            assert config["hosts"] == [("10.0.0.1", "Router"), ("10.0.0.2", "NAS")]

    def test_custom_hosts_no_label(self):
        """load_config uses IP as label when no label specified."""
        env = {"NETWORK_SCAN_HOSTS": "10.0.0.1"}
        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            assert config["hosts"] == [("10.0.0.1", "10.0.0.1")]

    def test_custom_ports(self):
        """load_config parses NETWORK_SCAN_PORTS."""
        env = {"NETWORK_SCAN_PORTS": "22,80,3000"}
        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            assert config["ports"] == [22, 80, 3000]

    def test_custom_critical(self):
        """load_config parses NETWORK_SCAN_CRITICAL."""
        env = {"NETWORK_SCAN_CRITICAL": "10.0.0.1,10.0.0.2"}
        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            assert config["critical"] == ["10.0.0.1", "10.0.0.2"]

    def test_critical_defaults_to_all_hosts(self):
        """When NETWORK_SCAN_CRITICAL is not set, all hosts are critical."""
        env = {"NETWORK_SCAN_HOSTS": "10.0.0.1:A, 10.0.0.2:B"}
        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            assert config["critical"] == ["10.0.0.1", "10.0.0.2"]

    def test_custom_subnets(self):
        """load_config parses NETWORK_SCAN_SUBNETS."""
        env = {"NETWORK_SCAN_SUBNETS": "192.168.1.0/24,10.0.0.0/24"}
        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            assert config["subnets"] == ["192.168.1.0/24", "10.0.0.0/24"]

    def test_custom_timeout_and_workers(self):
        """load_config reads timeout and workers from env."""
        env = {"NETWORK_SCAN_TIMEOUT": "5", "NETWORK_SCAN_WORKERS": "10"}
        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            assert config["timeout"] == 5
            assert config["workers"] == 10


# ── format_table tests ───────────────────────────────────────────────


class TestFormatTable:
    def test_table_includes_header(self):
        """format_table includes header row."""
        report = ScanReport(hosts=[], total_hosts=0, hosts_up=0, hosts_down=0)
        output = format_table(report)
        assert "HOST" in output
        assert "IP" in output
        assert "STATUS" in output
        assert "OPEN PORTS" in output

    def test_table_shows_host_status(self):
        """format_table shows UP/DOWN for each host."""
        report = ScanReport(
            hosts=[
                HostResult(ip="10.0.0.1", label="Router", alive=True, ping_time_ms=1.5),
                HostResult(ip="10.0.0.2", label="NAS", alive=False),
            ],
            total_hosts=2,
            hosts_up=1,
            hosts_down=1,
        )
        output = format_table(report)
        assert "Router" in output
        assert "UP" in output
        assert "NAS" in output
        assert "DOWN" in output
        assert "1.5ms" in output

    def test_table_shows_open_ports(self):
        """format_table displays open ports with service names."""
        report = ScanReport(
            hosts=[
                HostResult(
                    ip="10.0.0.1",
                    label="Web",
                    alive=True,
                    ping_time_ms=2.0,
                    ports=[
                        PortResult(port=22, open=True, response_time_ms=1.0),
                        PortResult(port=80, open=True, response_time_ms=2.0),
                        PortResult(port=443, open=False),
                    ],
                ),
            ],
            total_hosts=1,
            hosts_up=1,
            hosts_down=0,
        )
        output = format_table(report)
        assert "22/SSH" in output
        assert "80/HTTP" in output
        # Closed port not shown in summary
        assert "443/HTTPS" not in output

    def test_table_critical_down_warning(self):
        """format_table shows critical down warning."""
        report = ScanReport(
            hosts=[],
            total_hosts=1,
            hosts_up=0,
            hosts_down=1,
            critical_down=["10.0.0.1"],
        )
        output = format_table(report)
        assert "CRITICAL" in output
        assert "10.0.0.1" in output

    def test_table_all_ok_message(self):
        """format_table shows OK message when no critical hosts down."""
        report = ScanReport(
            hosts=[], total_hosts=1, hosts_up=1, hosts_down=0
        )
        output = format_table(report)
        assert "[OK]" in output


# ── format_port_detail tests ─────────────────────────────────────────


class TestFormatPortDetail:
    def test_detail_shows_open_and_closed(self):
        """format_port_detail shows both OPEN and CLOSED ports."""
        report = ScanReport(
            hosts=[
                HostResult(
                    ip="10.0.0.1",
                    label="Server",
                    alive=True,
                    ports=[
                        PortResult(port=22, open=True, response_time_ms=1.5),
                        PortResult(port=80, open=False),
                    ],
                ),
            ],
        )
        output = format_port_detail(report)
        assert "OPEN" in output
        assert "CLOSED" in output
        assert "1.5ms" in output

    def test_detail_skips_dead_hosts(self):
        """format_port_detail does not include dead hosts."""
        report = ScanReport(
            hosts=[
                HostResult(ip="10.0.0.1", label="Dead", alive=False),
            ],
        )
        output = format_port_detail(report)
        assert "Dead" not in output


# ── Skill runner tests ───────────────────────────────────────────────


class TestSkillRunner:
    def test_main_returns_0_on_all_up(self):
        """Skill main() returns 0 when all critical hosts are up."""
        fake_report = ScanReport(
            hosts=[HostResult(ip="10.0.0.1", label="H1", alive=True)],
            total_hosts=1,
            hosts_up=1,
            hosts_down=0,
            critical_down=[],
            scan_time_seconds=0.5,
        )
        with (
            patch.object(skill_mod, "load_config", return_value={
                "hosts": [("10.0.0.1", "H1")],
                "subnets": [],
                "ports": [22],
                "critical": ["10.0.0.1"],
                "timeout": 2,
                "workers": 5,
            }),
            patch.object(skill_mod, "run_scan", return_value=fake_report),
            patch.object(skill_mod, "format_table", return_value="table"),
            patch.object(skill_mod, "format_port_detail", return_value="detail"),
            patch.object(skill_mod.telegram_notify, "notify_error", return_value=False),
        ):
            assert skill_mod.main() == 0

    def test_main_returns_1_on_critical_down(self):
        """Skill main() returns 1 when a critical host is down."""
        fake_report = ScanReport(
            hosts=[HostResult(ip="10.0.0.1", label="H1", alive=False)],
            total_hosts=1,
            hosts_up=0,
            hosts_down=1,
            critical_down=["10.0.0.1"],
            scan_time_seconds=0.5,
        )
        with (
            patch.object(skill_mod, "load_config", return_value={
                "hosts": [("10.0.0.1", "H1")],
                "subnets": [],
                "ports": [22],
                "critical": ["10.0.0.1"],
                "timeout": 2,
                "workers": 5,
            }),
            patch.object(skill_mod, "run_scan", return_value=fake_report),
            patch.object(skill_mod, "format_table", return_value="table"),
            patch.object(skill_mod, "format_port_detail", return_value="detail"),
            patch.object(skill_mod.telegram_notify, "notify_error", return_value=False),
        ):
            assert skill_mod.main() == 1

    def test_main_returns_2_on_exception(self):
        """Skill main() returns 2 when scan raises an exception."""
        with (
            patch.object(skill_mod, "load_config", return_value={
                "hosts": [], "subnets": [], "ports": [],
                "critical": [], "timeout": 2, "workers": 5,
            }),
            patch.object(skill_mod, "run_scan", side_effect=RuntimeError("boom")),
            patch.object(skill_mod.telegram_notify, "notify_error", return_value=False),
        ):
            assert skill_mod.main() == 2
