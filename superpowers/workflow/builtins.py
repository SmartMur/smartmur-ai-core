"""Built-in workflow templates."""

from __future__ import annotations

from pathlib import Path

DEPLOY_WORKFLOW = """\
name: deploy
description: "Pull latest code, test, deploy via Docker Compose, health check, notify"
notify_profile: ""
steps:
  - name: git-pull
    type: shell
    command: "git pull origin main"
    on_failure: abort

  - name: run-tests
    type: shell
    command: "PYTHONPATH=. pytest tests/ -q"
    on_failure: abort

  - name: docker-deploy
    type: shell
    command: "docker compose up -d --build"
    on_failure: rollback

  - name: health-check
    type: shell
    command: "sleep 5 && curl -sf http://localhost:8100/health"
    timeout: 30
    on_failure: rollback

rollback:
  - name: rollback-deploy
    type: shell
    command: "docker compose down && git checkout HEAD~1 && docker compose up -d"
"""

BACKUP_WORKFLOW = """\
name: backup
description: "Snapshot VMs, verify snapshots, notify"
steps:
  - name: snapshot-vms
    type: shell
    command: ssh proxmox 'qm list | tail -n+2 | awk "{print $1}" | xargs -I{} qm snapshot {} auto-backup'
    timeout: 600
    on_failure: abort

  - name: verify-snapshots
    type: shell
    command: ssh proxmox 'qm list | tail -n+2 | awk "{print $1}" | xargs -I{} qm listsnapshot {}'
    on_failure: continue
"""

MORNING_BRIEF_WORKFLOW = """\
name: morning-brief
description: "Check services, summarize alerts, send digest"
notify_profile: info
steps:
  - name: health-check
    type: skill
    command: heartbeat
    on_failure: continue

  - name: summarize
    type: claude_prompt
    command: "Read the latest health check output and summarize the status of all services in 3 bullet points."
    on_failure: continue

  - name: send-digest
    type: shell
    command: "echo Morning brief complete"
    on_failure: continue
"""


def install_builtins(workflows_dir: Path) -> list[str]:
    """Write built-in workflow templates if they don't exist. Returns list of created names."""
    workflows_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for name, content in [
        ("deploy", DEPLOY_WORKFLOW),
        ("backup", BACKUP_WORKFLOW),
        ("morning-brief", MORNING_BRIEF_WORKFLOW),
    ]:
        path = workflows_dir / f"{name}.yaml"
        if not path.exists():
            path.write_text(content)
            created.append(name)
    return created
