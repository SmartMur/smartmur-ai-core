#!/usr/bin/env bash
# Phase D/E/F/G runner — dispatches Claude agents for each phase
# Sends Telegram notifications per completed task
set -uo pipefail

PROJECT_DIR="/home/ray/claude-superpowers"
source "$PROJECT_DIR/.env" 2>/dev/null || true

CHAT_ID="${TELEGRAM_DEFAULT_CHAT_ID:-}"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"

notify() {
    local msg="$1"
    if [[ -n "$BOT_TOKEN" && -n "$CHAT_ID" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
            -d "chat_id=${CHAT_ID}" \
            --data-urlencode "text=${msg}" \
            -d "disable_web_page_preview=true" >/dev/null 2>&1
    fi
    echo "$msg"
}

run_phase() {
    local phase="$1"
    local description="$2"
    local prompt="$3"
    local start_time=$(date '+%H:%M')

    notify "🚀 Starting Phase ${phase}: ${description} (${start_time})"

    local output
    output=$(cd "$PROJECT_DIR" && claude -p "$prompt" --output-format text 2>&1) || true
    local rc=$?
    local end_time=$(date '+%H:%M')

    if [[ $rc -eq 0 && -n "$output" ]]; then
        # Truncate for Telegram (max 4096 chars)
        local summary="${output:0:3800}"
        notify "✅ Phase ${phase} COMPLETE (${start_time}→${end_time})

${summary}"
    else
        notify "❌ Phase ${phase} FAILED (rc=${rc}, ${start_time}→${end_time})

${output:0:1000}"
    fi
}

notify "📋 ACTION PLAN: Starting Phases D/E/F/G
⏰ $(date '+%Y-%m-%d %H:%M %Z')
4 phases queued — will notify per completion"

# Phase D — Job Orchestration
run_phase "D" "Job Orchestration Mode" "You are working in /home/ray/claude-superpowers/. Implement Phase D — Job Orchestration Mode.

Build these in superpowers/job_runner.py:
D1: Job branch mode — create job/{id} branch, execute task, commit results
D2: PR creation — auto-create PR from job branch with summary using gh CLI at ~/.local/bin/gh
D3: Path-restricted auto-merge — ALLOWED_PATHS config, only auto-merge if changes within allowed paths
D4: PR status API — add endpoint to dashboard/routers/jobs.py to show job PRs and merge status

Build tests in tests/test_job_runner.py covering all features.

Use git for branch operations. Use gh CLI for PR creation. Add ALLOWED_AUTO_MERGE_PATHS to superpowers/config.py.
Run tests with: PYTHONPATH=. .venv/bin/python -m pytest tests/test_job_runner.py -v
All tests must pass. Do NOT push any branches to remote — this is local only."

# Phase E — Setup/Upgrade DX
run_phase "E" "Setup & Upgrade DX" "You are working in /home/ray/claude-superpowers/. Implement Phase E — Setup/Upgrade DX.

Build superpowers/setup_wizard.py:
E1: claw setup wizard — check prereqs (Python 3.12+, Docker, Redis, age), guided .env creation, vault init
E2: claw setup-telegram — create bot instructions, set webhook, configure allowlist
E3: Managed template lifecycle in superpowers/template_manager.py — claw template init/diff/reset/upgrade for workflows/docker/docs

Wire into superpowers/cli.py as 'claw setup' and 'claw template' commands.

Build tests in tests/test_setup_wizard.py.
Run tests with: PYTHONPATH=. .venv/bin/python -m pytest tests/test_setup_wizard.py -v
All tests must pass."

# Phase F — Model Split & Overrides
run_phase "F" "Model Split & Overrides" "You are working in /home/ray/claude-superpowers/. Implement Phase F — Model Split & Overrides.

F1: Add CHAT_MODEL and JOB_MODEL env vars to superpowers/config.py with defaults (claude for chat, claude for jobs)
F2: Wire model selection into superpowers/cron_engine.py (per-job llm_model field) and msg_gateway/telegram/ chat handler
F3: Build superpowers/llm_provider.py — abstract LLMProvider interface with AnthropicProvider, OpenAIProvider, GoogleProvider implementations. Each wraps the respective CLI or API.
F4: Build tests in tests/test_model_routing.py

Run tests with: PYTHONPATH=. .venv/bin/python -m pytest tests/test_model_routing.py -v
All tests must pass."

# Phase G — Security Hardening
run_phase "G" "Security Hardening" "You are working in /home/ray/claude-superpowers/. Implement Phase G — Security Hardening.

G1: Build msg_gateway/middleware.py — fail-closed webhook middleware, reject unsigned/unverified inbound by default
G2: Add rate limiting to dashboard/middleware.py and msg_gateway/middleware.py — per-IP and per-user limits using in-memory token bucket
G3: Stricter auth defaults in superpowers/config.py — no insecure fallbacks, FORCE_HTTPS env var for production mode
G4: Build msg_gateway/channels/base.py — ChannelAdapter base class with receive(), acknowledge(), startProcessingIndicator(), sendResponse(), supportsStreaming
G5: Update docs/SECURITY.md with hardening checklist reflecting all new middleware

Build tests in tests/test_security_hardening.py.
Run tests with: PYTHONPATH=. .venv/bin/python -m pytest tests/test_security_hardening.py -v
All tests must pass."

# Final summary
notify "🏁 ALL PHASES COMPLETE
⏰ $(date '+%Y-%m-%d %H:%M %Z')

Next: commit and push results"

# Commit everything
cd "$PROJECT_DIR"
git add -A -- . ':!.claude/settings.local.json' ':!ACTION-PLAN.md'
git commit -m "Phase D/E/F/G: job orchestration, setup wizard, model routing, security hardening

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" 2>&1 || true

notify "📦 Changes committed. Run 'git push origin main' to publish."
