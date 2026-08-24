"""Entry point: load restaurant config, scrape each one, email the result.

Run locally for testing:
    $env:SMTP_HOST="smtp.gmail.com"
    $env:SMTP_USER="you@gmail.com"
    $env:SMTP_PASSWORD="<app password>"
    $env:MAIL_TO="you@gmail.com"
    python main.py

Add --dry-run to skip sending the email and just print the result.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

from email_sender import send_email
from render import render_html, render_text
from scrapers.choiceqr import fetch_choiceqr_menu
from scrapers.generic_html import fetch_generic_menu
from scrapers.menubot import fetch_menubot_menu

CONFIG_PATH = "config/restaurants.yaml"
PRAGUE = ZoneInfo("Europe/Prague")
TARGET_LOCAL_HOUR = 9
TARGET_LOCAL_MINUTE = 33


def seconds_until_target(now: datetime | None = None) -> float:
    """How long until today's send time in Prague; 0 if it already passed."""
    now = now or datetime.now(PRAGUE)
    target = now.replace(
        hour=TARGET_LOCAL_HOUR, minute=TARGET_LOCAL_MINUTE, second=0, microsecond=0
    )
    return max(0.0, (target - now).total_seconds())


def wait_for_target_time() -> None:
    """Hold the job until the send time.

    The workflow is scheduled well before the send time because GitHub only
    promises to start a scheduled run *at or after* its cron time and in
    practice runs up to an hour late. Waiting here means the delivery time
    depends on this clock rather than on when the runner happened to boot.
    """
    delay = seconds_until_target()
    if not delay:
        print("Runner started past the send time, sending right away.", flush=True)
        return
    print(
        f"Runner started early, waiting {delay / 60:.0f} min until "
        f"{TARGET_LOCAL_HOUR}:{TARGET_LOCAL_MINUTE:02d} Europe/Prague.",
        flush=True,
    )
    time.sleep(delay)


def load_restaurants(path: str = CONFIG_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        restaurants = yaml.safe_load(f)["restaurants"]
    return sorted(restaurants, key=lambda r: r["name"].casefold())


def scrape_all(restaurants: list[dict]) -> list[dict]:
    results = []
    for r in restaurants:
        entry = {
            "name": r["name"],
            "url": r.get("url"),
            "logo_url": r.get("logo_url"),
            "menu_image_url": None,
            "menu": None,
            "error": None,
        }
        try:
            adapter = r["adapter"]
            if adapter == "menubot":
                entry["menu"] = fetch_menubot_menu(r["menubot_hash"], lang=r.get("lang", "_a"))
            elif adapter == "html":
                entry["menu"] = fetch_generic_menu(
                    r["url"],
                    item_selector=r["item_selector"],
                    name_selector=r.get("name_selector", ""),
                    price_selector=r.get("price_selector", ""),
                    content_selector=r.get("content_selector", ""),
                    image_selector=r.get("image_selector", ""),
                )
            elif adapter == "choiceqr":
                entry["menu"] = fetch_choiceqr_menu(r["choiceqr_url"])
            else:
                raise ValueError(f"Unknown adapter '{adapter}'")
            # Menu.image_url is auto-discovered fresh on every scrape (see
            # generic_html.fetch_generic_menu), so the email always shows
            # whatever photo is currently live instead of a stale URL.
            entry["menu_image_url"] = entry["menu"].image_url or None
        except Exception as exc:  # noqa: BLE001 - we want to keep going for other restaurants
            entry["error"] = str(exc)
            print(f"ERROR {r['name']}: {exc}", flush=True)
        results.append(entry)
    return results


def scrape_errors(results: list[dict]) -> list[tuple[str, str]]:
    return [(r["name"], r["error"]) for r in results if r.get("error")]


def fail_if_errors(results: list[dict]) -> None:
    """Turn the GitHub Actions run red when a restaurant scrape failed.

    The email still goes out with whatever did scrape, so a single broken
    adapter doesn't silence the rest. A green checkmark used to mean "the
    script ran", including the 2026-08-24 scheduled runs that skipped the
    send entirely - so a failed restaurant has to be a failed job.
    """
    errors = scrape_errors(results)
    if not errors:
        return
    print(
        f"Failing the run: {len(errors)} restaurant(s) could not be scraped:",
        flush=True,
    )
    for name, message in errors:
        print(f"  - {name}: {message}", flush=True)
    sys.exit(1)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    dry_run = "--dry-run" in sys.argv

    # Only scheduled runs wait for the send time; manual runs
    # (workflow_dispatch) and local runs send immediately, so testing is
    # never blocked by the time of day.
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not dry_run:
        wait_for_target_time()

    # Scraped after the wait so the menus are as fresh as the email claims.
    restaurants = load_restaurants()
    results = scrape_all(restaurants)

    generated_at = datetime.now(ZoneInfo("Europe/Prague"))
    text_body = render_text(results, generated_at)
    html_body = render_html(results, generated_at)

    if dry_run:
        print(text_body)
        fail_if_errors(results)
        return

    subject = f"Obědové menu – {datetime.now():%d.%m.%Y}"
    try:
        send_email(subject=subject, html_body=html_body, text_body=text_body)
    except Exception as exc:  # noqa: BLE001 - surface SMTP/config failures as a red job
        print(f"Failed to send email: {exc}", flush=True)
        raise SystemExit(1) from exc
    print(f"Sent menu email for {len(results)} restaurant(s).")
    fail_if_errors(results)


if __name__ == "__main__":
    main()
