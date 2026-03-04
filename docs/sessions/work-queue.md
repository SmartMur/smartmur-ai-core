# Work Queue

## P0 (Do Next)

1. Harden command execution paths that currently use `shell=True`:
   - `superpowers/workflow/engine.py` (`_run_shell`)
   - `msg_gateway/inbound.py` (`TriggerManager.execute`, shell action)
2. Remove insecure default dashboard credentials from code defaults.
3. Add tests for `superpowers/intake.py` and `superpowers/cli_intake.py`.
4. Set `TELEGRAM_DEFAULT_CHAT_ID` so intake updates deliver immediately (no queue delay).

## P1

1. Add multi-agent role routing (planner/executor/verifier) with per-role skill mapping.
2. Add structured telemetry for intake lifecycle in audit log.
3. Add retry/backoff for Telegram notifications.

## P2

1. Migrate hardcoded home paths to config-driven workspace root.
2. Add docs page for intake orchestration and unattended operations.
