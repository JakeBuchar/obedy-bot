"""Adapter for restaurants using the menubot.cz daily-menu widget.

menubot.cz serves the menu as a JS snippet that calls document.write() with
a big HTML string. Different restaurants use slightly different templates
(FUZE-style semantic divs vs. plain <h3>/<p> pairs), so we try a couple of
parsing strategies and fall back to a flat text dump if none of them match,
so the email always contains *something* useful even when the layout
changes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
}

DOCUMENT_WRITE_RE = re.compile(r'document\.write\("((?:[^"\\]|\\.)*)"\)')
PRICE_RE = re.compile(r"(\d[\d\s]*)\s*Kč")
ALLERGEN_TEXT_RE = re.compile(r"^[\d,\s]+$")


@dataclass
class MenuItem:
    name: str
    description: str = ""
    price: str = ""
    category: str = ""
    allergens: str = ""


@dataclass
class Menu:
    heading: str = ""
    items: list[MenuItem] = field(default_factory=list)
    raw_text: str = ""
    image_url: str = ""


def fetch_menubot_menu(menubot_hash: str, lang: str = "_a", timeout: int = 20) -> Menu:
    url = f"https://www.menubot.cz/app/users/{menubot_hash}/export/dailymenu{lang}.js"
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    resp.raise_for_status()

    fragment_html = _extract_document_write_html(resp.text)
    soup = BeautifulSoup(fragment_html, "html.parser")

    items = _parse_category_tables(soup)
    if not items:
        items = _parse_category_strong_items(soup)
    if not items:
        items = _parse_semantic_boxes(soup)
    if not items:
        items = _parse_heading_paragraph_pairs(soup)

    heading = _extract_heading(soup)
    raw_text = soup.get_text(separator=" ", strip=True)

    return Menu(heading=heading, items=items, raw_text=raw_text)


def _extract_document_write_html(js_source: str) -> str:
    matches = DOCUMENT_WRITE_RE.findall(js_source)
    if not matches:
        return ""
    # The menu content is always the largest document.write() call; smaller
    # ones (banners, popups) are noise.
    largest = max(matches, key=len)
    try:
        return json.loads(f'"{largest}"')
    except json.JSONDecodeError:
        return largest


def _extract_heading(soup: BeautifulSoup) -> str:
    # Search h1/h2 together (in document order) rather than all h1s first,
    # since some templates bury an unrelated <h1> (e.g. a GDPR popup) further
    # down the page after the real <h2> menu heading.
    tag = soup.find(["h1", "h2"])
    if tag:
        return tag.get_text(separator=" ", strip=True)
    return ""


def _parse_semantic_boxes(soup: BeautifulSoup) -> list[MenuItem]:
    """FUZE-style: <div class="menu__item"><h3 class="menu__type">category</h3>
    <div class="menu__box"><p class="menu__text"><strong>name</strong> desc
    <small>allergens</small></p><p class="menu__price">price</p></div>...
    """
    items: list[MenuItem] = []
    for item_block in soup.select(".menu__item"):
        category_tag = item_block.select_one(".menu__type")
        category = category_tag.get_text(strip=True) if category_tag else ""

        for box in item_block.select(".menu__box"):
            text_tag = box.select_one(".menu__text")
            price_tag = box.select_one(".menu__price")
            if not text_tag:
                continue

            strong_tag = text_tag.find("strong")
            name = strong_tag.get_text(strip=True) if strong_tag else ""

            small_tag = text_tag.find("small")
            allergens = small_tag.get_text(strip=True) if small_tag else ""

            full_text = text_tag.get_text(separator=" ", strip=True)
            description = full_text
            if name:
                description = description.replace(name, "", 1).strip()
            if allergens:
                description = description.replace(allergens, "", 1).strip()

            price = price_tag.get_text(strip=True) if price_tag else ""

            items.append(
                MenuItem(
                    name=name or full_text,
                    description=description,
                    price=price,
                    category=category,
                    allergens=allergens,
                )
            )
    return items


def _is_hidden_week_day(tag) -> bool:
    """Some menubot templates (e.g. Sia) publish the whole week in one HTML
    payload and only hide the non-today days client-side via a "hideweek"
    class (toggled by a "show whole week" JS button), so a pure HTML parse
    would otherwise pick up every day's items mixed together.
    """
    return "hideweek" in (tag.get("class") or [])


def _parse_category_tables(soup: BeautifulSoup) -> list[MenuItem]:
    """Hybernská-style: <div class="dm-cat"><div class="dm-cat-header">
    <div class="dm-cat-title"><h2>category</h2></div></div><div class="dm-item">
    <div class="dm-content"><table><tr><td><h3>name</h3><p>desc</p><p>allergens</p>
    </td><td>price</td></tr></table></div></div></div> repeated, with the category
    header only present on the first item of each category group.
    """
    items: list[MenuItem] = []
    category = ""
    for cat_block in soup.select(".dm-cat"):
        if _is_hidden_week_day(cat_block):
            continue
        title_tag = cat_block.select_one(".dm-cat-title h2")
        if title_tag:
            category = title_tag.get_text(strip=True)

        for item_block in cat_block.select(".dm-item"):
            name_tag = item_block.find("h3")
            cells = item_block.select("table td")
            if not name_tag or len(cells) < 2:
                # No <table> here means this is actually the Sia-style layout
                # (see _parse_category_strong_items) - leave it for that parser.
                continue

            price = cells[-1].get_text(strip=True) if len(cells) >= 2 else ""

            paragraphs = [
                p.get_text(strip=True)
                for p in (cells[0].find_all("p") if cells else [])
                if p.get_text(strip=True)
            ]
            allergens = ""
            if paragraphs and ALLERGEN_TEXT_RE.match(paragraphs[-1]):
                allergens = paragraphs.pop()

            items.append(
                MenuItem(
                    name=name_tag.get_text(strip=True),
                    description=" ".join(paragraphs),
                    price=price,
                    category=category,
                    allergens=allergens,
                )
            )
    return items


def _parse_category_strong_items(soup: BeautifulSoup) -> list[MenuItem]:
    """Sia-style: <div class="dm-cat"><div class="dm-cat-header"><div class="dm-cat-title">
    <h2>category</h2></div></div><div class="dm-item"><div class="dm-content"><h3>name</h3>
    <p>desc (often empty)</p><strong class="alerg">price&nbsp;&nbsp;&nbsp;allergens</strong>
    <strong class="special"></strong></div></div></div> repeated, with price and allergens
    packed into a single <strong class="alerg"> tag separated by a run of &nbsp; chars.
    """
    items: list[MenuItem] = []
    category = ""
    for cat_block in soup.select(".dm-cat"):
        if _is_hidden_week_day(cat_block):
            continue
        title_tag = cat_block.select_one(".dm-cat-title h2")
        if title_tag:
            category = title_tag.get_text(strip=True)

        for item_block in cat_block.select(".dm-item"):
            content = item_block.select_one(".dm-content")
            name_tag = content.find("h3") if content else None
            alerg_tag = content.select_one("strong.alerg") if content else None
            if not name_tag or alerg_tag is None:
                continue

            description = " ".join(
                p.get_text(strip=True) for p in content.find_all("p") if p.get_text(strip=True)
            )

            parts = re.split(r"\s{2,}", alerg_tag.get_text(strip=True))
            price = parts[0] if parts else ""
            allergens = " ".join(parts[1:])

            items.append(
                MenuItem(
                    name=name_tag.get_text(strip=True),
                    description=description,
                    price=price,
                    category=category,
                    allergens=allergens,
                )
            )
    return items


def _parse_heading_paragraph_pairs(soup: BeautifulSoup) -> list[MenuItem]:
    """Han.sik-style: <h3>name</h3><p>description<br>NN Kč</p> repeated."""
    items: list[MenuItem] = []
    for h3 in soup.find_all("h3"):
        name = h3.get_text(separator=" ", strip=True)
        if not name:
            continue

        sibling = h3.find_next_sibling()
        if not sibling or sibling.name != "p":
            continue

        lines = [
            line.strip()
            for line in sibling.get_text(separator="\n", strip=True).split("\n")
            if line.strip()
        ]
        if not lines:
            continue

        price = ""
        description_lines = lines
        if lines and PRICE_RE.search(lines[-1]):
            price_match = PRICE_RE.search(lines[-1])
            price = f"{price_match.group(1).strip()} Kč"
            description_lines = lines[:-1]

        items.append(
            MenuItem(name=name, description=" ".join(description_lines), price=price)
        )
    return items
