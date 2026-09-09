"""Shared Europe/Prague date helpers for daily-menu adapters."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")

CZECH_WEEKDAYS = ("Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle")


def today_prague(today: date | None = None) -> date:
    return today or datetime.now(PRAGUE).date()


def czech_weekday(d: date) -> str:
    return CZECH_WEEKDAYS[d.weekday()]


def date_strings(d: date) -> tuple[str, ...]:
    return (
        f"{d.day}.{d.month}.{d.year}",
        f"{d.day}. {d.month}. {d.year}",
        f"{d.day:02d}.{d.month:02d}.{d.year}",
        d.isoformat(),
    )


def text_has_date(text: str, d: date) -> bool:
    compact = " ".join(text.split())
    return any(marker in compact for marker in date_strings(d))


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())
