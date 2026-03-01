Run a multi-step workflow.

Usage: /workflow <command> [args]

Examples:
  /workflow list                    — list available workflows
  /workflow show deploy             — show steps in the deploy workflow
  /workflow run deploy              — execute the deploy workflow
  /workflow run deploy --dry-run    — preview without executing
  /workflow validate deploy         — check for errors
  /workflow init                    — install built-in templates (deploy, backup, morning-brief)

Now run:
```
cd ~/Projects/claude-superpowers && claw workflow $ARGUMENTS
```
