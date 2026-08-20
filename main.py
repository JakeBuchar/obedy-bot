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
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

from email_sender import send_email
from render import render_html, render_text
from scrapers.choiceqr import fetch_choiceqr_menu
from scrapers.generic_html import fetch_generic_menu
from scrapers.menubot import fetch_menubot_menu

CONFIG_PATH = "config/restaurants.yaml"
TARGET_LOCAL_HOUR = 10  # see daily-menu.yml for why two crons feed into this check


def is_target_local_hour() -> bool:
    return datetime.now(ZoneInfo("Europe/Prague")).hour == TARGET_LOCAL_HOUR


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
    # UTC offsets of 10:00 Europe/Prague (CEST/CET) so delivery time doesn't
    # drift across DST changes; whichever one fires outside the real local
    # 10:00 hour is a no-op. Manual runs (workflow_dispatch) and local runs
    # always go through, so testing is never blocked by the time of day.
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not is_target_local_hour():
        print("Skipping: this cron fires at the other DST offset, not the local 10:00 send.")
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
