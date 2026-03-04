from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import yaml

from superpowers.watcher.base import WatchAction, WatcherError, WatchRule
from superpowers.watcher.engine import WatcherEngine

# --- WatchRule dataclass ---


class TestWatchRule:
    def test_basic_creation(self):
        rule = WatchRule(
            name="test",
            path="~/Downloads/*.torrent",
            events=["created"],
            action=WatchAction.move,
            command="/tmp/dest",
        )
        assert rule.name == "test"
        assert rule.action == WatchAction.move
        assert rule.enabled is True
        assert rule.args == {}

    def test_action_coercion_from_string(self):
        rule = WatchRule(
            name="test",
            path="/tmp",
            events=["created"],
            action="shell",
            command="echo hi",
        )
        assert rule.action == WatchAction.shell

    def test_all_actions(self):
        for action in WatchAction:
            rule = WatchRule(
                name=f"test-{action.value}",
                path="/tmp",
                events=["created"],
                action=action,
                command="test",
            )
            assert rule.action == action

    def test_disabled_rule(self):
        rule = WatchRule(
            name="off",
            path="/tmp",
            events=["created"],
            action=WatchAction.shell,
            command="echo",
            enabled=False,
        )
        assert rule.enabled is False

    def test_custom_args(self):
        rule = WatchRule(
            name="test",
            path="/tmp",
            events=["created", "modified"],
            action=WatchAction.shell,
            command="echo",
            args={"extra": "value"},
        )
        assert rule.args == {"extra": "value"}
        assert rule.events == ["created", "modified"]


# --- WatcherEngine YAML loading ---


class TestWatcherEngineLoading:
    def test_load_empty_file(self, tmp_path):
        rules_file = tmp_path / "watchers.yaml"
        rules_file.write_text("")
        engine = WatcherEngine(rules_path=rules_file)
        assert engine.list_rules() == []

    def test_load_nonexistent_file(self, tmp_path):
        rules_file = tmp_path / "does_not_exist.yaml"
        engine = WatcherEngine(rules_path=rules_file)
        assert engine.list_rules() == []

    def test_load_valid_rules(self, tmp_path):
        rules_file = tmp_path / "watchers.yaml"
        rules = [
            {
                "name": "torrent-mover",
                "path": "~/Downloads/*.torrent",
                "events": ["created"],
                "action": "move",
                "command": "/tmp/dest",
            },
            {
                "name": "screenshot",
                "path": "~/Desktop/Screenshot*.png",
                "events": ["created"],
                "action": "shell",
                "command": "optipng $WATCHER_FILE",
            },
        ]
        rules_file.write_text(yaml.dump(rules))
        engine = WatcherEngine(rules_path=rules_file)
        loaded = engine.list_rules()
        assert len(loaded) == 2
        assert loaded[0].name == "torrent-mover"
        assert loaded[0].action == WatchAction.move
        assert loaded[1].name == "screenshot"
        assert loaded[1].action == WatchAction.shell

    def test_load_skips_invalid_rules(self, tmp_path):
        rules_file = tmp_path / "watchers.yaml"
        rules = [
            {
                "name": "good",
                "path": "/tmp",
                "events": ["created"],
                "action": "shell",
                "command": "echo ok",
            },
            {
                "name": "bad",
                # missing required fields
            },
        ]
        rules_file.write_text(yaml.dump(rules))
        engine = WatcherEngine(rules_path=rules_file)
        loaded = engine.list_rules()
        assert len(loaded) == 1
        assert loaded[0].name == "good"

    def test_load_with_disabled_rule(self, tmp_path):
        rules_file = tmp_path / "watchers.yaml"
        rules = [
            {
                "name": "disabled-one",
                "path": "/tmp",
                "events": ["created"],
                "action": "shell",
                "command": "echo",
                "enabled": False,
            },
        ]
        rules_file.write_text(yaml.dump(rules))
        engine = WatcherEngine(rules_path=rules_file)
        loaded = engine.list_rules()
        assert len(loaded) == 1
        assert loaded[0].enabled is False

    def test_get_rule_by_name(self, tmp_path):
        rules_file = tmp_path / "watchers.yaml"
        rules = [
            {
                "name": "finder",
                "path": "/tmp",
                "events": ["created"],
                "action": "shell",
                "command": "echo",
            },
        ]
        rules_file.write_text(yaml.dump(rules))
        engine = WatcherEngine(rules_path=rules_file)
        rule = engine.get_rule("finder")
        assert rule.name == "finder"

    def test_get_rule_not_found(self, tmp_path):
        rules_file = tmp_path / "watchers.yaml"
        rules_file.write_text("[]")
        engine = WatcherEngine(rules_path=rules_file)
        with pytest.raises(WatcherError, match="Rule not found"):
            engine.get_rule("nonexistent")


