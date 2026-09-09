"""Adapter for Restaurace Vodní svět (Kolín).

Daily lunch is in #dennimenu as `.deme_item` rows (size / name / price),
under a heading like "...pro 9.9.2026". The all-you-can-eat and standing
menu sections are ignored.
"""
from __future__ import annotations

from datetime import date

import requests
from bs4 import BeautifulSoup

from .menubot import BROWSER_HEADERS, Menu, MenuItem
from .prague import format_date, parse_czech_date, reject_stale, today_prague


def fetch_vodni_menu(url: str, today: date | None = None, timeout: int = 20) -> Menu:
    today = today_prague(today)
    response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")

    section = soup.select_one("#dennimenu")
    if section is None:
        raise ValueError("Vodní svět daily menu section (#dennimenu) was not found")

    published = parse_czech_date(section.get_text(" ", strip=True))
    reject_stale(published, today, "Vodní svět")

    place = section.select_one(".deme_place")
    if place is None:
        raise ValueError("Vodní svět daily dish list was not found")

    heading = f"Denní menu {format_date(published or today)}"
    items: list[MenuItem] = []
    category = ""
    for row in place.select(".deme_item"):
        bold = row.find("b")
        spans = row.find_all("span")
        if bold and not spans:
            category = bold.get_text(" ", strip=True)
            continue
        if len(spans) < 2:
            continue
        size = spans[0].get_text(" ", strip=True)
        name = spans[1].get_text(" ", strip=True)
        price = spans[2].get_text(" ", strip=True) if len(spans) > 2 else ""
        if not name:
            continue
        description = size if size and size.lower() not in {"bufet"} else ""
        items.append(MenuItem(name=name, price=price, category=category, description=description))

    if not items:
        raise ValueError("Vodní svět daily menu contains no dishes")

    return Menu(heading=heading, items=items, raw_text=place.get_text(" ", strip=True))
