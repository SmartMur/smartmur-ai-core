#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# enable-branch-protection.sh
#
# Enables branch protection rules on all 10 smartmur GitHub repos.
# Requires a GitHub Personal Access Token (PAT) with `repo` scope.
#
# Usage:
#   ./enable-branch-protection.sh <GITHUB_PAT>
#   GITHUB_TOKEN=ghp_xxx ./enable-branch-protection.sh
###############################################################################

# --- Token resolution ---
TOKEN="${1:-${GITHUB_TOKEN:-}}"

if [[ -z "$TOKEN" ]]; then
  echo "ERROR: No GitHub token provided."
  echo ""
  echo "Usage:"
  echo "  $0 <GITHUB_PAT>"
  echo "  GITHUB_TOKEN=ghp_xxx $0"
  echo ""
  echo "Create a token at: https://github.com/settings/tokens"
  echo "Required scope: repo (Full control of private repositories)"
  exit 1
fi

# --- Configuration ---
OWNER="smartmur"
API_BASE="https://api.github.com"

# repo:branch pairs
declare -a REPOS=(
  "k3s-cluster:main"
  "homelab:main"
  "dotfiles:main"
  "home_media:master"
  "Lighthouse-AI:main"
  "Smoke:main"
  "design-os:main"
  "claude-code-tresor:main"
  "agent-os:main"
  "claude-code-skill-factory:dev"
)

# Branch protection payload
read -r -d '' PROTECTION_BODY <<'PAYLOAD' || true
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
PAYLOAD

# --- Validate token by checking auth ---
echo "Validating GitHub token..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "$API_BASE/user")

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "ERROR: Token validation failed (HTTP $HTTP_CODE)."
  echo "Make sure your PAT is valid and has the 'repo' scope."
  exit 1
fi
echo "Token is valid."
echo ""

# --- Apply branch protection to each repo ---
SUCCESS=0
FAILURE=0
TOTAL=${#REPOS[@]}

for entry in "${REPOS[@]}"; do
  REPO="${entry%%:*}"
  BRANCH="${entry##*:}"
  FULL_NAME="${OWNER}/${REPO}"
  URL="${API_BASE}/repos/${FULL_NAME}/branches/${BRANCH}/protection"

  printf "%-45s " "[${FULL_NAME}] branch '${BRANCH}'..."

  RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X PUT \
    -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -d "$PROTECTION_BODY" \
    "$URL")

  # Extract HTTP status code (last line) and response body (everything else)
  HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
  BODY=$(echo "$RESPONSE" | sed '$d')

  if [[ "$HTTP_STATUS" == "200" ]]; then
    echo "OK (protected)"
    SUCCESS=$((SUCCESS + 1))
  else
    # Extract error message from JSON response
    ERROR_MSG=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message','unknown error'))" 2>/dev/null || echo "HTTP $HTTP_STATUS")
    echo "FAILED -- $ERROR_MSG"
    FAILURE=$((FAILURE + 1))
  fi
done

# --- Summary ---
echo ""
echo "=============================="
echo "  Branch Protection Summary"
echo "=============================="
echo "  Total repos:  $TOTAL"
echo "  Succeeded:    $SUCCESS"
echo "  Failed:       $FAILURE"
echo "=============================="

if [[ "$FAILURE" -gt 0 ]]; then
  echo ""
  echo "Some repos failed. Common causes:"
  echo "  - Repo does not exist or you lack admin access"
  echo "  - Branch does not exist yet (empty repo)"
  echo "  - PAT missing 'repo' scope"
  exit 1
fi

echo ""
echo "All repos protected successfully."
