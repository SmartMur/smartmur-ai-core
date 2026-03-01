"""Lazy-singleton engine factories for dashboard dependency injection."""

from __future__ import annotations

from pathlib import Path

from superpowers.config import Settings

_settings: Settings | None = None
_cron_engine = None
_memory_store = None
_channel_registry = None
_profile_manager = None
_host_registry = None
_ssh_pool = None
_ssh_executor = None
_health_checker = None
_workflow_loader = None
_workflow_engine = None
_skill_registry = None
_audit_log = None
_watcher_engine = None
_browser_profiles = None
_vault = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def get_cron_engine():
    global _cron_engine
    if _cron_engine is None:
        from superpowers.cron_engine import CronEngine
        _cron_engine = CronEngine()
    return _cron_engine


def get_memory_store():
    global _memory_store
    if _memory_store is None:
        from superpowers.memory.store import MemoryStore
        _memory_store = MemoryStore()
    return _memory_store


def get_channel_registry():
    global _channel_registry
    if _channel_registry is None:
        from superpowers.channels.registry import ChannelRegistry
        _channel_registry = ChannelRegistry(get_settings())
    return _channel_registry


def get_profile_manager():
    global _profile_manager
    if _profile_manager is None:
        from superpowers.profiles import ProfileManager
        _profile_manager = ProfileManager(get_channel_registry())
    return _profile_manager


def get_host_registry():
    global _host_registry
    if _host_registry is None:
        from superpowers.ssh_fabric.hosts import HostRegistry
        _host_registry = HostRegistry()
    return _host_registry


def get_ssh_executor():
    global _ssh_executor
    if _ssh_executor is None:
        from superpowers.ssh_fabric.executor import SSHExecutor
        from superpowers.ssh_fabric.pool import ConnectionPool
        global _ssh_pool
        hosts = get_host_registry()
        _ssh_pool = ConnectionPool(hosts)
        _ssh_executor = SSHExecutor(_ssh_pool, hosts)
    return _ssh_executor


def get_health_checker():
    global _health_checker
    if _health_checker is None:
        from superpowers.ssh_fabric.health import HealthChecker
        _health_checker = HealthChecker(get_host_registry(), get_ssh_executor())
    return _health_checker


def get_workflow_loader():
    global _workflow_loader
    if _workflow_loader is None:
        from superpowers.workflow.loader import WorkflowLoader
        _workflow_loader = WorkflowLoader()
    return _workflow_loader


def get_workflow_engine():
    global _workflow_engine
    if _workflow_engine is None:
        from superpowers.workflow.engine import WorkflowEngine
        _workflow_engine = WorkflowEngine()
    return _workflow_engine


def get_skill_registry():
    global _skill_registry
    if _skill_registry is None:
        from superpowers.skill_registry import SkillRegistry
        _skill_registry = SkillRegistry()
    return _skill_registry


def get_audit_log():
    global _audit_log
    if _audit_log is None:
        from superpowers.audit import AuditLog
        _audit_log = AuditLog()
    return _audit_log


def get_watcher_engine():
    global _watcher_engine
    if _watcher_engine is None:
        from superpowers.watcher.engine import WatcherEngine
        _watcher_engine = WatcherEngine()
    return _watcher_engine


def get_browser_profiles():
    global _browser_profiles
    if _browser_profiles is None:
        from superpowers.browser.profiles import ProfileManager
        _browser_profiles = ProfileManager()
    return _browser_profiles


def get_vault():
    global _vault
    if _vault is None:
        from superpowers.vault import Vault
        _vault = Vault()
    return _vault
