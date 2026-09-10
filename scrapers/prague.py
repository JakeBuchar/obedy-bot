"""Shared Europe/Prague date helpers for daily-menu adapters."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")

CZECH_WEEKDAYS = ("Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle")
CZECH_DATE_RE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")


def today_prague(today: date | None = None) -> date:
    return today or datetime.now(PRAGUE).date()


def czech_weekday(d: date) -> str:
    return CZECH_WEEKDAYS[d.weekday()]


def format_date(d: date) -> str:
    return f"{d.day}.{d.month}.{d.year}"


def parse_czech_date(text: str) -> date | None:
    """First d.m.yyyy in the text (also "9. 9. 2026"), or None."""
    match = CZECH_DATE_RE.search(" ".join(text.split()))
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


class StaleMenuError(ValueError):
    """The restaurant is reachable, but still showing a previous day's menu.

    That is not something we can fix, so the email still carries a notice
    and the GitHub Actions run stays green with a warning annotation. A red
    job is reserved for failures on our side (the site unreachable, a parser
    that no longer matches, a missing secret).
    """


def reject_stale(published: date | None, today: date, restaurant: str) -> None:
    """Refuse a menu the restaurant has not refreshed since a previous day.

    Restaurants swap the page to the next day as soon as lunch service ends,
    so a published date ahead of today is normal in the afternoon and still
    worth emailing - only a date in the past means the page is stale.
    """
    if published is not None and published < today:
        raise StaleMenuError(
            f"{restaurant} still shows the menu for {format_date(published)}, "
            f"not {format_date(today)}"
        )


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())
