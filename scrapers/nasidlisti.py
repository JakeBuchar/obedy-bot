"""Adapter for Restaurace Na Sídlišti 1962.

The homepage loads today's table from /denni-menu/fragment (JSON with an
HTML snippet). Rows use .dm-name / .dm-price / .dm-alerg / .dm-size.
"""
from __future__ import annotations

import json
from datetime import date
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from .menubot import BROWSER_HEADERS, Menu, MenuItem
from .prague import reject_stale, today_prague

FRAGMENT_PATH = "/denni-menu/fragment"


def fetch_nasidlisti_menu(url: str, today: date | None = None, timeout: int = 20) -> Menu:
    today = today_prague(today)
    parts = urlsplit(url)
    origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    fragment_url = origin + FRAGMENT_PATH
    headers = {**BROWSER_HEADERS, "Accept": "application/json, text/html;q=0.8"}
    response = requests.get(fragment_url, headers=headers, timeout=timeout)
    response.raise_for_status()

    payload = json.loads(response.text)
    html = payload.get("html") or ""
    soup = BeautifulSoup(html, "html.parser")

    head = soup.select_one(".today-head")
    reject_stale(_published_date(head), today, "Na Sídlišti")

    date_label = head.select_one(".today-date") if head else None
    heading = " ".join(date_label.get_text(" ", strip=True).split()) if date_label else today.isoformat()

    items: list[MenuItem] = []
    for row in soup.select("table.daily-menu tr"):
        name_tag = row.select_one(".dm-name")
        if not name_tag:
            continue
        allergen_tag = name_tag.select_one(".dm-alerg")
        allergens = allergen_tag.get_text(" ", strip=True) if allergen_tag else ""
        if allergen_tag:
            allergen_tag.extract()
        name = " ".join(name_tag.get_text(" ", strip=True).split())
        price_tag = row.select_one(".dm-price")
        price = " ".join(price_tag.get_text(" ", strip=True).split()) if price_tag else ""
        size_tag = row.select_one(".dm-size")
        size = " ".join(size_tag.get_text(" ", strip=True).split()) if size_tag else ""
        items.append(MenuItem(name=name, price=price, description=size, allergens=allergens))

    if not items:
        raise ValueError("Na Sídlišti daily menu contains no dishes")

    return Menu(heading=heading, items=items, raw_text=soup.get_text(" ", strip=True))


def _published_date(head: Tag | None) -> date | None:
    raw = (head.get("data-menu-date") if head else "") or ""
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None
