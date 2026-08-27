"""Guard against sending the menu twice on the same day.

The workflow schedules several crons because GitHub drops scheduled runs
outright when its scheduler is busy (2026-08-27 never fired at all). The
backups only help if they stay quiet once the menu is out, so each
scheduled run asks the Actions API whether an earlier run today already
finished successfully - every successful run has sent the email.
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

API_ROOT = "https://api.github.com"
WORKFLOW_FILE = "daily-menu.yml"
PRAGUE = ZoneInfo("Europe/Prague")


def already_sent_today(now: datetime | None = None, timeout: int = 15) -> bool:
    """Did an earlier run of this workflow already send today's email?

    Returns False whenever the answer can't be established (no token, API
    error, running outside Actions). A duplicate email is a far smaller
    problem than a missing one, so every uncertain case sends.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        return False

    now = now or datetime.now(PRAGUE)
    today = now.astimezone(PRAGUE).date()

    try:
        response = requests.get(
            f"{API_ROOT}/repos/{repository}/actions/workflows/{WORKFLOW_FILE}/runs",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"status": "success", "created": f">={today.isoformat()}", "per_page": 50},
            timeout=timeout,
        )
        response.raise_for_status()
        runs = response.json().get("workflow_runs", [])
    except Exception as exc:  # noqa: BLE001 - never let the check block the email
        print(f"Could not check earlier runs ({exc}); sending anyway.", flush=True)
        return False

    current_run_id = os.environ.get("GITHUB_RUN_ID")
    for run in runs:
        if str(run.get("id")) == current_run_id:
            continue
        started = run.get("run_started_at") or run.get("created_at")
        if not started:
            continue
        started_local = datetime.fromisoformat(started.replace("Z", "+00:00")).astimezone(PRAGUE)
        if started_local.date() == today:
            print(
                f"Menu already sent today by run #{run.get('run_number')} "
                f"at {started_local:%H:%M}; nothing to do.",
                flush=True,
            )
            return True
    return False
