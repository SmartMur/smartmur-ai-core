# QA Guardian

Run the autonomous code quality guardian. Performs 12 checks across security, quality, test health, and efficiency.

## Usage

```
/qa-guardian
/qa-guardian --run-tests
```

## Checks

**Security (4):** shell=True, bare except, hardcoded secrets, eval/exec
**Quality (4):** long files (>400 lines), test coverage gaps, duplicate functions, TODO count
**Test Health (1):** pytest regression check against baseline
**Efficiency (3):** unused imports, empty files, dead modules

## Output

- Console: detailed findings list with file:line references
- Telegram: summary notification (error for criticals, info otherwise)
- Audit log: structured metadata in ~/.claude-superpowers/audit.log
- Report: JSON at ~/.claude-superpowers/qa-guardian/latest.json

## Exit Codes

- 0: clean (no critical or warning findings)
- 1: findings detected (critical or warning level)
- 2: execution error
