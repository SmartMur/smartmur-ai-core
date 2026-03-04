# Action Plan: thepopebot Parity + Beyond

> Generated 2026-03-02 from `nextbest.md` competitive analysis.
> Reference repo still at `/tmp/tmp.v9c3usCfBg/thepopebot/`

---

## Phase A — Documentation Overhaul (P0)

**Goal**: Professional docs that match or beat thepopebot's operator-first style.

| # | Task | Output File | Est |
|---|------|-------------|-----|
| A1 | Root README with product narrative, arch diagram (ASCII), quickstart, "how it works" | `README.md` | 1h |
| A2 | Configuration reference — every env var, secret, config file with types/defaults/examples | `docs/CONFIGURATION.md` | 2h |
| A3 | Security doc — auth model, vault usage, webhook secrets, hardening checklist, risk disclosures | `docs/SECURITY.md` | 2h |
| A4 | Deployment guide — Docker Compose, systemd/launchd, reverse proxy, TLS, health checks | `docs/DEPLOYMENT.md` | 2h |
| A5 | Operator runbooks — deploy, rollback, incident triage, backup/restore | `docs/RUNBOOKS.md` | 1h |
| A6 | Upgrade guide — version migration, managed file diffs, breaking changes | `docs/UPGRADE.md` | 1h |
| A7 | Clean stale roadmap language from existing 19 docs, align to shipped behavior | `docs/*.md` | 1h |

**Acceptance**: Every doc has explicit tables, code examples, and zero TODO placeholders.

---

## Phase B — Telegram Parity+ (P0)

**Goal**: Match thepopebot's UX features while keeping our superior allowlist/concurrency/session system.

| # | Task | Files | Est |
|---|------|-------|-----|
| B1 | Add webhook endpoint to msg_gateway (FastAPI route, Telegram `setWebhook` helper) | `msg_gateway/telegram/webhook.py`, `msg_gateway/routes.py` | 3h |
| B2 | Webhook secret validation — fail-closed, HMAC verify, reject unsigned requests | `msg_gateway/telegram/webhook.py` | 1h |
| B3 | Keep polling as fallback — config toggle `TELEGRAM_MODE=webhook|polling` | `msg_gateway/telegram/poller.py`, `.env` | 30m |
| B4 | Typing indicator — send `ChatAction.typing` before LLM response starts | `msg_gateway/telegram/commands.py` | 30m |
| B5 | Message reactions — acknowledge receipt with thumbs-up reaction via Bot API | `msg_gateway/telegram/api.py` | 1h |
| B6 | Photo/document attachment ingestion — download file, extract text/describe image, feed to LLM | `msg_gateway/telegram/attachments.py` | 3h |
| B7 | Chat verification handshake — new user sends /start, must be on allowlist OR request access | `msg_gateway/telegram/auth.py` | 1h |
| B8 | Tests for all of the above (webhook mock, attachment pipeline, reaction send) | `tests/test_telegram_webhook.py`, `tests/test_telegram_attachments.py` | 2h |

**Acceptance**: Webhook mode works end-to-end. Photos sent to bot get described. Typing indicator shows. Reactions confirm receipt.

---

## Phase C — Dashboard GUI v2 (P0)

**Goal**: Real web app UX — streaming chat, job monitor, notifications, proper auth.

| # | Task | Files | Est |
|---|------|-------|-----|
| C1 | Server-side sessions — replace Basic auth with JWT/cookie sessions, login page | `dashboard/auth.py`, `dashboard/static/login.html` | 3h |
| C2 | Chat section — streaming SSE responses, message input, file upload | `dashboard/routers/chat.py`, `dashboard/static/chat.js` | 4h |
| C3 | Conversation history — list past chats, click to resume, stored in SQLite/Redis | `dashboard/routers/chat.py`, `superpowers/chat_store.py` | 3h |
| C4 | Notifications center — unread counter badge, event feed (cron failures, alerts, messages) | `dashboard/routers/notifications.py`, `dashboard/static/notifications.js` | 3h |
| C5 | Job monitor — show queued/running/completed tasks, real-time status updates via SSE | `dashboard/routers/jobs.py`, `dashboard/static/jobs.js` | 3h |
| C6 | Settings area — manage crons, triggers, API keys, integrations from UI | `dashboard/routers/settings.py` | 3h |
| C7 | Navigation overhaul — add new sections, improve responsive layout | `dashboard/static/index.html`, `dashboard/static/app.css` | 2h |
| C8 | Tests for chat streaming, session auth, job monitor API | `tests/test_dashboard_v2.py` | 2h |

**Acceptance**: Can have a full streaming conversation via web UI. Job monitor shows live task status. No more Basic auth popup.

---

## Phase D — Job Orchestration Mode (P1)

**Goal**: Branch-per-job execution with PR creation and optional auto-merge.

| # | Task | Files | Est |
|---|------|-------|-----|
| D1 | Job branch mode — create `job/{id}` branch, execute task, commit results | `superpowers/job_runner.py` | 4h |
| D2 | PR creation — auto-create PR from job branch with summary | `superpowers/job_runner.py` | 2h |
| D3 | Path-restricted auto-merge — `ALLOWED_PATHS` config, only auto-merge if changes within bounds | `superpowers/auto_merge.py` | 3h |
| D4 | PR status API — dashboard endpoint to show job PRs and their merge status | `dashboard/routers/jobs.py` | 2h |
| D5 | Tests | `tests/test_job_runner.py` | 2h |

