# Remember

Store a persistent memory for future sessions.

## Usage
`/remember "key" "value"`

## Examples
- `/remember "truenas-ssh" "ray@192.168.13.69, root needs pubkey"`
- `/remember "pve1-ip" "192.168.30.100" --category fact --tags infra,proxmox`
- `/remember "prefer-ruff" "Use ruff instead of flake8 for linting" --category preference`

## Implementation
Run: `cd ~/Projects/claude-superpowers && .venv/bin/claw memory remember $ARGUMENTS`
