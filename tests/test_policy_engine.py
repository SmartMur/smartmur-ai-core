"""Tests for the policy engine — orchestration safety enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from superpowers.policy_engine import (
    _DEFAULT_SECRET_PATTERNS,
    Policy,
    PolicyAction,
    PolicyDecision,
    PolicyEngine,
    PolicyRule,
    _default_policies,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine() -> PolicyEngine:
    """Engine with only built-in defaults (no config file)."""
    return PolicyEngine()


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    return tmp_path / "policies.yaml"


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Default policies
# ---------------------------------------------------------------------------


class TestDefaultPolicies:
    def test_default_policies_loaded(self, engine: PolicyEngine) -> None:
        policies = engine.get_policies()
        assert len(policies) >= 5
        names = [p.name for p in policies]
        assert "destructive-commands" in names
        assert "force-push-protection" in names
        assert "approval-required" in names
        assert "file-protection" in names
        assert "secret-detection" in names

    def test_default_policies_function(self) -> None:
        defaults = _default_policies()
        assert isinstance(defaults, list)
        assert all(isinstance(p, Policy) for p in defaults)

    def test_each_default_has_rules(self) -> None:
        for p in _default_policies():
            assert len(p.rules) > 0, f"Policy '{p.name}' has no rules"

    def test_default_secret_patterns_nonempty(self) -> None:
        assert len(_DEFAULT_SECRET_PATTERNS) >= 5


# ---------------------------------------------------------------------------
# Command checks — deny
# ---------------------------------------------------------------------------


class TestCommandDeny:
    def test_rm_rf_root(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("rm -rf /")
        assert decision.action == PolicyAction.deny

    def test_rm_rf_root_variants(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("rm -rf / ")
        assert decision.action == PolicyAction.deny

    def test_drop_table(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("mysql -e 'DROP TABLE users'")
        assert decision.action == PolicyAction.deny

    def test_drop_database(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("DROP DATABASE production")
        assert decision.action == PolicyAction.deny

    def test_format_drive(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("FORMAT C:")
        assert decision.action == PolicyAction.deny

    def test_mkfs(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("mkfs.ext4 /dev/sda1")
        assert decision.action == PolicyAction.deny

    def test_dd_to_device(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("dd if=/dev/zero of=/dev/sda bs=4M")
        assert decision.action == PolicyAction.deny

    def test_force_push_main(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("git push --force origin main")
        assert decision.action == PolicyAction.deny

    def test_force_push_master(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("git push -f origin master")
        assert decision.action == PolicyAction.deny

    def test_force_push_feature_allowed(self, engine: PolicyEngine) -> None:
        """Force push to feature branches should not be denied by default."""
        decision = engine.check_command("git push --force origin feature/my-branch")
        assert decision.action != PolicyAction.deny


# ---------------------------------------------------------------------------
# Command checks — require_approval
# ---------------------------------------------------------------------------


class TestCommandApproval:
    def test_git_push(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("git push origin feature")
        assert decision.action == PolicyAction.require_approval

    def test_docker_rm(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("docker rm my-container")
        assert decision.action == PolicyAction.require_approval

    def test_docker_rmi(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("docker rmi my-image:latest")
        assert decision.action == PolicyAction.require_approval

    def test_docker_system_prune(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("docker system prune -a")
        assert decision.action == PolicyAction.require_approval

    def test_docker_container_rm(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("docker container rm foo")
        assert decision.action == PolicyAction.require_approval


# ---------------------------------------------------------------------------
# Command checks — allow
# ---------------------------------------------------------------------------


class TestCommandAllow:
    def test_ls(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("ls -la")
        assert decision.action == PolicyAction.allow

    def test_cat(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("cat /etc/hostname")
        assert decision.action == PolicyAction.allow

    def test_git_status(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("git status")
        assert decision.action == PolicyAction.allow

    def test_docker_ps(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("docker ps")
        assert decision.action == PolicyAction.allow

    def test_empty_command(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("")
        assert decision.action == PolicyAction.allow

    def test_whitespace_command(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("   ")
        assert decision.action == PolicyAction.allow

    def test_pip_install(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("pip install requests")
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# File access checks
# ---------------------------------------------------------------------------


class TestFileAccess:
    def test_deny_etc_passwd(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("/etc/passwd")
        assert decision.action == PolicyAction.deny

    def test_deny_etc_shadow(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("/etc/shadow")
        assert decision.action == PolicyAction.deny

    def test_deny_etc_sudoers(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("/etc/sudoers")
        assert decision.action == PolicyAction.deny

    def test_deny_env_files(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("/home/user/project/.env")
        assert decision.action == PolicyAction.deny

    def test_deny_authorized_keys(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("/home/ray/.ssh/authorized_keys")
        assert decision.action == PolicyAction.deny

    def test_approval_pem_files(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("/etc/ssl/server.pem")
        assert decision.action == PolicyAction.require_approval

    def test_approval_key_files(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("/etc/ssl/private/server.key")
        assert decision.action == PolicyAction.require_approval

    def test_allow_normal_file(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("/home/ray/code/main.py")
        assert decision.action == PolicyAction.allow

    def test_allow_empty_path(self, engine: PolicyEngine) -> None:
        decision = engine.check_file_access("")
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# Secret detection in output
# ---------------------------------------------------------------------------


class TestOutputSecrets:
    def test_detects_api_key(self, engine: PolicyEngine) -> None:
        output = "Config: api_key=sk_live_abc123def456ghi789jkl012mno"
        has_secrets, redacted = engine.check_output(output)
        assert has_secrets is True
        assert "sk_live_abc123" not in redacted
        assert "[REDACTED]" in redacted

    def test_detects_bearer_token(self, engine: PolicyEngine) -> None:
        output = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdef"
        has_secrets, redacted = engine.check_output(output)
        assert has_secrets is True
        assert "[REDACTED]" in redacted

    def test_detects_aws_key(self, engine: PolicyEngine) -> None:
        output = "Found key: AKIAIOSFODNN7EXAMPLE"
        has_secrets, redacted = engine.check_output(output)
        assert has_secrets is True
        assert "AKIAIOSFODNN7EXAMPLE" not in redacted

    def test_detects_private_key(self, engine: PolicyEngine) -> None:
        output = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."
        has_secrets, redacted = engine.check_output(output)
        assert has_secrets is True
        assert "[REDACTED]" in redacted

    def test_detects_github_token(self, engine: PolicyEngine) -> None:
        output = "Token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        has_secrets, redacted = engine.check_output(output)
        assert has_secrets is True

    def test_detects_slack_token(self, engine: PolicyEngine) -> None:
        output = "SLACK_TOKEN=xoxb-123456789012-abcdefghij"
        has_secrets, redacted = engine.check_output(output)
        assert has_secrets is True

    def test_detects_password_assignment(self, engine: PolicyEngine) -> None:
        output = "password=MyS3cur3P@ssw0rd!"
        has_secrets, redacted = engine.check_output(output)
        assert has_secrets is True
        assert "MyS3cur3P@ssw0rd!" not in redacted

    def test_clean_output_passes(self, engine: PolicyEngine) -> None:
        output = "Build succeeded. 42 tests passed."
        has_secrets, redacted = engine.check_output(output)
        assert has_secrets is False
        assert redacted == output

    def test_empty_output(self, engine: PolicyEngine) -> None:
        has_secrets, redacted = engine.check_output("")
        assert has_secrets is False
        assert redacted == ""


# ---------------------------------------------------------------------------
# Custom YAML policies
# ---------------------------------------------------------------------------


class TestCustomPolicies:
    def test_load_custom_yaml(self, tmp_config: Path) -> None:
        config = {
            "policies": [
                {
                    "name": "test-policy",
                    "description": "Test policy",
                    "rules": [
                        {
                            "action": "deny",
                            "command_pattern": r"dangerous_command",
                            "description": "Block dangerous_command",
                        }
                    ],
                }
            ]
        }
        tmp_config.write_text(yaml.safe_dump(config))
        engine = PolicyEngine(config_path=tmp_config)

        decision = engine.check_command("run dangerous_command now")
        assert decision.action == PolicyAction.deny
        assert decision.policy_name == "test-policy"

    def test_custom_file_rule(self, tmp_config: Path) -> None:
        config = {
            "policies": [
                {
                    "name": "custom-files",
                    "rules": [
                        {
                            "action": "deny",
                            "resource_pattern": "*/secret.txt",
                            "description": "Block secret.txt",
                        }
                    ],
                }
            ]
        }
        tmp_config.write_text(yaml.safe_dump(config))
        engine = PolicyEngine(config_path=tmp_config)

        decision = engine.check_file_access("/home/ray/secret.txt")
        assert decision.action == PolicyAction.deny

    def test_custom_approval_rule(self, tmp_config: Path) -> None:
        config = {
            "policies": [
                {
                    "name": "custom-approval",
                    "rules": [
                        {
                            "action": "require_approval",
                            "command_pattern": r"deploy\s+prod",
                            "description": "Production deployment needs approval",
                        }
                    ],
                }
            ]
        }
        tmp_config.write_text(yaml.safe_dump(config))
        engine = PolicyEngine(config_path=tmp_config)

        decision = engine.check_command("deploy prod v2.0")
        assert decision.action == PolicyAction.require_approval

    def test_custom_secret_patterns(self, tmp_config: Path) -> None:
        config = {
            "policies": [
                {
                    "name": "custom-secrets",
                    "rules": [
                        {
                            "action": "deny",
                            "secret_patterns": [r"INTERNAL_SECRET_[A-Z0-9]{8,}"],
                            "description": "Internal secret detection",
                        }
                    ],
                }
            ]
        }
        tmp_config.write_text(yaml.safe_dump(config))
        engine = PolicyEngine(config_path=tmp_config)

        has_secrets, redacted = engine.check_output("key=INTERNAL_SECRET_ABCD1234EFGH")
        assert has_secrets is True
        assert "[REDACTED]" in redacted

    def test_missing_config_file(self, tmp_path: Path) -> None:
        """Engine should work even if config file does not exist."""
        engine = PolicyEngine(config_path=tmp_path / "nonexistent.yaml")
        assert len(engine.get_policies()) >= 5  # defaults still present

    def test_invalid_yaml(self, tmp_config: Path) -> None:
        tmp_config.write_text(": : : invalid yaml [[[")
        engine = PolicyEngine(config_path=tmp_config)
        # Should not crash, defaults still work
        assert len(engine.get_policies()) >= 5

    def test_wrong_yaml_type(self, tmp_config: Path) -> None:
        tmp_config.write_text("just a string")
        engine = PolicyEngine(config_path=tmp_config)
        assert len(engine.get_policies()) >= 5

    def test_invalid_action_skipped(self, tmp_config: Path) -> None:
        config = {
            "policies": [
                {
                    "name": "bad-action",
                    "rules": [
                        {
                            "action": "explode",
                            "command_pattern": "test",
                        }
                    ],
                }
            ]
        }
        tmp_config.write_text(yaml.safe_dump(config))
        engine = PolicyEngine(config_path=tmp_config)
        # bad-action policy exists but with no valid rules
        names = [p.name for p in engine.get_policies()]
        assert "bad-action" in names

    def test_custom_max_retries_and_timeout(self, tmp_config: Path) -> None:
        config = {
            "policies": [
                {
                    "name": "custom-limits",
                    "rules": [
                        {
                            "action": "deny",
                            "command_pattern": "slow_cmd",
                            "max_retries": 5,
                            "timeout_seconds": 600,
                        }
                    ],
                }
            ]
        }
        tmp_config.write_text(yaml.safe_dump(config))
        engine = PolicyEngine(config_path=tmp_config)
        policy = [p for p in engine.get_policies() if p.name == "custom-limits"][0]
        assert policy.rules[0].max_retries == 5
        assert policy.rules[0].timeout_seconds == 600


# ---------------------------------------------------------------------------
# PolicyRule unit tests
# ---------------------------------------------------------------------------


class TestPolicyRule:
    def test_matches_command(self) -> None:
        rule = PolicyRule(action=PolicyAction.deny, command_pattern=r"rm\s+-rf")
        assert rule.matches_command("rm -rf /tmp") is True
        assert rule.matches_command("ls -la") is False

    def test_matches_file(self) -> None:
        rule = PolicyRule(action=PolicyAction.deny, resource_pattern="*.key")
        assert rule.matches_file("server.key") is True
        assert rule.matches_file("readme.md") is False

    def test_no_pattern_no_match(self) -> None:
        rule = PolicyRule(action=PolicyAction.deny)
        assert rule.matches_command("anything") is False
        assert rule.matches_file("/anything") is False

    def test_invalid_regex(self) -> None:
        rule = PolicyRule(action=PolicyAction.deny, command_pattern="[invalid")
        assert rule.matches_command("test") is False


# ---------------------------------------------------------------------------
# PolicyDecision
# ---------------------------------------------------------------------------


class TestPolicyDecision:
    def test_fields(self) -> None:
        d = PolicyDecision(
            action=PolicyAction.deny,
            reason="test reason",
            policy_name="test-policy",
        )
        assert d.action == PolicyAction.deny
        assert d.reason == "test reason"
        assert d.policy_name == "test-policy"

    def test_default_policy_name(self) -> None:
        d = PolicyDecision(action=PolicyAction.allow, reason="ok")
        assert d.policy_name == ""


# ---------------------------------------------------------------------------
# Engine runtime management
# ---------------------------------------------------------------------------


class TestEngineManagement:
    def test_add_policy(self, engine: PolicyEngine) -> None:
        count_before = len(engine.get_policies())
        engine.add_policy(
            Policy(
                name="runtime-added",
                rules=[
                    PolicyRule(
                        action=PolicyAction.deny,
                        command_pattern="nuke_everything",
                    )
                ],
            )
        )
        assert len(engine.get_policies()) == count_before + 1
        decision = engine.check_command("nuke_everything")
        assert decision.action == PolicyAction.deny

    def test_remove_policy(self, engine: PolicyEngine) -> None:
        count_before = len(engine.get_policies())
        removed = engine.remove_policy("destructive-commands")
        assert removed is True
        assert len(engine.get_policies()) == count_before - 1

    def test_remove_nonexistent(self, engine: PolicyEngine) -> None:
        removed = engine.remove_policy("does-not-exist")
        assert removed is False

    def test_deny_wins_over_approval(self) -> None:
        """When both deny and approval rules match, deny should win."""
        engine = PolicyEngine()
        engine.add_policy(
            Policy(
                name="approval-for-push",
                rules=[
                    PolicyRule(
                        action=PolicyAction.require_approval,
                        command_pattern=r"git push",
                    )
                ],
            )
        )
        engine.add_policy(
            Policy(
                name="deny-specific-push",
                rules=[
                    PolicyRule(
                        action=PolicyAction.deny,
                        command_pattern=r"git push.*--delete",
                    )
                ],
            )
        )
        decision = engine.check_command("git push --delete origin branch")
        assert decision.action == PolicyAction.deny

    def test_from_data_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SUPERPOWERS_DATA_DIR", str(tmp_path))
        engine = PolicyEngine.from_data_dir()
        assert len(engine.get_policies()) >= 5


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_policy_list(self, runner: CliRunner) -> None:
        from superpowers.cli_policy import policy_group

        result = runner.invoke(policy_group, ["list"])
        assert result.exit_code == 0
        assert "destructive-commands" in result.output

    def test_policy_check_allow(self, runner: CliRunner) -> None:
        from superpowers.cli_policy import policy_group

        result = runner.invoke(policy_group, ["check", "ls -la"])
        assert result.exit_code == 0
        assert "allow" in result.output

    def test_policy_check_deny(self, runner: CliRunner) -> None:
        from superpowers.cli_policy import policy_group

        result = runner.invoke(policy_group, ["check", "DROP TABLE users"])
        assert result.exit_code == 1
        assert "deny" in result.output

    def test_policy_check_file_allow(self, runner: CliRunner) -> None:
        from superpowers.cli_policy import policy_group

        result = runner.invoke(policy_group, ["check-file", "/home/ray/code.py"])
        assert result.exit_code == 0
        assert "allow" in result.output

    def test_policy_check_file_deny(self, runner: CliRunner) -> None:
        from superpowers.cli_policy import policy_group

        result = runner.invoke(policy_group, ["check-file", "/etc/shadow"])
        assert result.exit_code == 1
        assert "deny" in result.output

    def test_policy_test_output_clean(self, runner: CliRunner) -> None:
        from superpowers.cli_policy import policy_group

        result = runner.invoke(policy_group, ["test-output", "Build OK, 42 tests passed"])
        assert result.exit_code == 0
        assert "No secrets detected" in result.output

    def test_policy_test_output_secret(self, runner: CliRunner) -> None:
        from superpowers.cli_policy import policy_group

        result = runner.invoke(
            policy_group, ["test-output", "api_key=sk_live_abcdefghijklmnopqrstuvwx"]
        )
        assert result.exit_code == 1
        assert "Secrets detected" in result.output


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_case_insensitive_drop(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("drop table users")
        assert decision.action == PolicyAction.deny

    def test_multiword_command(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("echo hello && git push origin main --force")
        assert decision.action == PolicyAction.deny

    def test_decision_has_reason(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("DROP TABLE x")
        assert len(decision.reason) > 0

    def test_decision_has_policy_name(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("DROP TABLE x")
        assert decision.policy_name == "destructive-commands"

    def test_unicode_command(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("echo 'hello world'")
        assert decision.action == PolicyAction.allow

    def test_very_long_command(self, engine: PolicyEngine) -> None:
        decision = engine.check_command("echo " + "a" * 10000)
        assert decision.action == PolicyAction.allow

    def test_policies_list_returns_copy(self, engine: PolicyEngine) -> None:
        p1 = engine.get_policies()
        p2 = engine.get_policies()
        assert p1 is not p2

    def test_load_policies_called_twice(self, tmp_config: Path) -> None:
        config = {
            "policies": [
                {
                    "name": "first",
                    "rules": [{"action": "deny", "command_pattern": "first_cmd"}],
                }
            ]
        }
        tmp_config.write_text(yaml.safe_dump(config))
        engine = PolicyEngine(config_path=tmp_config)

        config2 = {
            "policies": [
                {
                    "name": "second",
                    "rules": [{"action": "deny", "command_pattern": "second_cmd"}],
                }
            ]
        }
        tmp_config.write_text(yaml.safe_dump(config2))
        engine.load_policies(tmp_config)

        names = [p.name for p in engine.get_policies()]
        assert "first" in names
        assert "second" in names