**Acceptance**: Coding tasks create branch, execute, PR. Auto-merge only touches allowed paths.

---

## Phase E — Setup/Upgrade DX (P1)

**Goal**: Zero-friction onboarding and managed template lifecycle.

| # | Task | Files | Est |
|---|------|-------|-----|
| E1 | `claw setup` wizard — prereq checks (Python, Docker, Redis, age), guided env setup | `superpowers/setup_wizard.py`, `cli.py` | 3h |
| E2 | `claw setup-telegram` — Telegram-specific: create bot, set webhook, configure allowlist | `superpowers/setup_wizard.py` | 2h |
| E3 | Managed template lifecycle — `claw template init/diff/reset/upgrade` for workflows/docker/docs | `superpowers/template_manager.py` | 3h |
| E4 | Tests | `tests/test_setup_wizard.py` | 1h |

**Acceptance**: New user runs `claw setup`, answers prompts, gets working system. `claw template diff` shows what's changed.

---

## Phase F — Model Split & Overrides (P1)

**Goal**: Different models for interactive chat vs background jobs.

| # | Task | Files | Est |
|---|------|-------|-----|
| F1 | Config schema for model routing — `CHAT_MODEL`, `JOB_MODEL` env vars + per-job override | `superpowers/config.py` | 2h |
| F2 | Wire model selection into cron, workflow, and Telegram handler | `superpowers/cron_engine.py`, `msg_gateway/telegram/commands.py` | 2h |
| F3 | Multi-LLM provider support — abstract provider interface (Anthropic, OpenAI, Google) | `superpowers/llm_provider.py` | 3h |
| F4 | Tests | `tests/test_model_routing.py` | 1h |

**Acceptance**: Cron job can specify `llm_model: gpt-4o`. Chat uses Claude by default. Per-job override works.

---

## Phase G — Security Hardening (P1)

**Goal**: Fail-closed defaults, rate limiting, audit-ready.

| # | Task | Files | Est |
|---|------|-------|-----|
| G1 | Fail-closed webhook middleware — reject any unsigned/unverified inbound by default | `msg_gateway/middleware.py` | 2h |
| G2 | Rate limiting — per-IP and per-user limits on dashboard + webhook endpoints | `dashboard/middleware.py`, `msg_gateway/middleware.py` | 2h |
| G3 | Stricter auth defaults — no insecure fallbacks, force HTTPS in production mode | `superpowers/config.py` | 1h |
| G4 | Channel adapter normalization — base class contract for all adapters (Slack, Discord, Telegram, email) | `msg_gateway/channels/base.py` | 2h |
| G5 | Security audit checklist + deployment hardening doc finalization | `docs/SECURITY.md` | 1h |

**Acceptance**: All endpoints require auth. Rate limits active. No insecure defaults ship.

---

## Execution Priority & Dependencies

```
Phase A (Docs)          ──────► can start immediately, no code deps
Phase B (Telegram)      ──────► can start immediately, independent of A
Phase C (Dashboard v2)  ──────► can start immediately, independent of A/B
Phase D (Job Orch)      ──────► after C4 (needs job monitor API)
Phase E (Setup DX)      ──────► after A (docs inform wizard content)
Phase F (Model Split)   ──────► after B+C (needs chat + cron wiring)
Phase G (Security)      ──────► after B+C (hardens webhook + dashboard)
```

**Parallel tracks**:
- **Track 1**: A → E (docs → setup wizard)
- **Track 2**: B → F (Telegram → model routing)
- **Track 3**: C → D → G (dashboard → jobs → security)

---

## Quick Wins (can do right now, <30 min each)

1. **Typing indicator** (B4) — 10-line change in commands.py
2. **Webhook secret env var** — add `TELEGRAM_WEBHOOK_SECRET` to `.env.example`
3. **Root README.md** (A1) — high-visibility, no code changes
4. **Clean stale TODOs** (A7) — grep and fix across docs

---

## Patterns to Adopt from thepopebot

1. **Channel Adapter base class** — `receive()`, `acknowledge()`, `startProcessingIndicator()`, `sendResponse()`, `supportsStreaming`
2. **Secrets by prefix** — `AGENT_` (hidden from LLM), `AGENT_LLM_` (exposed to skills)
3. **Markdown template processor** — `{{var}}` substitution in prompts and config
4. **Checkpoint persistence** — save agent state per conversation, not just logs
5. **Simple JSON config** — CRONS.json/TRIGGERS.json pattern for user-editable configs
6. **Per-job LLM selection** — `llm_provider` + `llm_model` fields in cron/trigger entries

---

## What We Already Do Better (keep these)

- Allowlist security (secure-by-default vs thepopebot's open webhooks)
- Concurrency control (per-chat + global semaphores + queue overflow)
- Session persistence (Redis with TTL)
- Skill registry with auto-install and sandboxing
- Encrypted vault with rotation alerts
- 982 tests passing
- 14 production skills
- Full SSH fabric + browser automation (thepopebot has neither)

---

## Success Metrics

| Phase | Metric |
|-------|--------|
| A | All docs pass review, zero stale TODOs, README renders on GitHub |
| B | Telegram webhook processes 100 msgs without failure, attachments work |
| C | Full chat conversation via web UI with streaming, <200ms TTFB |
| D | Job creates branch + PR automatically, auto-merge respects path constraints |
| E | New user goes from `git clone` to working system in <5 minutes |
| F | Cron job runs with GPT-4o while chat uses Claude, no config conflicts |
| G | Zero unauthenticated endpoints, rate limits trigger on abuse |
