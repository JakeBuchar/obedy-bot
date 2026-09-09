"""Adapter for Restaurace Arco's Elementor price-list daily menu.

Take the first price list after a "POLEDNÍ MENU" heading that contains
today's date. Skip the weekly seasonal dish further down the page.
"""
from __future__ import annotations

from datetime import date

import requests
from bs4 import BeautifulSoup

from .menubot import BROWSER_HEADERS, Menu, MenuItem
from .prague import text_has_date, today_prague


def fetch_arco_menu(url: str, today: date | None = None, timeout: int = 20) -> Menu:
    today = today_prague(today)
    response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    heading_tag = next(
        (
            tag
            for tag in soup.select(".pbmit-element-title")
            if "POLEDNÍ MENU" in tag.get_text(" ", strip=True).upper()
            and "TÝDENNÍ" not in tag.get_text(" ", strip=True).upper()
        ),
        None,
    )
    if heading_tag is None:
        raise ValueError("Arco daily lunch heading was not found")

    heading = " ".join(heading_tag.get_text(" ", strip=True).split())
    if not text_has_date(heading, today):
        raise ValueError(f"Arco has no polední menu published for {today.day}.{today.month}.{today.year}")

    wrap = heading_tag.find_parent(class_="elementor-widget-wrap")
    price_list = wrap.select_one("ul.elementor-price-list") if wrap else None
    if price_list is None:
        raise ValueError("Arco daily price list was not found")

    items: list[MenuItem] = []
    for row in price_list.select(".elementor-price-list-item"):
        name_tag = row.select_one(".elementor-price-list-title")
        price_tag = row.select_one(".elementor-price-list-price")
        desc_tag = row.select_one(".elementor-price-list-description")
        name = " ".join(name_tag.get_text(" ", strip=True).split()) if name_tag else ""
        if not name:
            continue
        price = " ".join(price_tag.get_text(" ", strip=True).split()) if price_tag else ""
        description = " ".join(desc_tag.get_text(" ", strip=True).split()) if desc_tag else ""
        items.append(MenuItem(name=name, price=price, description=description))

    if not items:
        raise ValueError("Arco daily menu contains no dishes")

    return Menu(heading=heading, items=items, raw_text=price_list.get_text(" ", strip=True))
