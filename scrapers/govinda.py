"""Adapter for Góvinda's weekly menu page.

The page publishes every weekday in a separate column. Select the column
whose heading contains today's Prague date so the email does not include
the whole week (or a stale duplicate column left in the page).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from .menubot import BROWSER_HEADERS, Menu, MenuItem

PRAGUE = ZoneInfo("Europe/Prague")
ALLERGENS_RE = re.compile(r"\s*(\([\d,\s]+\))\s*$")


def fetch_govinda_menu(
    url: str,
    today: date | None = None,
    timeout: int = 20,
) -> Menu:
    response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    today = today or datetime.now(PRAGUE).date()
    date_text = f"{today.day}.{today.month}.{today.year}"
    menu_scope = soup.select_one("#menu")
    if menu_scope is None:
        raise ValueError("Góvinda menu section (#menu) was not found")

    day_column = next(
        (
            column
            for column in menu_scope.select(".col.space-bottom")
            if date_text in column.get_text(" ", strip=True)
        ),
        None,
    )
    if day_column is None:
        raise ValueError(f"Góvinda has no menu published for {date_text}")

    heading_tag = day_column.find(["h3", "h4"])
    heading = heading_tag.get_text(" ", strip=True) if heading_tag else date_text
    items: list[MenuItem] = []
    for paragraph in day_column.find_all("p"):
        category_tag = paragraph.find(["b", "strong"])
        full_text = paragraph.get_text(" ", strip=True)
        if not full_text:
            continue

        category = category_tag.get_text(" ", strip=True).rstrip(" –-") if category_tag else ""
        description = full_text
        if category_tag:
            category_prefix = category_tag.get_text(" ", strip=True)
            description = description.removeprefix(category_prefix).strip(" –-")

        allergen_match = ALLERGENS_RE.search(description)
        allergens = allergen_match.group(1) if allergen_match else ""
        if allergen_match:
            description = description[: allergen_match.start()].rstrip()

        items.append(
            MenuItem(
                name=description,
                category=category,
                allergens=allergens,
            )
        )

    if not items:
        raise ValueError(f"Góvinda menu for {date_text} contains no dishes")

    return Menu(heading=heading, items=items, raw_text=day_column.get_text(" ", strip=True))
