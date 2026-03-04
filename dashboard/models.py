"""Pydantic v2 request/response models for the dashboard API."""

from __future__ import annotations

from pydantic import BaseModel

# --- Status ---


class SubsystemStatus(BaseModel):
    name: str
    ok: bool
    detail: str = ""
    count: int = 0


class AggregateStatus(BaseModel):
    subsystems: list[SubsystemStatus]


# --- Cron ---


class CronJobOut(BaseModel):
    id: str
    name: str
    schedule: str
    job_type: str
    command: str
    args: dict = {}
    output_channel: str = "file"
    enabled: bool = True
    created_at: str = ""
    last_run: str = ""
    last_status: str = ""


class CronJobCreate(BaseModel):
    name: str
    schedule: str
    job_type: str = "shell"
    command: str
    args: dict = {}
    output_channel: str = "file"
    enabled: bool = True


class CronLogEntry(BaseModel):
    filename: str
    content: str


# --- Messaging ---


class SendMessageRequest(BaseModel):
    channel: str
    target: str
    message: str


class SendMessageResponse(BaseModel):
    ok: bool
    channel: str
    target: str
    error: str = ""


class ChannelInfo(BaseModel):
    name: str
    configured: bool


class ProfileOut(BaseModel):
    name: str
    targets: list[dict]


class ProfileSendRequest(BaseModel):
    message: str


# --- SSH ---


class SSHRunRequest(BaseModel):
    target: str
    command: str
    timeout: int = 30


class SSHCommandResult(BaseModel):
    host: str
    command: str
    stdout: str
    stderr: str
    exit_code: int
    ok: bool
    error: str = ""


class SSHHostOut(BaseModel):
    alias: str
    hostname: str
    port: int
    username: str
    groups: list[str]


class SSHHealthOut(BaseModel):
    alias: str
    hostname: str
    ping_ok: bool
    ssh_ok: bool
    uptime: str = ""
    load_avg: str = ""
    latency_ms: float = 0.0
    error: str = ""


# --- Workflows ---


class WorkflowOut(BaseModel):
    name: str
    description: str = ""
    step_count: int = 0


class WorkflowDetail(BaseModel):
    name: str
    description: str = ""
    steps: list[dict]
    rollback_steps: list[dict] = []
    notify_profile: str = ""


class WorkflowRunRequest(BaseModel):
    dry_run: bool = False


class StepResultOut(BaseModel):
    step_name: str
    status: str
    output: str = ""
    error: str = ""


# --- Memory ---


class MemoryEntryOut(BaseModel):
    id: int
    category: str
    key: str
    value: str
    tags: list[str] = []
    project: str = ""
    created_at: str = ""
    accessed_at: str = ""
    access_count: int = 0


class MemoryCreateRequest(BaseModel):
    key: str
    value: str
    category: str = "fact"
    tags: list[str] = []
    project: str = ""


class MemoryStatsOut(BaseModel):
    total: int
    by_category: dict[str, int] = {}
    oldest: str | None = None
    newest: str | None = None


# --- Skills ---


class SkillOut(BaseModel):
    name: str
    description: str
    version: str
    author: str


class SkillDetail(BaseModel):
    name: str
    description: str
    version: str
    author: str
    triggers: list[str] = []
    dependencies: list[str] = []
    permissions: list[str] = []


class SkillRunRequest(BaseModel):
    args: dict = {}


class SkillRunResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int


# --- Audit ---


class AuditEntry(BaseModel):
    ts: str = ""
    action: str = ""
    detail: str = ""
    source: str = ""


# --- Vault ---


class VaultStatus(BaseModel):
    initialized: bool
    key_count: int = 0


# --- Watchers ---


class WatchRuleOut(BaseModel):
    name: str
    path: str
    events: list[str]
    action: str
    command: str
    enabled: bool = True


# --- Browser ---


class BrowserProfileOut(BaseModel):
    name: str


# --- GitHub Security ---


class GitHubRepoOut(BaseModel):
    name: str
    default_branch: str = "main"
    is_private: bool = False
    is_fork: bool = False
    protected: bool = False


class GitHubProtectionOut(BaseModel):
    repo: str
    branch: str
    enforce_admins: bool = False
    require_reviews: bool = False
    required_approvals: int = 0
    dismiss_stale: bool = False
    allow_force_push: bool = True
    allow_deletions: bool = True


class GitHubSecurityStatus(BaseModel):
    authenticated: bool
    auth_detail: str = ""
    repo_count: int = 0
    protected_count: int = 0
    unprotected_repos: list[str] = []
    timestamp: str = ""


class GitHubAuditFinding(BaseModel):
    severity: str  # critical, warning, info
    repo: str
    finding: str
    detail: str = ""


# --- Rsync ---


class RsyncJobCreate(BaseModel):
    name: str = ""
    source_host: str = ""
    source_path: str
    source_user: str = "root"
    dest_host: str = ""
    dest_path: str
    dest_user: str = "root"
    ssh_key: str = ""
    delete: bool = False
    exclude_patterns: list[str] = []
    bandwidth_limit_kbps: int = 0
    dry_run: bool = False


class RsyncJobOut(BaseModel):
    id: str
    name: str = ""
    source_host: str = ""
    source_path: str
    source_user: str = "root"
    dest_host: str = ""
    dest_path: str
    dest_user: str = "root"
    options: dict = {}
    ssh_key: str = ""
    status: str = "pending"
    progress: dict = {}
    stats: dict = {}
    output: str = ""
    error: str = ""
    pid: int | None = None
    started_at: float | None = None
    completed_at: float | None = None
    created_at: float


class RsyncProgressEvent(BaseModel):
    current_file: str = ""
    percent: int = 0
    speed: str = ""
    eta: str = ""
    files_transferred: int = 0
    bytes_transferred: int = 0
