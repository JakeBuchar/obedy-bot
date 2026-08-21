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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from email_sender import send_email
from render import render_html, render_text
from scrapers.choiceqr import fetch_choiceqr_menu
from scrapers.generic_html import fetch_generic_menu
from scrapers.menubot import fetch_menubot_menu

CONFIG_PATH = "config/restaurants.yaml"
PRAGUE = ZoneInfo("Europe/Prague")
# See daily-menu.yml for why two crons feed into this check.
TARGET_LOCAL_HOUR = 9
TARGET_LOCAL_MINUTE = 33


def is_matching_cron(cron: str, now: datetime) -> bool:
    """Is `cron` the one scheduled for Prague's currently active UTC offset?

    Deciding from the cron expression rather than from the clock keeps the
    send working when GitHub starts the job late, which it routinely does by
    half an hour or more.
    """
    cron_utc_hour = int(cron.split()[1])
    offset_hours = int(now.utcoffset().total_seconds() // 3600)
    return cron_utc_hour == (TARGET_LOCAL_HOUR - offset_hours) % 24


def should_send_now(now: datetime | None = None) -> bool:
    now = now or datetime.now(PRAGUE)

    cron = os.environ.get("GITHUB_EVENT_SCHEDULE", "").strip()
    if cron:
        return is_matching_cron(cron, now)

    # No cron expression available: fall back to the clock, accepting the
    # whole hour that starts at the target time. That still rules out the
    # other offset's run (exactly one hour off) while tolerating delay.
    target = now.replace(
        hour=TARGET_LOCAL_HOUR, minute=TARGET_LOCAL_MINUTE, second=0, microsecond=0
    )
    return timedelta(0) <= now - target < timedelta(hours=1)


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
        results.append(entry)
    return results


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    dry_run = "--dry-run" in sys.argv

    # The GitHub Actions workflow schedules cron triggers for both possible
    # UTC offsets of 9:33 Europe/Prague (CEST/CET) so delivery time doesn't
    # drift across DST changes; the one belonging to the inactive offset is
    # a no-op. Manual runs (workflow_dispatch) and local runs always go
    # through, so testing is never blocked by the time of day.
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not should_send_now():
        print("Skipping: this cron belongs to the other DST offset, not today's send.")
        return

    restaurants = load_restaurants()
    results = scrape_all(restaurants)

    generated_at = datetime.now(ZoneInfo("Europe/Prague"))
    text_body = render_text(results, generated_at)
    html_body = render_html(results, generated_at)

    if dry_run:
        print(text_body)
        return

    subject = f"Obědové menu – {datetime.now():%d.%m.%Y}"
    send_email(subject=subject, html_body=html_body, text_body=text_body)
    print(f"Sent menu email for {len(results)} restaurant(s).")


if __name__ == "__main__":
    main()
