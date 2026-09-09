"""Adapter for Hostinec Stoletá.

The public site is a Vite SPA; daily specials live in Supabase
(`menu_items` where is_daily_special is true). Credentials are the same
anon key the website embeds in its JS bundle.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

import requests

from .menubot import BROWSER_HEADERS, Menu, MenuItem
from .prague import czech_weekday, monday_of, today_prague

INDEX_JS_RE = re.compile(r'src="(/assets/index-[^"]+\.js)"')
SUPABASE_URL_RE = re.compile(r"https://[a-z0-9]+\.supabase\.co")
ANON_KEY_RE = re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")
CATEGORY_ORDER = {"Polévka": 1, "Hlavní chod": 2, "Dezert": 3}


def fetch_stoleta_menu(url: str, today: date | None = None, timeout: int = 20) -> Menu:
    today = today_prague(today)
    week_start = monday_of(today).isoformat()
    supabase_url, anon_key = _supabase_config(url, timeout=timeout)
    headers = {
        **BROWSER_HEADERS,
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Accept": "application/json",
    }
    params = {
        "select": "name,description,price,category,day_of_week,order_in_category,week_start_date",
        "is_daily_special": "eq.true",
        "week_start_date": f"eq.{week_start}",
        "day_of_week": f"eq.{today.weekday()}",
        "order": "order_in_category.asc",
    }
    response = requests.get(
        f"{supabase_url}/rest/v1/menu_items",
        headers=headers,
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    rows = response.json()
    if not rows:
        raise ValueError(f"Stoletá has no daily specials for {czech_weekday(today)} ({week_start})")

    rows.sort(key=lambda row: (CATEGORY_ORDER.get(row.get("category") or "", 99), row.get("order_in_category") or 0))
    items = [
        MenuItem(
            name=" ".join((row.get("name") or "").split()),
            description=" ".join((row.get("description") or "").split()),
            price=f"{row['price']} Kč" if row.get("price") is not None else "",
            category=row.get("category") or "",
        )
        for row in rows
        if row.get("name")
    ]
    if not items:
        raise ValueError("Stoletá daily specials contain no dishes")

    heading = f"{czech_weekday(today)} {today.day}.{today.month}.{today.year}"
    return Menu(heading=heading, items=items)


def _supabase_config(page_url: str, timeout: int) -> tuple[str, str]:
    page = requests.get(page_url, headers=BROWSER_HEADERS, timeout=timeout)
    page.raise_for_status()
    script = INDEX_JS_RE.search(page.text)
    if not script:
        raise ValueError("Stoletá frontend bundle was not found")
    bundle = requests.get(urljoin(page_url, script.group(1)), headers=BROWSER_HEADERS, timeout=timeout)
    bundle.raise_for_status()
    supabase_url = SUPABASE_URL_RE.search(bundle.text)
    anon_key = ANON_KEY_RE.search(bundle.text)
    if not supabase_url or not anon_key:
        raise ValueError("Stoletá Supabase credentials were not found in the frontend bundle")
    return supabase_url.group(0), anon_key.group(0)
