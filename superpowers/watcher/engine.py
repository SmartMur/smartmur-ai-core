from __future__ import annotations

import fnmatch
import logging
import os
import shutil
import subprocess
from pathlib import Path

import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from superpowers.watcher.base import WatchAction, WatcherError, WatchRule

logger = logging.getLogger("watcher-engine")

# Map watchdog event types to our event names
_EVENT_MAP = {
    "created": "created",
    "modified": "modified",
    "deleted": "deleted",
    "moved": "moved",
}


class _RuleHandler(FileSystemEventHandler):
    """Watchdog handler that delegates matching events to the engine."""

    def __init__(self, engine: WatcherEngine, rule: WatchRule):
        super().__init__()
        self._engine = engine
        self._rule = rule

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        event_type = event.event_type  # created, modified, deleted, moved
        mapped = _EVENT_MAP.get(event_type)
        if mapped and mapped in self._rule.events:
            self._engine._on_event(event, self._rule)


class WatcherEngine:
    def __init__(self, rules_path: Path | None = None):
        if rules_path is None:
            rules_path = Path.home() / ".claude-superpowers" / "watchers.yaml"
        self._rules_path = Path(rules_path)
        self._rules: list[WatchRule] = []
        self._observer: Observer | None = None
        self._load_rules()

    def _load_rules(self) -> None:
        if not self._rules_path.exists():
            self._rules = []
            return

        try:
            data = yaml.safe_load(self._rules_path.read_text())
        except (yaml.YAMLError, OSError) as exc:
            raise WatcherError(f"Failed to load rules: {exc}")

        if not isinstance(data, list):
            self._rules = []
            return

        self._rules = []
        for item in data:
            try:
                rule = WatchRule(
                    name=item["name"],
                    path=item["path"],
                    events=item.get("events", ["created"]),
                    action=WatchAction(item["action"]),
                    command=item["command"],
                    args=item.get("args", {}),
                    enabled=item.get("enabled", True),
                )
                self._rules.append(rule)
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping invalid rule: %s", exc)

    def start(self) -> None:
        if self._observer is not None:
            raise WatcherError("Watcher already running")

        self._observer = Observer()

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Expand ~ and resolve the watch directory
            watch_path = Path(rule.path).expanduser()
            # If path has a glob pattern, watch the parent directory
            if any(c in watch_path.name for c in ("*", "?", "[")):
                watch_dir = watch_path.parent
            else:
                watch_dir = watch_path

            if not watch_dir.exists():
                logger.warning("Watch path does not exist: %s (rule: %s)", watch_dir, rule.name)
                continue

            handler = _RuleHandler(self, rule)
            self._observer.schedule(handler, str(watch_dir), recursive=False)
            logger.info("Watching %s for rule '%s'", watch_dir, rule.name)

        self._observer.start()
        logger.info("Watcher engine started with %d rules", len(self._rules))

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Watcher engine stopped")

    def _on_event(self, event: FileSystemEvent, rule: WatchRule) -> None:
        src_path = event.src_path
        watch_pattern = str(Path(rule.path).expanduser())

        # If the rule path has a glob in the filename, match against it
        if any(c in Path(rule.path).name for c in ("*", "?", "[")):
            if not fnmatch.fnmatch(src_path, watch_pattern):
                return

        logger.info("Event %s on %s matched rule '%s'", event.event_type, src_path, rule.name)

        try:
            if rule.action == WatchAction.shell:
                self._action_shell(src_path, rule)
            elif rule.action == WatchAction.skill:
                self._action_skill(src_path, rule)
            elif rule.action == WatchAction.workflow:
                self._action_workflow(src_path, rule)
            elif rule.action == WatchAction.move:
                self._action_move(src_path, rule)
            elif rule.action == WatchAction.copy:
                self._action_copy(src_path, rule)
        except Exception:
            logger.exception("Action failed for rule '%s' on %s", rule.name, src_path)

    def _action_shell(self, src_path: str, rule: WatchRule) -> None:
        env = {**os.environ, "WATCHER_FILE": src_path}
        for k, v in rule.args.items():
            env[f"WATCHER_{k.upper()}"] = str(v)
        result = subprocess.run(
            rule.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        logger.info("Shell action exit=%d stdout=%s", result.returncode, result.stdout[:200])

    def _action_skill(self, src_path: str, rule: WatchRule) -> None:
        from superpowers.skill_loader import SkillLoader
        from superpowers.skill_registry import SkillRegistry

        registry = SkillRegistry()
        loader = SkillLoader()
        skill = registry.get(rule.command)
        args = {**rule.args, "file": src_path}
        result = loader.run(skill, args)
        logger.info("Skill action exit=%d", result.returncode)

    def _action_workflow(self, src_path: str, rule: WatchRule) -> None:
        logger.warning("Workflow action not yet implemented (rule: %s)", rule.name)

    def _action_move(self, src_path: str, rule: WatchRule) -> None:
        target_dir = Path(rule.command).expanduser()
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / Path(src_path).name
        shutil.move(src_path, str(dest))
        logger.info("Moved %s -> %s", src_path, dest)

    def _action_copy(self, src_path: str, rule: WatchRule) -> None:
        target_dir = Path(rule.command).expanduser()
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / Path(src_path).name
        shutil.copy2(src_path, str(dest))
        logger.info("Copied %s -> %s", src_path, dest)

    def list_rules(self) -> list[WatchRule]:
        return list(self._rules)

    def get_rule(self, name: str) -> WatchRule:
        for rule in self._rules:
            if rule.name == name:
                return rule
        raise WatcherError(f"Rule not found: {name}")
