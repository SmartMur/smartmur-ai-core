Send a message via the messaging gateway.

Usage: /msg <channel> "<target>" "<message>"

Examples:
  /msg slack "#homelab" "PVE1 backup complete"
  /msg telegram "123456789" "Disk usage at 90%"
  /msg discord "1234567890" "Deploy finished"
  /msg email "admin@example.com" "Subject\nBody here"

Profile-based (fan-out to multiple targets):
  claw msg notify critical "Service down on PVE1"
  claw msg notify daily-digest "All systems nominal"

Setup:
1. Add tokens to ~/.claude-superpowers/.env (SLACK_BOT_TOKEN, TELEGRAM_BOT_TOKEN, etc.)
2. Test: claw msg test slack
3. Configure profiles in ~/.claude-superpowers/profiles.yaml

Now run the following command to send the message:
```
cd ~/Projects/claude-superpowers && claw msg send $ARGUMENTS
```
