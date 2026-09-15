"""Entry point: load restaurant config, scrape each one, email the result.

Run locally for testing:
    $env:SMTP_HOST="smtp.gmail.com"
    $env:SMTP_USER="you@gmail.com"
    $env:SMTP_PASSWORD="<app password>"
    $env:MAIL_TO="you@gmail.com"
    python main.py                    # Praha (default)
    $env:CONFIG_PATH="config/kolin.yaml"
    python main.py --dry-run          # Kolín

Add --dry-run to skip sending the email, print the text result, and write
email_preview.html (open that file to see the real HTML email). Add
--preview to also open email_preview.html in a browser.
"""
from __future__ import annotations

import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from already_sent import already_sent_today
from email_sender import send_email
from logos import inline_logos
from render import render_html, render_text
from scrapers.arco import fetch_arco_menu
from scrapers.choiceqr import fetch_choiceqr_menu
from scrapers.farina import fetch_farina_menu
from scrapers.generic_html import fetch_generic_menu
from scrapers.katolak import fetch_katolak_menu
from scrapers.lamusica import fetch_lamusica_menu
from scrapers.laventola import fetch_laventola_menu
from scrapers.menubot import fetch_menubot_menu
from scrapers.nasidlisti import fetch_nasidlisti_menu
from scrapers.prague import StaleMenuError
from scrapers.stoleta import fetch_stoleta_menu
from scrapers.vodni import fetch_vodni_menu

DEFAULT_CONFIG_PATH = "config/praha.yaml"
PREVIEW_PATH = Path("email_preview.html")
PRAGUE = ZoneInfo("Europe/Prague")


def write_preview(html_body: str) -> Path:
    """Overwrite email_preview.html with the rendered HTML email body."""
    PREVIEW_PATH.write_text(html_body, encoding="utf-8")
    return PREVIEW_PATH.resolve()


def config_path() -> str:
    return os.environ.get("CONFIG_PATH", DEFAULT_CONFIG_PATH).strip() or DEFAULT_CONFIG_PATH


def city_label() -> str:
    return os.environ.get("CITY", "Praha").strip() or "Praha"


def load_restaurants(path: str | None = None) -> list[dict]:
    with open(path or config_path(), encoding="utf-8") as f:
        restaurants = yaml.safe_load(f)["restaurants"] or []
    # Order is the yaml list order (Masaryčka is last on purpose in Praha).
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
            "stale": False,
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
            elif adapter == "laventola":
                entry["menu"] = fetch_laventola_menu(r["url"])
            elif adapter == "vodni":
                entry["menu"] = fetch_vodni_menu(r["url"])
            elif adapter == "farina":
                entry["menu"] = fetch_farina_menu(r["url"])
            elif adapter == "lamusica":
                entry["menu"] = fetch_lamusica_menu(r["url"])
            elif adapter == "arco":
                entry["menu"] = fetch_arco_menu(r["url"])
            elif adapter == "katolak":
                entry["menu"] = fetch_katolak_menu(r["url"])
            elif adapter == "nasidlisti":
                entry["menu"] = fetch_nasidlisti_menu(r["url"])
            elif adapter == "stoleta":
                entry["menu"] = fetch_stoleta_menu(r["url"])
            else:
                raise ValueError(f"Unknown adapter '{adapter}'")
            # Menu.image_url is auto-discovered fresh on every scrape (see
            # generic_html.fetch_generic_menu), so the email always shows
            # whatever photo is currently live instead of a stale URL.
            entry["menu_image_url"] = entry["menu"].image_url or None
        except StaleMenuError as exc:
            # Restaurant is up, the page is just yesterday's menu. The email
            # still shows a notice; the job stays green with a warning.
            entry["error"] = str(exc)
            entry["stale"] = True
            print(f"::warning title={r['name']}::{exc}", flush=True)
        except Exception as exc:  # noqa: BLE001 - we want to keep going for other restaurants
            entry["error"] = str(exc)
            print(f"::error title={r['name']}::{exc}", flush=True)
        results.append(entry)
    return results


def scrape_errors(results: list[dict]) -> list[tuple[str, str]]:
    return [(r["name"], r["error"]) for r in results if r.get("error")]


def scrape_failures(results: list[dict]) -> list[tuple[str, str]]:
    return [(r["name"], r["error"]) for r in results if r.get("error") and not r.get("stale")]


def scrape_stale(results: list[dict]) -> list[tuple[str, str]]:
    return [(r["name"], r["error"]) for r in results if r.get("stale")]


def fail_if_errors(results: list[dict]) -> None:
    """Turn the GitHub Actions run red only when something on our side failed.

    A restaurant that is still showing yesterday's menu is a warning
    (`::warning::`, yellow in the Actions log) and does not fail the job.
    Connection errors, parser mismatches and missing secrets still exit 1,
    because those we can actually fix. The email goes out either way.
    """
    stale = scrape_stale(results)
    if stale:
        print(
            f"{len(stale)} restaurant(s) have not published today's menu:",
            flush=True,
        )
        for name, message in stale:
            print(f"  - {name}: {message}", flush=True)

    failures = scrape_failures(results)
    if not failures:
        return
    print(
        f"Failing the run: {len(failures)} restaurant(s) could not be scraped:",
        flush=True,
    )
    for name, message in failures:
        print(f"  - {name}: {message}", flush=True)
    sys.exit(1)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    preview = "--preview" in sys.argv
    dry_run = "--dry-run" in sys.argv or preview

    # Whichever trigger gets here first sends; the rest bail out. That covers
    # an external scheduler retrying its dispatch, and a scheduled run should
    # anything ever put a cron back. Clicking "Run workflow" by hand leaves
    # skip_if_sent unset and always sends - asking for a run means asking for
    # an email.
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    skip_if_sent = os.environ.get("SKIP_IF_SENT", "").strip().lower() == "true"
    if (scheduled or skip_if_sent) and not dry_run:
        if already_sent_today():
            return

    restaurants = load_restaurants()
    if not restaurants:
        print(f"No restaurants in {config_path()}; nothing to send.", flush=True)
        raise SystemExit(1)

    results = scrape_all(restaurants)

    generated_at = datetime.now(PRAGUE)
    text_body = render_text(results, generated_at)

    if dry_run:
        # The preview keeps the plain logo URLs: a browser loads those
        # directly, while cid: references only resolve inside a message.
        preview_path = write_preview(render_html(results, generated_at, city=city_label()))
        print(text_body)
        print(f"\nHTML náhled: {preview_path}", flush=True)
        if preview:
            webbrowser.open(preview_path.as_uri())
        fail_if_errors(results)
        return

    logo_images = inline_logos(results)
    html_body = render_html(results, generated_at, city=city_label())

    subject = f"Obědové menu ({city_label()}) – {generated_at:%d.%m.%Y}"
    try:
        send_email(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            inline_images=logo_images,
        )
    except Exception as exc:  # noqa: BLE001 - surface SMTP/config failures as a red job
        print(f"Failed to send email: {exc}", flush=True)
        raise SystemExit(1) from exc
    print(f"Sent menu email for {len(results)} restaurant(s).")
    fail_if_errors(results)


if __name__ == "__main__":
    main()
