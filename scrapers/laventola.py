"""Adapter for Pizzeria La Ventola's lunch menu.

The daily menu lives in #menu as a Food Menu Pro widget. The same dishes
are rendered twice (a hidden "all" tab plus the visible tab), so items are
deduped by name+price. Heading is the widget title plus the date line.
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from .menubot import BROWSER_HEADERS, Menu, MenuItem


def fetch_laventola_menu(url: str, timeout: int = 20) -> Menu:
    response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    scope = soup.select_one("#menu")
    if scope is None:
        raise ValueError("La Ventola menu section (#menu) was not found")

    title = scope.select_one(".head-title")
    date_line = scope.select_one(".desc_price_list")
    heading_parts = []
    if title:
        heading_parts.append(title.get_text(" ", strip=True))
    if date_line:
        heading_parts.append(" ".join(date_line.get_text(" ", strip=True).split()))
    heading = " · ".join(part for part in heading_parts if part)

    items: list[MenuItem] = []
    seen: set[tuple[str, str]] = set()
    for block in scope.select(".name-price-desc"):
        name_tag = block.select_one(".name")
        price_tag = block.select_one(".spl-price")
        name = name_tag.get_text(" ", strip=True) if name_tag else ""
        price = price_tag.get_text(" ", strip=True) if price_tag else ""
        if not name:
            continue
        key = (name, price)
        if key in seen:
            continue
        seen.add(key)
        items.append(MenuItem(name=name, price=price))

    if not items:
        raise ValueError("La Ventola lunch menu contains no dishes")

    return Menu(heading=heading, items=items, raw_text=scope.get_text(" ", strip=True))