# --- Event matching ---


class TestEventMatching:
    def _make_engine(self, tmp_path, rule_data):
        rules_file = tmp_path / "watchers.yaml"
        rules_file.write_text(yaml.dump([rule_data]))
        return WatcherEngine(rules_path=rules_file)

    def test_glob_match(self, tmp_path):
        engine = self._make_engine(
            tmp_path,
            {
                "name": "test",
                "path": str(tmp_path / "*.txt"),
                "events": ["created"],
                "action": "shell",
                "command": "echo matched",
            },
        )
        rule = engine.list_rules()[0]

        from watchdog.events import FileCreatedEvent

        # Should match
        event = FileCreatedEvent(str(tmp_path / "hello.txt"))
        with patch.object(engine, "_action_shell") as mock:
            engine._on_event(event, rule)
            mock.assert_called_once()

    def test_glob_no_match(self, tmp_path):
        engine = self._make_engine(
            tmp_path,
            {
                "name": "test",
                "path": str(tmp_path / "*.txt"),
                "events": ["created"],
                "action": "shell",
                "command": "echo matched",
            },
        )
        rule = engine.list_rules()[0]

        from watchdog.events import FileCreatedEvent

        # Should NOT match (wrong extension)
        event = FileCreatedEvent(str(tmp_path / "hello.jpg"))
        with patch.object(engine, "_action_shell") as mock:
            engine._on_event(event, rule)
            mock.assert_not_called()


# --- Action dispatch ---


class TestActionDispatch:
    def _make_engine_with_rule(self, tmp_path, action, command):
        rules_file = tmp_path / "watchers.yaml"
        rules = [
            {
                "name": "test-action",
                "path": str(tmp_path / "*"),
                "events": ["created"],
                "action": action,
                "command": command,
            }
        ]
        rules_file.write_text(yaml.dump(rules))
        return WatcherEngine(rules_path=rules_file)

    @patch("superpowers.watcher.engine.subprocess.run")
    def test_shell_action(self, mock_run, tmp_path):
        engine = self._make_engine_with_rule(tmp_path, "shell", "echo $WATCHER_FILE")
        rule = engine.list_rules()[0]
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        from watchdog.events import FileCreatedEvent

        event = FileCreatedEvent(str(tmp_path / "file.txt"))
        engine._on_event(event, rule)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs[1]["env"]["WATCHER_FILE"] == str(tmp_path / "file.txt")

    @patch("superpowers.watcher.engine.shutil.move")
    def test_move_action(self, mock_move, tmp_path):
        dest = tmp_path / "dest"
        engine = self._make_engine_with_rule(tmp_path, "move", str(dest))
        rule = engine.list_rules()[0]

        from watchdog.events import FileCreatedEvent

        src_file = tmp_path / "file.torrent"
        src_file.touch()
        event = FileCreatedEvent(str(src_file))
        engine._on_event(event, rule)

        mock_move.assert_called_once_with(str(src_file), str(dest / "file.torrent"))

    @patch("superpowers.watcher.engine.shutil.copy2")
    def test_copy_action(self, mock_copy, tmp_path):
        dest = tmp_path / "backup"
        engine = self._make_engine_with_rule(tmp_path, "copy", str(dest))
        rule = engine.list_rules()[0]

        from watchdog.events import FileCreatedEvent

        src_file = tmp_path / "data.csv"
        src_file.touch()
        event = FileCreatedEvent(str(src_file))
        engine._on_event(event, rule)

        mock_copy.assert_called_once_with(str(src_file), str(dest / "data.csv"))
