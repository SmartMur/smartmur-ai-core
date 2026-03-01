# Cron Job Manager

Manage scheduled jobs for Claude Superpowers.

## Usage
- List jobs: `cd ~/Projects/claude-superpowers && .venv/bin/claw cron list`
- Add job: `cd ~/Projects/claude-superpowers && .venv/bin/claw cron add "name" "schedule" "command" --type shell`
- Remove: `cd ~/Projects/claude-superpowers && .venv/bin/claw cron remove JOB_ID`
- View logs: `cd ~/Projects/claude-superpowers && .venv/bin/claw cron logs JOB_ID`
- Force run: `cd ~/Projects/claude-superpowers && .venv/bin/claw cron run JOB_ID`

## Schedule Formats
- Interval: "every 30m", "every 6h", "every 1d"
- Daily: "daily at 09:00"
- Cron: "0 */6 * * *"

## Job Types
- shell: Run a shell command
- claude: Spawn `claude -p "prompt"` headless
- webhook: POST to a URL
- skill: Run a registered skill by name
