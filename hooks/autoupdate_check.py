#!/usr/bin/env python3
"""SessionStart hook: nudge the user to enable marketplace auto-update for `plaiiin-status`.

`plaiiin-status` changes frequently, so a stale install is easy to end up with.
If auto-update is NOT enabled for the `plaiiin-status` marketplace in any settings scope, emit
an `additionalContext` note so the assistant reminds the user. Silent when enabled.
Never fails the session (any error → no output, exit 0).
"""
import json
import os
import sys

MARKETPLACE = "plaiiin-status"


def _autoupdate_enabled():
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".claude", "settings.json"),
        os.path.join(home, ".claude", "settings.local.json"),
    ]
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        candidates += [
            os.path.join(proj, ".claude", "settings.json"),
            os.path.join(proj, ".claude", "settings.local.json"),
        ]
    for path in candidates:
        try:
            with open(path) as fh:
                data = json.load(fh)
        except Exception:
            continue
        entry = data.get("extraKnownMarketplaces", {}).get(MARKETPLACE, {})
        if isinstance(entry, dict) and entry.get("autoUpdate") is True:
            return True
    return False


def main():
    try:
        if _autoupdate_enabled():
            return
        msg = (
            "NOTE for the assistant — mention this to the user once, briefly: the "
            "`plaiiin-status` plugin marketplace does NOT have auto-update enabled here, and "
            "`plaiiin-status` changes frequently, so this machine may be on a stale "
            "version. To stay current: open /plugin -> Marketplaces -> plaiiin-status -> "
            "Enable auto-update (or add \"autoUpdate\": true to the plaiiin-status entry under "
            "extraKnownMarketplaces in ~/.claude/settings.json), then run "
            "/plugin update plaiiin-status@plaiiin-status to pull the latest now."
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": msg,
            }
        }))
    except Exception:
        pass  # never break a session over a reminder


if __name__ == "__main__":
    main()
    sys.exit(0)
