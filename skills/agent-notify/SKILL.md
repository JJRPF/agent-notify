---
name: agent-notify
description: >
  Send push notifications to the user's mobile phone and desktop, or configure
  24/7 cloud monitors (GitHub PRs, workflows, branch commits, HTTP endpoints)
  that alert the user even when this machine is asleep. Use when finishing
  long-running tasks, when blocked requiring user attention/decision, or when
  asked to watch external repositories, issues, PRs, or websites.
---

# Agent-Notify Skill

Send notifications to the user's mobile phone (via [ntfy.sh](https://ntfy.sh)) and desktop (via `notify-send`), or manage 24/7 background monitors running on GitHub Actions.

---

## 1. When to Send Direct Pings

Notification hygiene is essential. Never spam the user with trivial status updates.

### ALWAYS Notify:
- **Task Completion**: A long build, test suite execution (>10 tests), or asynchronous subagent workflow finishes and the user may be away from keyboard.
- **Blocked on User Decision**: The agent needs confirmation, hit an ambiguous decision, or encountered merge conflicts requiring human judgment.
- **Critical Failure**: Unhandled crash or fatal errors that halted progress.

### DO NOT Notify:
- Step-by-step progress during active back-and-forth interactive pair-programming.
- Informational output already visible in the chat transcript.

---

## 2. Direct Pings (`agent-notify send`)

The `agent-notify` CLI is installed in `$PATH` (`~/.local/bin/agent-notify`).

### Quick Ping
```bash
agent-notify "Test suite finished: 53 tests passed"
```

### Full Alert with Priority and Click Link
```bash
agent-notify send \
  --title "PR Needs Review" \
  --message "All tests passed and PR #380 is ready for your sign-off." \
  --priority high \
  --tags "robot,white_check_mark" \
  --click "https://github.com/omacom/omarchy-mac/pull/380"
```

### Priority Guidelines:
| Priority | Flag | When to Use | Phone Behavior |
| :--- | :--- | :--- | :--- |
| `urgent` / `max` | `-p urgent` | Critical failure or blocking decision required | Loud ringtone, persistent banner |
| `high` | `-p high` | Long task completed, test suite finished | Banner popup, vibration |
| `default` | `-p default` | Standard informational milestone | Standard banner |
| `low` | `-p low` | Background status or silent receipt | Silent lock screen entry |

---

## 3. Managing 24/7 Cloud Monitors (`agent-notify watch`)

Cloud monitors run on GitHub Actions runners every 20 minutes and do NOT require this laptop to be awake or powered on.

### List Active Monitors
```bash
agent-notify watch list
```

### Add a GitHub PR Monitor
Watches for merge events, closures, and new review comments:
```bash
agent-notify watch add pr \
  --id "my-feature-pr" \
  --name "Feature X PR" \
  --repo "owner/repo" \
  --pr 123
```

### Add a GitHub Workflow Monitor
Watches for workflow conclusions (e.g. alerts when a broken build turns green):
```bash
agent-notify watch add workflow \
  --id "main-ci" \
  --name "Main CI Build" \
  --repo "owner/repo" \
  --workflow "ci.yml" \
  --branch "main"
```

### Add a GitHub Branch Monitor
Watches for new commits on a branch:
```bash
agent-notify watch add branch \
  --id "upstream-dev" \
  --name "Upstream Dev Commits" \
  --repo "owner/repo" \
  --branch "dev"
```

### Add an HTTP Health Ping
Watches for website uptime or API status changes:
```bash
agent-notify watch add ping \
  --id "api-health" \
  --name "Production API Health" \
  --url "https://api.example.com/healthz" \
  --expected-status 200
```

### Enable, Mute, or Delete Monitors
```bash
agent-notify watch disable <id>   # Mute alerts without deleting
agent-notify watch enable <id>    # Resume alerts
agent-notify watch remove <id>    # Delete permanently
```
*(All `agent-notify watch` commands automatically commit and push to the GitHub cloud runner).*

---

## 4. Phone Two-Way Remote Control

The user can send text commands directly in the `ntfy` app compose box to control monitors from anywhere:
- `unsub <id>` or `unsub <pr_number>`: Mutes a monitor (e.g. `unsub 380`).
- `sub <id>`: Resumes a muted monitor.
- `list` or `status`: Replies with a list of all monitors and their active/muted status.
- `help`: Replies with command help.
