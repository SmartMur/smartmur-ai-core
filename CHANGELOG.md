# Changelog

All notable changes to Claude Superpowers are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-03-06

Initial release with all 8 phases complete.

### Features
- Skill registry, loader, and generator with auto-install and SkillHub sync
- Cron daemon with APScheduler, SQLite job store, and launchd integration
- Multi-channel message gateway (Slack, Discord, Telegram, email, iMessage)
- SSH command fabric with connection pool and encrypted credential vault
- Playwright-based browser automation with session persistence
- YAML-defined workflow engine with approval gates and rollback actions
- Structured memory store with auto-context injection and decay
- File watcher service with directory monitoring and skill/workflow triggers

### Infrastructure
- `claw` CLI with 20+ subcommand groups
- Docker Compose stack (msg-gateway, cron-daemon, redis, browser-engine)
- CI/CD pipelines (lint, test, security scan, Docker build, deploy)
- Encrypted vault with age encryption and atomic writes
- Append-only audit log for all operations
- Agent registry with orchestrator and DAG executor
- Pack manager for skill/workflow/agent bundles
- Policy engine and reporting system
- Dashboard with authentication
- Release manager with migration checking
