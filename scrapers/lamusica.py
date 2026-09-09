"""Adapter for La Musica's Tastyc / Elementor daily lunch block.

The page has a daily "POLEDNÍ MENU: <weekday> d. m. yyyy" block, then a
separate weekly block. Only the daily `.tst-menu-rows` section is used.
"""
from __future__ import annotations

from datetime import date

import requests
from bs4 import BeautifulSoup

from .http import with_retries
from .menubot import BROWSER_HEADERS, Menu, MenuItem
from .prague import text_has_date, today_prague


def fetch_lamusica_menu(url: str, today: date | None = None, timeout: int = 20) -> Menu:
    today = today_prague(today)
    response = with_retries(lambda: requests.get(url, headers=BROWSER_HEADERS, timeout=timeout), url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    daily_block = None
    heading = ""
    for block in soup.select(".tst-menu-rows"):
        title = block.select_one(".tst-title--h")
        title_text = " ".join(title.get_text(" ", strip=True).split()) if title else ""
        if "POLEDNÍ MENU" in title_text.upper() and "TÝDENNÍ" not in title_text.upper():
            daily_block = block
            heading = title_text
            break

    if daily_block is None:
        raise ValueError("La Musica daily lunch block was not found")
    if not text_has_date(heading, today):
        raise ValueError(f"La Musica has no polední menu published for {today.day}.{today.month}.{today.year}")

    items: list[MenuItem] = []
    for card in daily_block.select(".tst-menu-book-item"):
        name_tag = card.select_one(".tst-menu-book-name h5")
        desc_tag = card.select_one(".tst-menu-book-name .tst-text")
        price_tag = card.select_one(".tst-price")
        name = " ".join(name_tag.get_text(" ", strip=True).split()) if name_tag else ""
        if not name:
            continue
        description = " ".join(desc_tag.get_text(" ", strip=True).split()) if desc_tag else ""
        price = " ".join(price_tag.get_text(" ", strip=True).split()) if price_tag else ""
        items.append(MenuItem(name=name, description=description, price=price))

    if not items:
        raise ValueError("La Musica daily menu contains no dishes")

    return Menu(heading=heading, items=items, raw_text=daily_block.get_text(" ", strip=True))
