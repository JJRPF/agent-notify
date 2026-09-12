# Omarchy PR & Upstream Watcher 🔔

Automated, 24/7 cloud watcher running on GitHub Actions. Monitors [omacom/omarchy-mac#380](https://github.com/omacom/omarchy-mac/pull/380) and upstream `quattro` branch status, sending push notifications directly to your phone via [ntfy.sh](https://ntfy.sh).

Runs continuously in the cloud even when your local machine is asleep or powered off.

---

## What It Monitors

1. **Upstream `Install VM` Status**: Alerts when the upstream package metadata break (`omarchy-nvim`) is resolved and `Install VM` turns green, signaling that it is safe to rebase.
2. **New Commits on `quattro`**: Alerts whenever maintainers land a new commit on the base branch.
3. **PR #380 Review & Comments**: Alerts when `@malik-na` or other maintainers post comments or submit reviews.
4. **PR #380 Merge**: Sends a high-priority celebration alert when PR #380 is merged!

---

## How to Receive Notifications on Your Phone

Push notifications are powered by [ntfy.sh](https://ntfy.sh), an open-source, free notification service requiring **no account or registration**.

1. **Install the App**:
   * **iOS**: [ntfy on App Store](https://apps.apple.com/app/ntfy/id1625396347)
   * **Android**: [ntfy on Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy) or [F-Droid](https://f-droid.org/en/packages/io.heckel.ntfy/)
2. **Subscribe to Your Topic**:
   * Open the app and tap **+** (Subscribe).
   * Topic name: `jjr-omarchy-pr380` (or your custom topic if configured).
3. **Test It**:
   * Run this in your terminal or trigger the workflow manually with the test option:
     ```bash
     curl -d "Test notification from your watcher!" https://ntfy.sh/jjr-omarchy-pr380
     ```

---

## How It Works

* A GitHub Actions workflow (`.github/workflows/monitor.yml`) runs every 20 minutes on GitHub's cloud runners.
* It compares live GitHub REST API responses against `state.json`.
* If a state change occurs (new comment, merge, or green VM run), it fires an HTTP push to `ntfy.sh` and commits the updated state back to this repository.
* If nothing changed, it exits immediately without modifying repository history.
