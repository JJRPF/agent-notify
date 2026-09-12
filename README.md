# 🔔 Agent-Notify

An extensible, 24/7 notification hub and cloud monitor for developers and autonomous AI agents.

- **Direct Agent Alerts**: Agents ping your phone immediately (e.g., long task finished, human input needed).
- **24/7 External Cloud Watchers**: Runs on GitHub Actions cloud runners every 20 minutes to monitor PRs, workflows, branches, and health checks—even when your laptop is in deep sleep.
- **Two-Way Phone Remote Control**: Send commands directly from the mobile app (e.g. `unsubscribe omarchy-pr380`, `status`) to dynamically mute or manage monitors.

---

## 📱 Quick Setup (30 Seconds)

1. Install the free **ntfy** app on iOS (App Store) or Android (Google Play / F-Droid), or open [ntfy.sh](https://ntfy.sh) in any browser.
2. Subscribe to your topic:
   ```text
   agent-notify
   ```
   *(Or your custom topic set in `NTFY_TOPIC`)*.

---

## 💬 Phone Commands (Two-Way Remote Control)

Type commands directly in the message compose box inside your topic feed:

| Command | Description | Example |
| :--- | :--- | :--- |
| `unsub <id>` | Mute alerts for a monitor (supports exact ID or PR number) | `unsub 380` or `unsub omarchy-pr380` |
| `sub <id>` | Resume alerts for a muted monitor | `sub omarchy-pr380` |
| `list` / `status` | View all active and muted monitors and their current states | `list` |
| `help` | Show command reference | `help` |

When the cloud watcher runs its cycle, it reads your command, updates `monitors.json`, and sends a confirmation alert back to your phone.

---

## 🛠️ Monitored Targets (`monitors.json`)

Monitors are defined declaratively in `monitors.json`:

```json
[
  {
    "id": "omarchy-pr380",
    "name": "Omarchy Bluetooth Poweroff PR #380",
    "type": "github_pr",
    "repo": "omacom/omarchy-mac",
    "pr": 380,
    "enabled": true
  },
  {
    "id": "quattro-vm",
    "name": "Omarchy Quattro Install VM",
    "type": "github_workflow",
    "repo": "omacom/omarchy-mac",
    "workflow": "install-vm.yml",
    "branch": "quattro",
    "enabled": true
  },
  {
    "id": "quattro-commits",
    "name": "Omarchy Quattro Branch Commits",
    "type": "github_branch",
    "repo": "omacom/omarchy-mac",
    "branch": "quattro",
    "enabled": true
  }
]
```

### Supported Types:
- `github_pr`: Monitors PR merge status, closures, new reviews, and comment counts.
- `github_workflow`: Monitors CI workflow run conclusions (`success`, `failure`).
- `github_branch`: Monitors branch HEAD commit changes.
- `http_ping`: Monitors HTTP status code / service availability.

---

## 💻 Local CLI (`agent-notify`)

Installable locally to `~/.local/bin/agent-notify`:

```bash
# Instant ping to phone and local desktop notification
agent-notify "Test suite finished successfully"

# High-priority alert with click-through URL and custom tags
agent-notify -t "PR Merged" -m "Upstream PR #380 has merged" -p high --tags tada --click "https://github.com/..."

# Manage cloud monitors locally
agent-notify watch list
agent-notify watch disable omarchy-pr380
agent-notify watch add pr --repo omacom/omarchy-mac --pr 400
```
