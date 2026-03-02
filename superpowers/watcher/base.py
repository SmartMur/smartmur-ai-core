from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class WatcherError(Exception):
    pass


class WatchAction(StrEnum):
    shell = "shell"
    skill = "skill"
    workflow = "workflow"
    move = "move"
    copy = "copy"


@dataclass
class WatchRule:
    name: str
    path: str
    events: list[str]
    action: WatchAction
    command: str
    args: dict = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self):
        if isinstance(self.action, str):
            self.action = WatchAction(self.action)
