#!/usr/bin/env python3
"""
Agent-Notify: Generalized Cloud Watcher Engine
Evaluates monitors.json, ingests two-way commands from ntfy,
and sends phone push notifications when monitored conditions change.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

TOPIC = os.getenv("NTFY_TOPIC", "jjr-omarchy-pr380")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
MONITORS_FILE = os.getenv("MONITORS_FILE", "monitors.json")
STATE_FILE = os.getenv("STATE_FILE", "state.json")
NTFY_BASE_URL = os.getenv("NTFY_BASE_URL", "https://ntfy.sh")
BOT_HEADER_VALUE = "agent-notify-engine"


def ntfy_send(title, message, priority="default", tags="bell", click=None):
    """Sends a push notification to the configured ntfy topic."""
    url = f"{NTFY_BASE_URL}/{TOPIC}"
    print(f"--> [ntfy] [{priority}] {title}: {message}")
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
        "X-Sender": BOT_HEADER_VALUE,
        "User-Agent": "agent-notify-bot/1.0",
    }
    if click:
        headers["Click"] = click

    req = urllib.request.Request(url, data=message.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Warning: Failed to send push notification to {url}: {e}", file=sys.stderr)
        return False


def fetch_json(url, extra_headers=None):
    """Fetches JSON from a URL with optional GitHub Authorization headers."""
    headers = {
        "User-Agent": "agent-notify-engine/1.0",
        "Accept": "application/vnd.github+json"
    }
    if GITHUB_TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTPError fetching {url}: {e.code} {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


def fetch_ntfy_messages():
    """Polls recent messages from ntfy topic (buffer up to 12h)."""
    url = f"{NTFY_BASE_URL}/{TOPIC}/json?poll=1&since=12h"
    req = urllib.request.Request(url, headers={"User-Agent": "agent-notify-engine/1.0"})
    messages = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            for line in resp.read().decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("event") == "message":
                        messages.append(data)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Notice: Could not poll ntfy messages: {e}", file=sys.stderr)
    return messages


def find_monitor(monitors, query):
    """Fuzzy matches a monitor by exact ID, prefix, name, or PR/issue number."""
    q = query.strip().lower()
    if not q:
        return None

    # 1. Exact ID match
    for m in monitors:
        if m.get("id", "").lower() == q:
            return m

    # 2. PR / Issue number match
    for m in monitors:
        if str(m.get("pr", "")) == q or str(m.get("issue", "")) == q:
            return m

    # 3. Substring in ID
    for m in monitors:
        if q in m.get("id", "").lower():
            return m

    # 4. Substring in Name
    for m in monitors:
        if q in m.get("name", "").lower():
            return m

    return None


def process_phone_commands(monitors, state):
    """
    Checks for user commands sent from the phone in ntfy and updates monitors accordingly.
    Returns (monitors_modified, state_modified).
    """
    monitors_changed = False
    state_changed = False

    last_id = state.get("last_processed_command_id", "")
    messages = fetch_ntfy_messages()
    if not messages:
        return False, False

    # Filter out messages until we pass last_id (if present)
    new_messages = []
    if last_id:
        found_last = False
        for msg in messages:
            if found_last:
                new_messages.append(msg)
            elif msg.get("id") == last_id:
                found_last = True
        if not found_last:
            # If last_id wasn't found in current 12h buffer, process all messages that are newer than last_checked
            last_checked = state.get("last_checked", "")
            for msg in messages:
                msg_time = datetime.fromtimestamp(msg.get("time", 0), tz=timezone.utc).isoformat()
                if not last_checked or msg_time > last_checked:
                    new_messages.append(msg)
    else:
        new_messages = messages

    for msg in new_messages:
        msg_id = msg.get("id")
        content = (msg.get("message") or "").strip()
        tags = msg.get("tags") or []
        title = msg.get("title") or ""

        # Update last processed ID
        state["last_processed_command_id"] = msg_id
        state_changed = True

        # Skip messages generated by the bot itself
        if "agent-notify" in title.lower() or "Test Ping" in title:
            continue
        # If user published a message from phone, title is usually empty or matches user command
        if not content:
            continue

        print(f"Processing candidate command from phone: '{content}' (id={msg_id})")

        lower = content.lower()

        # Command: Unsubscribe / Mute
        unsub_match = re.match(r"^(?:unsubscribe|unsub|stop|mute|disable)\s*(.*)$", lower)
        if unsub_match:
            target_query = unsub_match.group(1).strip()
            if not target_query:
                ntfy_send(
                    "Command Help: Unsubscribe",
                    "Please specify which monitor to unsubscribe, e.g. 'unsub omarchy-pr380' or 'unsub 380'. Send 'list' to see active monitors.",
                    priority="default",
                    tags="information_source"
                )
                continue

            target = find_monitor(monitors, target_query)
            if target:
                target["enabled"] = False
                monitors_changed = True
                active_ids = [m["id"] for m in monitors if m.get("enabled", True)]
                ntfy_send(
                    f"Unsubscribed: {target['id']} 🔕",
                    f"Disabled alerts for '{target.get('name', target['id'])}'.\nActive remaining: {', '.join(active_ids) or 'none'}.\nSend 'sub {target['id']}' to re-enable.",
                    priority="default",
                    tags="mute,white_check_mark"
                )
            else:
                available = [m["id"] for m in monitors]
                ntfy_send(
                    "Monitor Not Found ❓",
                    f"Could not find monitor matching '{target_query}'.\nAvailable monitors: {', '.join(available)}",
                    priority="default",
                    tags="question"
                )
            continue

        # Command: Subscribe / Resume
        sub_match = re.match(r"^(?:subscribe|sub|start|resume|unmute|enable)\s*(.*)$", lower)
        if sub_match:
            target_query = sub_match.group(1).strip()
            if not target_query:
                ntfy_send(
                    "Command Help: Subscribe",
                    "Please specify which monitor to enable, e.g. 'sub omarchy-pr380'. Send 'list' to see all monitors.",
                    priority="default",
                    tags="information_source"
                )
                continue

            target = find_monitor(monitors, target_query)
            if target:
                target["enabled"] = True
                monitors_changed = True
                ntfy_send(
                    f"Subscribed: {target['id']} 🔔",
                    f"Alerts resumed for '{target.get('name', target['id'])}'.",
                    priority="default",
                    tags="bell,white_check_mark"
                )
            else:
                available = [m["id"] for m in monitors]
                ntfy_send(
                    "Monitor Not Found ❓",
                    f"Could not find monitor matching '{target_query}'.\nAvailable: {', '.join(available)}",
                    priority="default",
                    tags="question"
                )
            continue

        # Command: Status / List
        if lower in ("status", "list", "monitors", "ls"):
            lines = ["📋 Monitored Targets:"]
            for m in monitors:
                status_emoji = "🟢" if m.get("enabled", True) else "⚪ [Muted]"
                lines.append(f"{status_emoji} {m['id']}: {m.get('name', m['id'])}")
            lines.append("\nTip: Send 'unsub <id>' to mute, 'sub <id>' to resume.")
            ntfy_send(
                "Agent-Notify Status",
                "\n".join(lines),
                priority="default",
                tags="clipboard"
            )
            continue

        # Command: Help
        if lower in ("help", "?"):
            ntfy_send(
                "Agent-Notify Commands",
                "Available phone commands:\n• 'unsub <id>' - Stop alerts for a target\n• 'sub <id>' - Resume alerts for a target\n• 'list' - Show all monitors and status\n• 'help' - Show this guide",
                priority="default",
                tags="information_source"
            )
            continue

    return monitors_changed, state_changed


def check_github_pr(monitor, prev_state):
    repo = monitor["repo"]
    pr_num = monitor["pr"]
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
    data = fetch_json(url)
    if not data:
        return prev_state, False

    curr_state = data.get("state", "open")
    curr_merged = bool(data.get("merged", False))
    curr_comments = data.get("comments", 0)
    curr_title = data.get("title", f"PR #{pr_num}")
    html_url = data.get("html_url", f"https://github.com/{repo}/pull/{pr_num}")

    prev_merged = bool(prev_state.get("merged", False))
    prev_pr_state = prev_state.get("state", "open")
    prev_comments = prev_state.get("comments", 0)

    changed = False

    # Event 1: PR Merged!
    if not prev_merged and curr_merged:
        ntfy_send(
            f"PR #{pr_num} MERGED! 🎉",
            f"'{curr_title}' was merged into upstream repo {repo}!",
            priority="max",
            tags="tada,partying_face,rocket",
            click=html_url
        )
        changed = True

    # Event 2: Closed without merge
    elif prev_pr_state == "open" and curr_state == "closed" and not curr_merged:
        ntfy_send(
            f"PR #{pr_num} Closed",
            f"'{curr_title}' in {repo} was closed without merge.",
            priority="high",
            tags="warning,x",
            click=html_url
        )
        changed = True

    # Event 3: New comments
    elif prev_comments > 0 and curr_comments > prev_comments:
        new_cnt = curr_comments - prev_comments
        ntfy_send(
            f"New Comment on PR #{pr_num} 💬",
            f"PR #{pr_num} ('{curr_title}') received {new_cnt} new comment(s) (total: {curr_comments}).",
            priority="high",
            tags="speech_balloon,bell",
            click=html_url
        )
        changed = True

    new_state = {
        "state": curr_state,
        "merged": curr_merged,
        "comments": curr_comments,
        "title": curr_title,
    }
    return new_state, changed


def check_github_workflow(monitor, prev_state):
    repo = monitor["repo"]
    workflow = monitor["workflow"]
    branch = monitor.get("branch")

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=1"
    if branch:
        url += f"&branch={branch}"

    data = fetch_json(url)
    if not data or not data.get("workflow_runs"):
        return prev_state, False

    latest_run = data["workflow_runs"][0]
    run_id = latest_run.get("id")
    curr_conclusion = latest_run.get("conclusion") or latest_run.get("status")
    html_url = latest_run.get("html_url", f"https://github.com/{repo}/actions/workflows/{workflow}")
    run_name = monitor.get("name", f"{workflow} ({branch or 'default'})")

    prev_conclusion = prev_state.get("conclusion", "")
    changed = False

    if prev_conclusion and curr_conclusion != prev_conclusion:
        if curr_conclusion == "success":
            ntfy_send(
                f"{run_name} PASSED! ✅",
                f"Workflow run #{run_id} completed successfully!",
                priority="high",
                tags="white_check_mark,apple",
                click=html_url
            )
            changed = True
        elif curr_conclusion == "failure":
            ntfy_send(
                f"{run_name} FAILED ❌",
                f"Workflow run #{run_id} failed on branch {branch or 'main'}.",
                priority="high",
                tags="x,warning",
                click=html_url
            )
            changed = True

    new_state = {
        "run_id": run_id,
        "conclusion": curr_conclusion,
    }
    return new_state, changed


def check_github_branch(monitor, prev_state):
    repo = monitor["repo"]
    branch = monitor["branch"]
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"

    data = fetch_json(url)
    if not data:
        return prev_state, False

    curr_sha = data.get("sha", "")
    commit_msg = (data.get("commit", {}).get("message") or "").splitlines()[0]
    html_url = data.get("html_url", f"https://github.com/{repo}/commits/{branch}")

    prev_sha = prev_state.get("sha", "")
    changed = False

    if prev_sha and curr_sha != prev_sha:
        ntfy_send(
            f"New Commit on {branch} 📦",
            f"{commit_msg} ({curr_sha[:8]}) in {repo}",
            priority="default",
            tags="package,git",
            click=html_url
        )
        changed = True

    new_state = {
        "sha": curr_sha,
        "message": commit_msg,
    }
    return new_state, changed


def check_http_ping(monitor, prev_state):
    url = monitor["url"]
    expected = monitor.get("expected_status", 200)
    name = monitor.get("name", url)

    status_code = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agent-notify-engine/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            status_code = resp.status
    except urllib.error.HTTPError as e:
        status_code = e.code
    except Exception as e:
        status_code = 0

    prev_status = prev_state.get("status_code")
    changed = False

    if prev_status is not None and status_code != prev_status:
        if status_code == expected:
            ntfy_send(
                f"{name} RECOVERED 🟢",
                f"Service is back up with HTTP {status_code}.",
                priority="high",
                tags="white_check_mark,globe",
                click=url
            )
        else:
            ntfy_send(
                f"{name} DOWN / CHANGED 🔴",
                f"Expected status {expected}, received {status_code}.",
                priority="high",
                tags="warning,globe",
                click=url
            )
        changed = True

    new_state = {
        "status_code": status_code,
    }
    return new_state, changed


def main():
    print("=== Agent-Notify Cloud Watcher Starting ===")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Load monitors
    monitors = []
    if os.path.exists(MONITORS_FILE):
        with open(MONITORS_FILE, "r", encoding="utf-8") as f:
            monitors = json.load(f)
    else:
        print(f"Error: {MONITORS_FILE} not found.", file=sys.stderr)
        sys.exit(1)

    # 2. Load state
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    if "monitors" not in state:
        state["monitors"] = {}

    # 3. Process phone commands
    monitors_changed, state_changed = process_phone_commands(monitors, state)

    # 4. Check active monitors
    for m in monitors:
        m_id = m.get("id")
        if not m.get("enabled", True):
            print(f"Skipping muted monitor: {m_id}")
            continue

        m_type = m.get("type")
        prev_m_state = state["monitors"].get(m_id, {})
        new_m_state = prev_m_state
        m_changed = False

        print(f"Checking monitor [{m_type}]: {m_id}...")

        if m_type == "github_pr":
            new_m_state, m_changed = check_github_pr(m, prev_m_state)
        elif m_type == "github_workflow":
            new_m_state, m_changed = check_github_workflow(m, prev_m_state)
        elif m_type == "github_branch":
            new_m_state, m_changed = check_github_branch(m, prev_m_state)
        elif m_type == "http_ping":
            new_m_state, m_changed = check_http_ping(m, prev_m_state)
        else:
            print(f"Warning: Unknown monitor type '{m_type}' for {m_id}")

        state["monitors"][m_id] = new_m_state
        if m_changed:
            state_changed = True

    state["last_checked"] = now_iso

    # 5. Save files if changed
    if monitors_changed:
        print(f"Saving updated {MONITORS_FILE}...")
        with open(MONITORS_FILE, "w", encoding="utf-8") as f:
            json.dump(monitors, f, indent=2)
            f.write("\n")

    if state_changed or monitors_changed:
        print(f"Saving updated {STATE_FILE}...")
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")

    overall_changed = monitors_changed or state_changed
    print(f"=== Check Finished. Changes detected: {overall_changed} ===")

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output and os.path.exists(github_output):
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if overall_changed else 'false'}\n")


if __name__ == "__main__":
    main()
