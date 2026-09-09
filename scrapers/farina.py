"""Adapter for Farina's JetEngine polední-menu listing.

The page shows one day's post. Take dishes under "Denní nabídka" and stop
before "Týdenní nabídka".
"""
from __future__ import annotations

import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from .menubot import BROWSER_HEADERS, Menu, MenuItem
from .prague import czech_weekday, today_prague

PRICE_RE = re.compile(r"^\d[\d\s]*\s*Kč$", re.IGNORECASE)
WEEKLY_HEADING = re.compile(r"týdenní", re.IGNORECASE)
DAILY_HEADING = re.compile(r"denní nabídka", re.IGNORECASE)


def fetch_farina_menu(url: str, today: date | None = None, timeout: int = 20) -> Menu:
    today = today_prague(today)
    response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    listing = soup.select_one(".jet-listing-grid__item")
    if listing is None:
        raise ValueError("Farina polední menu listing was not found")

    fields: list[str] = []
    for node in listing.select(".jet-listing-dynamic-field__content, .elementor-heading-title"):
        text = " ".join(node.get_text(" ", strip=True).split())
        if text:
            fields.append(text)

    weekday = czech_weekday(today)
    if weekday not in fields:
        raise ValueError(f"Farina has no polední menu published for {weekday}")

    start = next((i for i, text in enumerate(fields) if DAILY_HEADING.search(text)), None)
    if start is None:
        raise ValueError("Farina daily offer heading was not found")
    stop = next((i for i, text in enumerate(fields[start + 1 :], start + 1) if WEEKLY_HEADING.search(text)), len(fields))

    items: list[MenuItem] = []
    pending_name = ""
    for text in fields[start + 1 : stop]:
        if PRICE_RE.match(text):
            if pending_name:
                items.append(MenuItem(name=pending_name, price=text))
                pending_name = ""
            continue
        pending_name = text

    if not items:
        raise ValueError(f"Farina daily menu for {weekday} contains no dishes")

    hours = next((text for text in fields if re.search(r"\d+:\d+", text)), "")
    heading = " · ".join(part for part in [weekday, hours] if part)
    return Menu(heading=heading, items=items, raw_text=" ".join(fields[start:stop]))
