#!/bin/bash
set -euo pipefail

NTFY_TOPIC="${NTFY_TOPIC:-jjr-omarchy-pr380}"
STATE_FILE="${STATE_FILE:-state.json}"
REPO="omacom/omarchy-mac"
PR_NUMBER="380"

AUTH_HEADER=()
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer $GITHUB_TOKEN")
fi

send_notification() {
  local title="$1"
  local message="$2"
  local priority="${3:-default}"
  local tags="${4:-bell}"
  local click="${5:-https://github.com/$REPO/pull/$PR_NUMBER}"

  echo "--> Sending notification: [$title] $message"
  curl -s \
    -H "Title: $title" \
    -H "Priority: $priority" \
    -H "Tags: $tags" \
    -H "Click: $click" \
    -d "$message" \
    "https://ntfy.sh/$NTFY_TOPIC" >/dev/null || echo "Warning: failed to send push notification" >&2
}

# 1. Initialize state if missing
if [[ ! -f "$STATE_FILE" ]]; then
  cat <<'EOF' > "$STATE_FILE"
{
  "quattro_sha": "",
  "quattro_msg": "",
  "quattro_vm_id": 0,
  "quattro_vm_conclusion": "",
  "latest_vm_id": 0,
  "latest_vm_conclusion": "failure",
  "pr_state": "open",
  "pr_merged": false,
  "pr_comments": 4,
  "last_checked": ""
}
EOF
fi

prev_quattro_sha=$(jq -r '.quattro_sha // ""' "$STATE_FILE")
prev_quattro_vm_id=$(jq -r '.quattro_vm_id // 0' "$STATE_FILE")
prev_quattro_vm_conclusion=$(jq -r '.quattro_vm_conclusion // ""' "$STATE_FILE")
prev_latest_vm_id=$(jq -r '.latest_vm_id // 0' "$STATE_FILE")
prev_latest_vm_conclusion=$(jq -r '.latest_vm_conclusion // ""' "$STATE_FILE")
prev_pr_state=$(jq -r '.pr_state // "open"' "$STATE_FILE")
prev_pr_merged=$(jq -r '.pr_merged // false' "$STATE_FILE")
prev_pr_comments=$(jq -r '.pr_comments // 0' "$STATE_FILE")

echo "Previous state loaded:"
echo "  quattro_sha: $prev_quattro_sha"
echo "  latest_vm_conclusion: $prev_latest_vm_conclusion"
echo "  pr_state: $prev_pr_state (merged: $prev_pr_merged, comments: $prev_pr_comments)"

# 2. Fetch current status from GitHub API
echo "Fetching latest quattro commit..."
quattro_json=$(curl -s "${AUTH_HEADER[@]}" "https://api.github.com/repos/$REPO/commits/quattro")
curr_quattro_sha=$(echo "$quattro_json" | jq -r '.sha // ""')
curr_quattro_msg=$(echo "$quattro_json" | jq -r '.commit.message // ""' | head -n 1)

echo "Fetching latest Install VM workflow run (quattro)..."
quattro_vm_json=$(curl -s "${AUTH_HEADER[@]}" "https://api.github.com/repos/$REPO/actions/workflows/install-vm.yml/runs?branch=quattro&per_page=1")
curr_quattro_vm_id=$(echo "$quattro_vm_json" | jq -r '.workflow_runs[0].id // 0')
curr_quattro_vm_conclusion=$(echo "$quattro_vm_json" | jq -r '.workflow_runs[0].conclusion // ""')

echo "Fetching latest overall Install VM workflow run..."
overall_vm_json=$(curl -s "${AUTH_HEADER[@]}" "https://api.github.com/repos/$REPO/actions/workflows/install-vm.yml/runs?per_page=1")
curr_latest_vm_id=$(echo "$overall_vm_json" | jq -r '.workflow_runs[0].id // 0')
curr_latest_vm_conclusion=$(echo "$overall_vm_json" | jq -r '.workflow_runs[0].conclusion // ""')
curr_latest_vm_branch=$(echo "$overall_vm_json" | jq -r '.workflow_runs[0].head_branch // ""')

