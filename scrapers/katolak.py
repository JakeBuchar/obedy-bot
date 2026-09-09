"""Adapter for Restaurace Obecní dům (katolak.cz).

The Angular app loads today's menu from https://be.katolak.cz. The JSON
view includes OCR-style text spans plus a JPEG of the printed menu.
"""
from __future__ import annotations

import re
from datetime import date

import requests

from .http import with_retries
from .menubot import BROWSER_HEADERS, Menu, MenuItem
from .prague import format_date, reject_stale, today_prague

API_VIEW_URL = "https://be.katolak.cz/menu/today/view"
PAGE_IMAGE_URL = "https://be.katolak.cz/menu/today/page/0"

PRICE_RE = re.compile(r"^\d[\d\s]*,-\s*$")
ALLERGEN_RE = re.compile(r"^\([\d,\s]+\)$")
SIZE_RE = re.compile(r"^(?:\d+\s*(?:g|ks|ml)|1ks)$", re.IGNORECASE)
SKIP_RE = re.compile(
    r"^(restaurace|obecní dům|polévky|dnes nabízíme|výhodná menu|menu \d+\)|"
    r"objednávky|k výhodnému)",
    re.IGNORECASE,
)


def fetch_katolak_menu(url: str, today: date | None = None, timeout: int = 20) -> Menu:
    today = today_prague(today)
    headers = {**BROWSER_HEADERS, "Accept": "application/json"}
    response = with_retries(
        lambda: requests.get(API_VIEW_URL, headers=headers, timeout=timeout), API_VIEW_URL
    )
    response.raise_for_status()
    payload = response.json()

    published = _published_date(payload)
    reject_stale(published, today, "Obecní dům")

    pages = payload.get("pages") or []
    if not pages:
        raise ValueError("Obecní dům daily menu has no pages")

    spans = pages[0].get("spans") or []
    items = _items_from_spans(spans)
    image_url = PAGE_IMAGE_URL if pages else ""
    heading = f"Denní menu {format_date(published or today)}"
    raw_text = " ".join(span.get("text", "").strip() for span in spans if span.get("text"))
    if not items and not image_url:
        raise ValueError("Obecní dům daily menu could not be parsed")
    return Menu(heading=heading, items=items, raw_text=raw_text, image_url=image_url)


def _published_date(payload: dict) -> date | None:
    try:
        return date.fromisoformat(payload.get("forDate") or "")
    except ValueError:
        return None


def _items_from_spans(spans: list[dict]) -> list[MenuItem]:
    texts: list[str] = []
    for span in spans:
        text = " ".join((span.get("text") or "").split())
        if not text:
            continue
        if text.lower().startswith("výhodná menu"):
            break
        texts.append(text)

    items: list[MenuItem] = []
    buffer: list[str] = []
    for text in texts:
        if SKIP_RE.match(text):
            continue
        if PRICE_RE.match(text):
            item = _item_from_buffer(buffer, _format_price(text))
            if item:
                items.append(item)
            buffer = []
            continue
        buffer.append(text)
    return items


def _format_price(text: str) -> str:
    digits = re.sub(r"[^\d]", "", text)
    return f"{digits} Kč" if digits else text


def _item_from_buffer(parts: list[str], price: str) -> MenuItem | None:
    size = ""
    allergens = ""
    name_parts: list[str] = []
    for part in parts:
        if SIZE_RE.match(part) and not size:
            size = part
            continue
        if ALLERGEN_RE.match(part):
            allergens = part
            continue
        name_parts.append(part)
    name = " ".join(name_parts).strip()
    if not name:
        return None
    return MenuItem(name=name, price=price, description=size, allergens=allergens)
