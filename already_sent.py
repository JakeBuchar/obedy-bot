"""Guard against sending the menu twice on the same day.

A run started by the external scheduler asks the Actions API whether an
earlier run today already finished successfully, so a retried dispatch does
not deliver a second copy.

Note what "successful" leaves out: a run that emailed the menu and then
exited red over an unreachable restaurant does not count as sent. That is
why the crons, back when they existed, sent a second copy on 2026-09-10.
Clicking "Run workflow" by hand always sends - asking for a run means asking
for an email.
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

API_ROOT = "https://api.github.com"
DEFAULT_WORKFLOW_FILE = "daily-menu.yml"
PRAGUE = ZoneInfo("Europe/Prague")


def workflow_file() -> str:
    """Which workflow's successful runs count as "already sent".

    Praha and Kolín are separate workflows, so each must only look at its
    own runs. The workflow file name is passed in as WORKFLOW_FILE.
    """
    return os.environ.get("WORKFLOW_FILE", DEFAULT_WORKFLOW_FILE).strip() or DEFAULT_WORKFLOW_FILE


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
            f"{API_ROOT}/repos/{repository}/actions/workflows/{workflow_file()}/runs",
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
