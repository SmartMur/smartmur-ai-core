# Recall

Retrieve a stored memory by key.

## Usage
`/recall "key"`

## Examples
- `/recall "truenas-ssh"`
- `/recall "pve1-ip" --category fact`

## Implementation
Run: `cd /home/ray/claude-superpowers && .venv/bin/claw memory recall $ARGUMENTS`
