#!/usr/bin/env bash
# ops-report — Gathers system status from all subsystems and sends to Telegram
# Robust: individual check failures are noted in report, never abort.

set -uo pipefail

source "$(dirname "$0")/../lib.sh"
load_env

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-${TELEGRAM_DEFAULT_CHAT_ID:-}}"

if [[ -z "$TELEGRAM_BOT_TOKEN" ]]; then
    error "TELEGRAM_BOT_TOKEN not set"
    exit 1
fi

if [[ -z "$CHAT_ID" ]]; then
    error "TELEGRAM_CHAT_ID or TELEGRAM_DEFAULT_CHAT_ID not set"
    exit 1
fi

REPORT_TIME="$(timestamp_utc)"

########################################
# 1. Docker containers
########################################
gather_docker() {
    local all_output
    all_output=$(docker ps -a --format "{{.Names}}\t{{.Status}}" 2>/dev/null) || { echo "Docker: unavailable"; return; }

    local total running stopped
    total=$(echo "$all_output" | wc -l | tr -d ' ')
    running=$(docker ps --format "{{.Names}}" 2>/dev/null | wc -l | tr -d ' ')
    stopped=$((total - running))

    local docker_line
    if [[ "$stopped" -eq 0 ]]; then
        docker_line="Docker: ${running}/${total} running"
    else
        docker_line="Docker: ${running}/${total} running, ${stopped} stopped"
    fi
    echo "$docker_line"

    # List stopped containers if any
    if [[ "$stopped" -gt 0 ]]; then
        local stopped_list
        stopped_list=$(docker ps -a --filter "status=exited" --filter "status=dead" --filter "status=created" --format "  - {{.Names}} ({{.Status}})" 2>/dev/null | head -5)
        if [[ -n "$stopped_list" ]]; then
            echo "$stopped_list"
        fi
    fi
}

########################################
# 2. Disk usage
########################################
gather_disk() {
    local root_pct home_pct
    root_pct=$(df -h / 2>/dev/null | awk 'NR==2 {print $5}') || root_pct="?"
    home_pct=$(df -h /home 2>/dev/null | awk 'NR==2 {print $5}') || home_pct="?"
    echo "Disk: / ${root_pct} | /home ${home_pct}"
}

########################################
# 3. Memory
########################################
gather_memory() {
    local used total pct
    used=$(free -h 2>/dev/null | awk '/^Mem:/ {print $3}') || { echo "Memory: unavailable"; return; }
    total=$(free -h 2>/dev/null | awk '/^Mem:/ {print $2}')
    pct=$(free 2>/dev/null | awk '/^Mem:/ {printf "%.0f", $3/$2*100}')
    echo "Memory: ${used}/${total} (${pct}%)"
}

########################################
# 4. Load average
########################################
gather_load() {
    local load
    load=$(uptime 2>/dev/null | sed 's/.*load average: //' | tr -d ',') || load="?"
    echo "Load: ${load}"
}

########################################
# 5. Service checks  (uses check_http from lib.sh)
########################################
svc_status() {
    local url="$1" timeout="${2:-3}"
    if check_http "$url" "$timeout"; then echo "ok"; else echo "down"; fi
}

gather_services() {
    local dashboard_status gateway_status redis_status tgbot_status

    dashboard_status=$(svc_status "http://localhost:8200/health" 3)
    gateway_status=$(svc_status "http://localhost:8100/health" 3)

    redis_ping=$(docker exec claude-superpowers-redis-1 redis-cli ping 2>/dev/null) || redis_ping="FAIL"
    if [[ "$redis_ping" == "PONG" ]]; then redis_status="ok"; else redis_status="down"; fi

    tgbot_running=$(docker ps --filter "name=telegram-bot" --format "{{.Status}}" 2>/dev/null)
    if [[ -n "$tgbot_running" && "$tgbot_running" == *"Up"* ]]; then tgbot_status="ok"; else tgbot_status="down"; fi

    local svc_block=""
    for pair in "Dashboard (8200):$dashboard_status" "Gateway (8100):$gateway_status" "Redis:$redis_status" "Telegram Bot:$tgbot_status"; do
        local svc_name="${pair%%:*}"
        local svc_st="${pair##*:}"
        if [[ "$svc_st" == "ok" ]]; then
            svc_block+="  ✅ ${svc_name}"$'\n'
        else
            svc_block+="  ❌ ${svc_name} — ${svc_st}"$'\n'
        fi
    done
    # Trim trailing newline
    echo "${svc_block%$'\n'}"
}

########################################
# 6. Recent errors (docker logs, last hour)
########################################
gather_issues() {
    local issues=""
    local issue_count=0

    local containers
    containers=$(docker ps --format "{{.Names}}" 2>/dev/null) || { echo "  - Docker unavailable"; return; }

    while IFS= read -r cname; do
        [[ -z "$cname" ]] && continue

        local restart_count
        restart_count=$(docker inspect --format '{{.RestartCount}}' "$cname" 2>/dev/null) || continue
        if [[ "$restart_count" =~ ^[0-9]+$ ]] && [[ "$restart_count" -gt 0 ]]; then
            issues+="  - ${cname}: ${restart_count} restart(s)"$'\n'
            issue_count=$((issue_count + 1))
        fi

        local err_count
        err_count=$(docker logs --since 1h "$cname" 2>&1 | grep -ciE '(error|exception|fatal|oom|killed|panic)' 2>/dev/null) || err_count=0
        if [[ "$err_count" -gt 5 ]]; then
            issues+="  - ${cname}: ${err_count} error lines (last hour)"$'\n'
            issue_count=$((issue_count + 1))
        fi

        if [[ "$issue_count" -ge 8 ]]; then
            issues+="  - ... (truncated)"$'\n'
            break
        fi
    done <<< "$containers"

    if [[ -z "$issues" ]]; then
        echo "  None"
    else
        echo "$issues" | sed '/^$/d'
    fi
}

