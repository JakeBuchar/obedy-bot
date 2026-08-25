"""Entry point: load restaurant config, scrape each one, email the result.

Run locally for testing:
    $env:SMTP_HOST="smtp.gmail.com"
    $env:SMTP_USER="you@gmail.com"
    $env:SMTP_PASSWORD="<app password>"
    $env:MAIL_TO="you@gmail.com"
    python main.py

Add --dry-run to skip sending the email, print the text result, and write
email_preview.html (open that file to see the real HTML email). Add
--preview to also open email_preview.html in a browser.
"""
from __future__ import annotations

import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from email_sender import send_email
from render import render_html, render_text
from scrapers.choiceqr import fetch_choiceqr_menu
from scrapers.generic_html import fetch_generic_menu
from scrapers.govinda import fetch_govinda_menu
from scrapers.laventola import fetch_laventola_menu
from scrapers.menubot import fetch_menubot_menu

CONFIG_PATH = "config/restaurants.yaml"
PREVIEW_PATH = Path("email_preview.html")
PRAGUE = ZoneInfo("Europe/Prague")


def write_preview(html_body: str) -> Path:
    """Overwrite email_preview.html with the rendered HTML email body."""
    PREVIEW_PATH.write_text(html_body, encoding="utf-8")
    return PREVIEW_PATH.resolve()


def load_restaurants(path: str = CONFIG_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        restaurants = yaml.safe_load(f)["restaurants"]
    # Order is the yaml list order (Masaryčka is last on purpose).
    return restaurants


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
            elif adapter == "govinda":
                entry["menu"] = fetch_govinda_menu(r["url"])
            elif adapter == "laventola":
                entry["menu"] = fetch_laventola_menu(r["url"])
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

    preview = "--preview" in sys.argv
    dry_run = "--dry-run" in sys.argv or preview

    restaurants = load_restaurants()
    results = scrape_all(restaurants)

    generated_at = datetime.now(PRAGUE)
    text_body = render_text(results, generated_at)
    html_body = render_html(results, generated_at)

    if dry_run:
        preview_path = write_preview(html_body)
        print(text_body)
        print(f"\nHTML náhled: {preview_path}", flush=True)
        if preview:
            webbrowser.open(preview_path.as_uri())
        fail_if_errors(results)
        return

    subject = f"Obědové menu – {generated_at:%d.%m.%Y}"
    try:
        send_email(subject=subject, html_body=html_body, text_body=text_body)
    except Exception as exc:  # noqa: BLE001 - surface SMTP/config failures as a red job
        print(f"Failed to send email: {exc}", flush=True)
        raise SystemExit(1) from exc
    print(f"Sent menu email for {len(results)} restaurant(s).")
    fail_if_errors(results)


if __name__ == "__main__":
    main()