echo "Fetching PR #$PR_NUMBER status..."
pr_json=$(curl -s "${AUTH_HEADER[@]}" "https://api.github.com/repos/$REPO/pulls/$PR_NUMBER")
curr_pr_state=$(echo "$pr_json" | jq -r '.state // "open"')
curr_pr_merged=$(echo "$pr_json" | jq -r '.merged // false')
curr_pr_comments=$(echo "$pr_json" | jq -r '.comments // 0')
curr_pr_title=$(echo "$pr_json" | jq -r '.title // "fix(bluetooth): power off adapters via BlueZ before rfkill block"')

state_changed=false

# 3. Check for events

# Event 1: PR merged!
if [[ "$prev_pr_merged" != "true" && "$curr_pr_merged" == "true" ]]; then
  send_notification \
    "PR #$PR_NUMBER MERGED! 🎉" \
    "Your PR '$curr_pr_title' has been merged into quattro by maintainers!" \
    "max" \
    "tada,partying_face,rocket" \
    "https://github.com/$REPO/pull/$PR_NUMBER"
  state_changed=true

# Event 2: PR closed without merge
elif [[ "$prev_pr_state" == "open" && "$curr_pr_state" == "closed" && "$curr_pr_merged" != "true" ]]; then
  send_notification \
    "PR #$PR_NUMBER Closed" \
    "PR #$PR_NUMBER was closed." \
    "high" \
    "warning,x" \
    "https://github.com/$REPO/pull/$PR_NUMBER"
  state_changed=true
fi

# Event 3: New comments or reviews on PR
if (( prev_pr_comments > 0 && curr_pr_comments > prev_pr_comments )); then
  new_count=$((curr_pr_comments - prev_pr_comments))
  send_notification \
    "New Comment on PR #$PR_NUMBER 💬" \
    "PR #$PR_NUMBER received $new_count new comment(s) (total: $curr_pr_comments)." \
    "high" \
    "speech_balloon,bell" \
    "https://github.com/$REPO/pull/$PR_NUMBER"
  state_changed=true
fi

# Event 4: New commit on quattro
if [[ -n "$prev_quattro_sha" && -n "$curr_quattro_sha" && "$prev_quattro_sha" != "$curr_quattro_sha" ]]; then
  send_notification \
    "New Commit on quattro 📦" \
    "Commit: $curr_quattro_msg (${curr_quattro_sha:0:8})" \
    "default" \
    "package,git" \
    "https://github.com/$REPO/commits/quattro"
  state_changed=true
fi

# Event 5: Install VM is GREEN (either on quattro or latest overall run)
if [[ "$prev_latest_vm_conclusion" != "success" && "$curr_latest_vm_conclusion" == "success" ]]; then
  send_notification \
    "Install VM is now GREEN! ✅" \
    "The Install VM check succeeded on branch $curr_latest_vm_branch. Upstream omarchy-nvim break is fixed!" \
    "high" \
    "white_check_mark,apple" \
    "https://github.com/$REPO/actions/workflows/install-vm.yml"
  state_changed=true
fi

now_iso=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Save updated state
cat <<EOF > "$STATE_FILE"
{
  "quattro_sha": "$curr_quattro_sha",
  "quattro_msg": $(echo "$curr_quattro_msg" | jq -R .),
  "quattro_vm_id": $curr_quattro_vm_id,
  "quattro_vm_conclusion": "$curr_quattro_vm_conclusion",
  "latest_vm_id": $curr_latest_vm_id,
  "latest_vm_conclusion": "$curr_latest_vm_conclusion",
  "pr_state": "$curr_pr_state",
  "pr_merged": $curr_pr_merged,
  "pr_comments": $curr_pr_comments,
  "last_checked": "$now_iso"
}
EOF

echo "Check complete. State changed: $state_changed."
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "changed=$state_changed" >> "$GITHUB_OUTPUT"
fi
