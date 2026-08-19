"""Adapter for restaurants using the ChoiceQR ordering platform (choiceqr.com).

ChoiceQR renders each menu page as a server-side-rendered Next.js app, so
instead of scraping the visible HTML we parse the __NEXT_DATA__ JSON blob
that ships with the page (React hydration data) - it contains the full menu
catalogue directly as structured records. Daily lunch menus are modelled as
a "section" (e.g. "Polední menu") whose items are grouped into day-of-week
"categories" (Pondělí..Pátek), so we only keep items for today's category.
"""
from __future__ import annotations

import json
from datetime import date
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .menubot import BROWSER_HEADERS, Menu, MenuItem

CZECH_WEEKDAYS = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"]


def fetch_choiceqr_menu(url: str, timeout: int = 20) -> Menu:
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    app = _extract_app_data(soup)
    if app is None:
        return Menu(raw_text=soup.get_text(separator=" ", strip=True))

    section_hurl = urlparse(url).path.strip("/")
    section = next((s for s in app.get("sections", []) if s.get("hurl") == section_hurl), None)
    if section is None:
        return Menu(raw_text=soup.get_text(separator=" ", strip=True))

    today_name = CZECH_WEEKDAYS[date.today().weekday()]
    category = next((c for c in app.get("categories", []) if c.get("name") == today_name), None)
    if category is None:
        return Menu(
            heading=section.get("name", ""),
            raw_text=f"Dnes ({today_name}) restaurace nenabízí polední menu.",
        )

    items = [
        MenuItem(
            name=entry.get("name", ""),
            description=entry.get("description") or "",
            price=_format_price(entry.get("price")),
            allergens=", ".join(str(a) for a in entry.get("allergens") or []),
        )
        for entry in app.get("menu", [])
        if entry.get("section") == section["_id"] and entry.get("category") == category["_id"]
    ]
    heading = f"{section.get('name', '')} – {today_name}"
    raw_text = " ".join(f"{item.name} ({item.price})" for item in items)
    return Menu(heading=heading, items=items, raw_text=raw_text)


def _extract_app_data(soup: BeautifulSoup) -> dict | None:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)["props"]["app"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _format_price(price_cents: object) -> str:
    if not isinstance(price_cents, (int, float)):
        return ""
    czk = price_cents / 100
    if czk == int(czk):
        return f"{int(czk)} Kč"
    return f"{czk:.2f} Kč"