########################################
# 7. Cron jobs count
########################################
gather_cron() {
    if [[ -f "$PROJECT_DIR/.venv/bin/claw" ]]; then
        local jobs_count
        jobs_count=$(cd "$PROJECT_DIR" && PYTHONPATH="$PROJECT_DIR" "$PROJECT_DIR/.venv/bin/claw" cron list 2>/dev/null | grep -c "│" 2>/dev/null) || jobs_count="0"
        if [[ "$jobs_count" -gt 0 ]]; then
            jobs_count=$((jobs_count > 2 ? jobs_count - 2 : 0))
        fi
        echo "Cron: ${jobs_count} jobs configured"
    else
        echo "Cron: unavailable"
    fi
}

########################################
# 8. Skills count
########################################
gather_skills() {
    local skill_count
    skill_count=$(ls -d "$PROJECT_DIR/skills"/*/skill.yaml 2>/dev/null | wc -l | tr -d ' ')
    echo "Skills: ${skill_count} installed"
}

########################################
# Build the report
########################################
echo "Gathering ops data..."

DOCKER_INFO=$(gather_docker)
DISK_INFO=$(gather_disk)
MEMORY_INFO=$(gather_memory)
LOAD_INFO=$(gather_load)
SERVICES_INFO=$(gather_services)
ISSUES_INFO=$(gather_issues)
CRON_INFO=$(gather_cron)
SKILLS_INFO=$(gather_skills)

DOCKER_SUMMARY=$(echo "$DOCKER_INFO" | head -1)
DOCKER_STOPPED=$(echo "$DOCKER_INFO" | tail -n +2)

REPORT="📊 OPS REPORT
🕐 ${REPORT_TIME}

🐳 ${DOCKER_SUMMARY}"

if [[ -n "$DOCKER_STOPPED" ]]; then
    REPORT+="
${DOCKER_STOPPED}"
fi

REPORT+="
💾 ${DISK_INFO}
🧠 ${MEMORY_INFO}
⚡ ${LOAD_INFO}

🤖 Services:
${SERVICES_INFO}

⚠️ Issues (last hour):
${ISSUES_INFO}

📋 ${CRON_INFO}
🔧 ${SKILLS_INFO}"

########################################
# Send to Telegram
########################################
echo ""
echo "--- Report Preview ---"
echo "$REPORT"
echo "--- End Preview ---"
echo ""

echo "Sending to Telegram (chat_id=${CHAT_ID})..."

RESPONSE=$(curl -s -X POST \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${REPORT}" \
    -d "disable_web_page_preview=true" \
    2>&1)

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "Telegram report sent successfully."
else
    warn "WARNING: Failed to send Telegram message"
    echo "Response: $RESPONSE" >&2
fi

########################################
# Send email report
########################################
EMAIL_TO="${OPS_REPORT_EMAIL:-}"
SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASS="${SMTP_PASS:-}"
SMTP_FROM="${SMTP_FROM:-${SMTP_USER}}"

if [[ -n "$SMTP_USER" && -n "$SMTP_PASS" && -n "$SMTP_HOST" && -n "$EMAIL_TO" ]]; then
    echo "Sending email report to ${EMAIL_TO}..."

    EMAIL_BODY=$(echo "$REPORT" | sed 's/[📊🕐🐳💾🧠⚡🤖✅❌⚠️📋🔧]//g' | sed 's/^  /    /g')

    DOCKER_SHORT=$(echo "$DOCKER_SUMMARY" | head -1)
    EMAIL_SUBJECT="Ops Report ${REPORT_TIME} — ${DOCKER_SHORT}"

    python3 -c "
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

msg = MIMEMultipart('alternative')
msg['Subject'] = '''${EMAIL_SUBJECT}'''
msg['From'] = '${SMTP_FROM}'
msg['To'] = '${EMAIL_TO}'

body = '''${EMAIL_BODY}'''

# Plain text
msg.attach(MIMEText(body, 'plain'))

# HTML version
html_body = '<html><body><pre style=\"font-family: monospace; font-size: 14px; line-height: 1.5;\">' + body.replace('<', '&lt;').replace('>', '&gt;') + '</pre></body></html>'
msg.attach(MIMEText(html_body, 'html'))

try:
    with smtplib.SMTP('${SMTP_HOST}', ${SMTP_PORT}) as server:
        server.starttls()
        server.login('${SMTP_USER}', '${SMTP_PASS}')
        server.sendmail('${SMTP_FROM}', '${EMAIL_TO}', msg.as_string())
    print('Email sent successfully.')
except Exception as e:
    print(f'WARNING: Email failed: {e}', file=sys.stderr)
" 2>&1

else
    echo "Email skipped — SMTP not configured (set SMTP_USER, SMTP_PASS, SMTP_HOST in .env)"
fi

exit 0
