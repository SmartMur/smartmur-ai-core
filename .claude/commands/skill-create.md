# Create a New Skill

Help the user create a new Claude Superpowers skill.

## Process
1. Ask for: skill name, description, script type (bash or python), any special permissions needed
2. Run the scaffolder: `cd ~/Projects/claude-superpowers && python3 -c "from superpowers.skill_creator import create_skill; print(create_skill('$NAME', '$DESCRIPTION', script_type='$TYPE'))"`
3. Write the actual implementation into the generated run.sh or run.py
4. Run `cd ~/Projects/claude-superpowers && python3 -c "from superpowers.skill_registry import SkillRegistry; r=SkillRegistry(); r.sync_slash_commands()"` to wire up the slash command
5. Verify with: `ls -la ~/.claude/commands/` to confirm the symlink exists

## Skill Directory Structure
```
skills/{name}/
├── skill.yaml      # Manifest
├── command.md       # Slash command prompt
└── run.sh|run.py    # Implementation
```

## Guidelines
- Skill names: kebab-case
- Scripts must be idempotent where possible
- Include error handling and meaningful exit codes
- Document what the skill does in command.md
