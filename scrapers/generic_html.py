"""Fallback adapter for restaurants that render the menu in their own page
HTML with no external widget. Configure with a CSS selector per restaurant
in restaurants.yaml (item_selector, name_selector, price_selector).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from .menubot import BROWSER_HEADERS, MenuItem, Menu

MENU_HINT_RE = re.compile(r"menu", re.IGNORECASE)


def fetch_generic_menu(
    url: str,
    item_selector: str,
    name_selector: str = "",
    price_selector: str = "",
    content_selector: str = "",
    image_selector: str = "",
    timeout: int = 20,
) -> Menu:
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    # content_selector scopes both item search and the raw-text fallback to a
    # sub-region of the page (e.g. "main"), so nav/footer boilerplate doesn't
    # drown out the actual menu when no items match item_selector.
    scope = (soup.select_one(content_selector) if content_selector else None) or soup

    items: list[MenuItem] = []
    for block in scope.select(item_selector):
        name_tag = block.select_one(name_selector) if name_selector else None
        price_tag = block.select_one(price_selector) if price_selector else None

        name = name_tag.get_text(strip=True) if name_tag else ""
        price = price_tag.get_text(strip=True) if price_tag else ""
        description = block.get_text(separator=" ", strip=True)
        if name:
            description = description.replace(name, "", 1).strip()
        if price:
            description = description.replace(price, "", 1).strip()

        items.append(MenuItem(name=name or description[:60], description=description, price=price))

    # Some sites publish the daily menu purely as an image (no item markup at
    # all); fall back to any alt text so the email still shows *something*
    # instead of an empty block.
    visible_text = scope.get_text(separator=" ", strip=True)
    alt_texts = [img.get("alt", "").strip() for img in scope.find_all("img")]
    raw_text = " ".join(text for text in [visible_text, *alt_texts] if text)

    image_url = _find_menu_image_url(scope, url, image_selector)
    return Menu(items=items, raw_text=raw_text, image_url=image_url)


def _find_menu_image_url(scope: Tag, page_url: str, image_selector: str = "") -> str:
    if image_selector:
        img = scope.select_one(image_selector)
        return urljoin(page_url, img["src"]) if img and img.get("src") else ""

    images = [img for img in scope.find_all("img") if img.get("src")]
    if not images:
        return ""

    # Restaurants that publish the daily menu purely as a photo tend to embed
    # it alongside unrelated gallery/logo images in the same content area, so
    # prefer whichever <img> looks menu-related by filename/alt text, and
    # otherwise fall back to the visually largest one (a food-gallery thumbnail
    # is reliably smaller than a full menu scan).
    best = max(images, key=lambda img: (_looks_like_menu(img), _declared_area(img)))
    return urljoin(page_url, best["src"])


def _looks_like_menu(img: Tag) -> bool:
    haystack = f"{img.get('src', '')} {img.get('alt', '')}"
    return bool(MENU_HINT_RE.search(haystack))


def _declared_area(img: Tag) -> int:
    try:
        return int(img.get("width", 0)) * int(img.get("height", 0))
    except (TypeError, ValueError):
        return 0
